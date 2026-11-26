"""Transactional score invalidations shared by all web workers."""

import hashlib
import json
import logging
import select
from collections import defaultdict
from collections.abc import Iterator
from contextlib import closing
from threading import Event, Lock, Thread
from time import monotonic, sleep

import psycopg2
from psycopg2.extensions import connection
from sqlalchemy import func
from sqlalchemy import select as sql_select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

CHANNEL = "manytask_score_changes"
HEARTBEAT = 15
STREAM_LIFETIME = 300
logger = logging.getLogger(__name__)


def _topic(course: str, username: str | None) -> str:
    # Fixed-size payload even for long names; no student identifiers on the wire.
    return hashlib.sha256(json.dumps([course, username]).encode()).hexdigest()


def notify_score_change(session: Session, course: str, username: str | None = None) -> None:
    # PostgreSQL delivers NOTIFY only when the surrounding transaction commits.
    session.execute(sql_select(func.pg_notify(CHANNEL, _topic(course, username))))


class ScoreEvents:
    def __init__(self, database_url: str) -> None:
        self._dsn = make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)
        self._subscribers: defaultdict[str, set[Event]] = defaultdict(set)
        self._lock = Lock()
        self._listener: Thread | None = None
        self._initialized = False

    def stream(self, course: str, username: str) -> Iterator[str]:
        changed = Event()
        topics = (_topic(course, username), _topic(course, None))
        with self._lock:
            for topic in topics:
                self._subscribers[topic].add(changed)
            if self._initialized:
                changed.set()
            if self._listener is None:
                self._listener = Thread(target=self._listen, daemon=True, name="score-events")
                self._listener.start()

        try:
            # Subscribe before asking for the snapshot, including after a reconnect.
            expires = monotonic() + STREAM_LIFETIME
            while monotonic() < expires:
                if changed.wait(HEARTBEAT):
                    changed.clear()
                    yield "data: refresh\n\n"
                else:
                    yield ": keep-alive\n\n"
        finally:
            with self._lock:
                for topic in topics:
                    self._subscribers[topic].remove(changed)
                    if not self._subscribers[topic]:
                        del self._subscribers[topic]

    def _listen(self) -> None:
        while True:
            with self._lock:
                if not self._subscribers:
                    self._initialized = False
                    self._listener = None
                    return
            try:
                with closing(psycopg2.connect(self._dsn, connect_timeout=5)) as conn:
                    conn.autocommit = True
                    with conn.cursor() as cursor:
                        cursor.execute(f"LISTEN {CHANNEL}")
                    # Refresh after LISTEN succeeds to cover commits before setup or during an outage.
                    self._wake_all()
                    self._receive(conn)
            except (psycopg2.Error, OSError):
                logger.warning("PostgreSQL score listener unavailable; retrying in 5 seconds")
                if not self._initialized:
                    self._wake_all()  # Allow the initial snapshot even during a listener outage.
                sleep(5)

    def _wake_all(self) -> None:
        with self._lock:
            self._initialized = True
            for subscribers in self._subscribers.values():
                for changed in subscribers:
                    changed.set()

    def _receive(self, conn: connection) -> None:
        while True:
            with self._lock:
                if not self._subscribers:
                    return
            if select.select([conn], [], [], HEARTBEAT)[0]:
                conn.poll()
                with self._lock:
                    for notice in conn.notifies:
                        for changed in self._subscribers.get(notice.payload, ()):
                            changed.set()
                    conn.notifies.clear()

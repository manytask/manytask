from contextlib import closing
from typing import Any

import pytest
from sqlalchemy.orm import Session

from manytask.score_events import ScoreEvents, notify_score_change


def test_committed_score_notifications_reach_only_matching_streams(
    postgres_container: Any, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Idle streams emit comments, so a missing or misrouted event fails without hanging the test.
    monkeypatch.setattr("manytask.score_events.HEARTBEAT", 0.5)
    hub = ScoreEvents(postgres_container.get_connection_url())
    with (
        closing(hub.stream("python", "alice")) as alice,
        closing(hub.stream("python", "bob")) as bob,
        closing(hub.stream("cpp", "alice")) as cpp,
        Session(engine) as writer,
    ):
        refresh = "data: refresh\n\n"
        heartbeat = ": keep-alive\n\n"
        for stream in (alice, bob, cpp):
            assert next(stream) == refresh

        notify_score_change(writer, "python", "alice")
        writer.rollback()
        assert next(alice) == heartbeat
        notify_score_change(writer, "python", "alice")
        writer.commit()
        assert next(alice) == refresh
        assert next(bob) == heartbeat
        assert next(cpp) == heartbeat

        notify_score_change(writer, "python")
        writer.commit()
        assert next(alice) == next(bob) == refresh
        assert next(cpp) == heartbeat

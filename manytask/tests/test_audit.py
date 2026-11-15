import json
import logging
from collections.abc import Iterator
from http import HTTPStatus
from threading import Thread
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from flask import Flask, Response, g, has_request_context
from flask_wtf import CSRFProtect
from sqlalchemy import create_engine, delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from manytask.api import requires_token
from manytask.database import DataBaseApi
from manytask.main import CustomFlask
from manytask.utils.audit import (
    audit_context,
    audit_operation,
    install_request_audit,
    run_with_audit_context,
)
from manytask.utils.database_audit import audit_session


class AuditBase(DeclarativeBase):
    pass


class AuditRow(AuditBase):
    __tablename__ = "audit_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(unique=True)


@pytest.fixture(autouse=True)
def capture_audit(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="manytask.audit")


@pytest.fixture
def audit_db() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    AuditBase.metadata.create_all(engine)
    with audit_session(Session(engine)) as session:
        yield session
    engine.dispose()


def records(caplog: pytest.LogCaptureFixture, event: str) -> list[dict[str, Any]]:
    entries = [json.loads(record.getMessage()) for record in caplog.records if record.name == "manytask.audit"]
    return [entry for entry in entries if entry["event"] == event]


@pytest.mark.parametrize("finish", ["commit", "rollback", "close"])
def test_write_outcome_follows_transaction(audit_db: Session, caplog: pytest.LogCaptureFixture, finish: str) -> None:
    audit_session(audit_db)  # Attaching twice must not duplicate records.
    audit_db.add(AuditRow(value="private-submitted-text"))
    audit_db.flush()
    assert [entry["outcome"] for entry in records(caplog, "database.write")] == ["attempted"]
    getattr(audit_db, finish)()
    entries = records(caplog, "database.write")
    assert [entry["outcome"] for entry in entries] == [
        "attempted",
        "committed" if finish == "commit" else "rolled_back",
    ]
    assert entries[0]["write_id"] == entries[1]["write_id"]
    assert entries[0]["transaction_id"] == entries[1]["transaction_id"]
    assert "private-submitted-text" not in caplog.text


def test_failed_commit_never_logs_committed(audit_db: Session, caplog: pytest.LogCaptureFixture) -> None:
    audit_db.add_all([AuditRow(value="same-private-value"), AuditRow(value="same-private-value")])
    with pytest.raises(IntegrityError):
        audit_db.commit()
    audit_db.rollback()
    assert [entry["outcome"] for entry in records(caplog, "database.write")] == ["attempted", "rolled_back"]
    assert "same-private-value" not in caplog.text


def test_bulk_writes_and_orm_updates_are_audited(audit_db: Session, caplog: pytest.LogCaptureFixture) -> None:
    audit_db.execute(insert(AuditRow).values(value="initial"))
    audit_db.execute(update(AuditRow).values(value="changed"))
    row = audit_db.scalar(select(AuditRow))
    assert row is not None
    row.value = "orm-update"
    audit_db.flush()
    audit_db.execute(delete(AuditRow))
    audit_db.commit()
    entries = records(caplog, "database.write")
    attempts = [entry for entry in entries if entry["outcome"] == "attempted"]
    committed = [entry for entry in entries if entry["outcome"] == "committed"]
    expected_writes = 4
    assert len(attempts) == len(committed) == expected_writes
    assert {key for entry in attempts for key in entry["changes"]} == {
        "insert:audit_rows",
        "update:audit_rows",
        "update:AuditRow",
        "delete:audit_rows",
    }


@pytest.mark.parametrize("finish", ["commit", "rollback", "close"])
def test_savepoint_does_not_misreport_root_commit(
    audit_db: Session, caplog: pytest.LogCaptureFixture, finish: str
) -> None:
    audit_db.add(AuditRow(value="outer"))
    audit_db.flush()
    savepoint = audit_db.begin_nested()
    audit_db.add(AuditRow(value="inner"))
    audit_db.flush()
    getattr(savepoint, finish)()
    assert not [entry for entry in records(caplog, "database.write") if entry["outcome"] == "committed"]
    audit_db.commit()
    outcomes = [entry["outcome"] for entry in records(caplog, "database.write")]
    assert outcomes.count("committed") == (2 if finish == "commit" else 1)
    assert outcomes.count("rolled_back") == (0 if finish == "commit" else 1)


def test_uncommitted_getter_attempt_is_logged(audit_db: Session, caplog: pytest.LogCaptureFixture) -> None:
    @audit_operation
    def get_or_create(username: str) -> int:
        audit_db.add(AuditRow(value=username))
        audit_db.flush()
        return 0

    get_or_create("student")
    audit_db.close()
    assert [entry["outcome"] for entry in records(caplog, "storage.operation")] == ["attempted", "completed"]
    writes = records(caplog, "database.write")
    assert [entry["outcome"] for entry in writes] == ["attempted", "rolled_back"]
    assert all(entry["target"] == {"username": "student"} for entry in writes)


@pytest.mark.parametrize("failure", [False, True])
def test_previously_silent_namespace_update_is_audited(caplog: pytest.LogCaptureFixture, failure: bool) -> None:
    api = DataBaseApi.__new__(DataBaseApi)
    session = MagicMock()
    session.__enter__.return_value = session
    api._session_create = MagicMock(return_value=session)
    # These probes exercise the actual storage method; transaction behavior is
    # independently tested above using real SQLAlchemy sessions.
    api._get = MagicMock(return_value=SimpleNamespace(name="old", description=None))
    if failure:
        session.commit.side_effect = RuntimeError("private-error-details")
        with pytest.raises(RuntimeError):
            api.update_namespace(7, "new", "private-description")
    else:
        api.update_namespace(7, "new", "private-description")
    entries = records(caplog, "storage.operation")
    assert [entry["outcome"] for entry in entries] == ["attempted", "failed" if failure else "completed"]
    assert entries[-1]["target"] == {"namespace_id": 7}
    assert "private-description" not in caplog.text
    assert "private-error-details" not in caplog.text


@pytest.mark.parametrize("status", [200, 400, 403, 404, 409, 500])
def test_request_rejections_and_results_are_logged(caplog: pytest.LogCaptureFixture, status: int) -> None:
    app = Flask(__name__)
    install_request_audit(app)

    @app.post("/namespaces/<int:namespace_id>")
    def edit(namespace_id: int) -> Response:
        g.audit_actor = "teacher"
        g.audit_auth_method = "session"
        return Response(status=status)

    response = app.test_client().post("/namespaces/7?token=private-query", json={"comment": "private-body"})
    assert response.status_code == status
    entries = records(caplog, "http.request")
    assert entries[0]["outcome"] == "attempted"
    assert entries[-1]["outcome"] == (
        "failed"
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR
        else "rejected"
        if status >= HTTPStatus.BAD_REQUEST
        else "returned"
    )
    assert entries[-1]["target"] == {"namespace_id": 7}
    assert entries[-1]["actor"] == "teacher"
    assert entries[0]["request_id"] == entries[-1]["request_id"]
    assert "private-query" not in caplog.text
    assert "private-body" not in caplog.text


def test_csrf_rejection_is_audited(caplog: pytest.LogCaptureFixture) -> None:
    app = Flask(__name__)
    app.secret_key = "test-key"
    install_request_audit(app)
    CSRFProtect(app)
    app.add_url_rule("/write", view_func=lambda: "ok", methods=["POST"])
    assert app.test_client().post("/write").status_code == HTTPStatus.BAD_REQUEST
    assert [entry["outcome"] for entry in records(caplog, "http.request")] == ["attempted", "rejected"]


@pytest.mark.parametrize("propagate", [False, True])
def test_unhandled_error_is_logged_once(caplog: pytest.LogCaptureFixture, propagate: bool) -> None:
    app = Flask(__name__)
    app.config["PROPAGATE_EXCEPTIONS"] = propagate
    install_request_audit(app)

    @app.post("/fail")
    def fail() -> Response:
        raise RuntimeError("private-error-details")

    if propagate:
        with pytest.raises(RuntimeError):
            app.test_client().post("/fail")
    else:
        assert app.test_client().post("/fail").status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    entries = records(caplog, "http.request")
    assert [entry["outcome"] for entry in entries] == ["attempted", "failed"]
    assert "private-error-details" not in json.dumps(entries)


def test_token_actor_never_uses_browser_session(caplog: pytest.LogCaptureFixture) -> None:
    app = CustomFlask(__name__)
    app.secret_key = "test-key"
    app.storage_api = MagicMock()
    app.storage_api.get_course.return_value = SimpleNamespace(token="private-token")
    install_request_audit(app)

    @app.post("/api/<course_name>/write")
    @requires_token
    def write(course_name: str) -> Response:
        return Response(status=204)

    client = app.test_client()
    with client.session_transaction() as session:
        session["manytask"] = {"username": "browser-admin"}
    assert (
        client.post("/api/demo/write", headers={"Authorization": "Bearer private-token"}).status_code
        == HTTPStatus.NO_CONTENT
    )
    assert (
        client.post("/api/demo/write", headers={"Authorization": "Bearer wrong-token"}).status_code
        == HTTPStatus.FORBIDDEN
    )
    results = [entry for entry in records(caplog, "http.request") if entry["outcome"] != "attempted"]
    assert [entry["actor"] for entry in results] == ["course_token", "anonymous"]
    assert results[0]["request_id"] != results[1]["request_id"]
    assert "private-token" not in caplog.text
    assert "wrong-token" not in caplog.text


def test_background_context_survives_request_without_retaining_flask() -> None:
    app = Flask(__name__)
    observed = []
    with app.test_request_context("/write"):
        g.audit_actor = "teacher"
        g.audit_auth_method = "session"
        context = audit_context()

    def callback() -> None:
        assert not has_request_context()
        observed.append(audit_context())

    thread = Thread(target=run_with_audit_context, args=(context, callback))
    thread.start()
    thread.join()
    assert observed[0]["actor"] == "teacher"
    assert audit_context()["actor"] == "system"

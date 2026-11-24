import logging
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from manytask import models
from manytask.database import DataBaseApi


@pytest.fixture
def storage() -> tuple[DataBaseApi, MagicMock]:
    api = DataBaseApi.__new__(DataBaseApi)
    session = MagicMock()
    session.__enter__.return_value = session
    api._session_create = MagicMock(return_value=session)
    return api, session


@pytest.mark.parametrize("commit_fails", [False, True])
def test_namespace_change_logs_attempt_before_commit(
    storage: tuple[DataBaseApi, MagicMock], caplog: pytest.LogCaptureFixture, commit_fails: bool
) -> None:
    caplog.set_level(logging.INFO, logger="manytask.database")
    api, session = storage
    api._get = MagicMock(return_value=SimpleNamespace(name="old", description=None))
    if commit_fails:
        session.commit.side_effect = RuntimeError("commit failed")
        with pytest.raises(RuntimeError):
            api.update_namespace(7, "new", "private-description")
    else:
        api.update_namespace(7, "new", "private-description")
    assert "Updating namespace id=7" in caplog.text
    assert ("Updated namespace id=7" in caplog.text) is not commit_fails
    assert "private-description" not in caplog.text


def test_rejected_namespace_delete_is_logged(
    storage: tuple[DataBaseApi, MagicMock], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="manytask.database")
    api, session = storage
    session.query.return_value.filter_by.return_value.with_for_update.return_value.one.return_value = SimpleNamespace(
        name="expected"
    )
    with pytest.raises(ValueError, match="name does not match"):
        api.delete_namespace(7, "wrong")
    assert "Deleting namespace id=7" in caplog.text
    assert "Cannot delete namespace id=7: name does not match" in caplog.text
    session.commit.assert_not_called()


def test_initial_admin_binding_is_logged_despite_early_return(
    storage: tuple[DataBaseApi, MagicMock], caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="manytask.database")
    api, session = storage
    api._query_with_for_update = MagicMock(
        return_value=SimpleNamespace(username="bootstrap", is_instance_admin=True, rms_id="-1", auth_id=-1)
    )
    api.update_or_create_user("bootstrap", "Private", "Name", "provider-id", 7)
    assert "Binding initial admin identity for user=bootstrap" in caplog.text
    assert "Bound initial admin identity for user=bootstrap" in caplog.text
    assert "Private" not in caplog.text
    session.commit.assert_called_once()


@pytest.mark.parametrize("commit_fails", [False, True])
def test_course_membership_insert_attempt_is_visible_at_info(
    storage: tuple[DataBaseApi, MagicMock], caplog: pytest.LogCaptureFixture, commit_fails: bool
) -> None:
    caplog.set_level(logging.INFO, logger="manytask.database")
    api, session = storage
    api._get = MagicMock(return_value=SimpleNamespace(id=7))
    if commit_fails:
        session.commit.side_effect = RuntimeError("commit failed")
    with (
        patch.object(DataBaseApi, "_query_with_for_update", return_value=None),
        pytest.raises(RuntimeError, match="commit failed") if commit_fails else nullcontext(),
    ):
        api.sync_user_on_course("demo", "student", course_admin=False)
    assert "Ensuring course membership user=student course_id=7" in caplog.text
    assert "Creating new UserOnCourse" in caplog.text
    assert ("Synced course membership course=demo user=student" in caplog.text) is not commit_fails
    session.flush.assert_called_once()
    session.commit.assert_called_once()


def test_create_attempt_does_not_log_sensitive_values(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="manytask.database")
    session = MagicMock()
    session.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError):
        DataBaseApi._create(
            session, models.Course, name="demo", token="private-token", registration_secret="private-secret"
        )
    assert "Creating Course" in caplog.text
    assert "private-token" not in caplog.text
    assert "private-secret" not in caplog.text

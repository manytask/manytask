import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from manytask.main import CustomFlask, create_app
from tests.constants import (
    TEST_CACHE_DIR,
    TEST_COURSE_NAME,
    TEST_PUBLIC_REPO,
    TEST_STUDENTS_GROUP,
)


def _minimal_config():
    return {
        "version": 1,
        "ui": {"task_url_template": "https://example.org/$GROUP_NAME/$USER_NAME/$TASK_NAME"},
        "deadlines": {
            "timezone": "Europe/Moscow",
            "schedule": [
                {
                    "group": "week_1",
                    "start": "2025-01-01 10:00",
                    "end": "2025-01-15 23:59",
                    "tasks": [{"task": "task_1", "score": 10}],
                }
            ],
        },
    }


@pytest.fixture
def mock_env(monkeypatch, postgres_container):
    load_dotenv()

    class MockEnv:
        def __init__(self, monkeypatch):
            self.monkeypatch = monkeypatch

    mock_env = MockEnv(monkeypatch)

    # Set env var only if not already present
    def set_if_missing(key, value):
        if not os.getenv(key):
            monkeypatch.setenv(key, value)

    set_if_missing("FLASK_SECRET_KEY", "test_secret_key")
    set_if_missing("TESTING", "true")
    set_if_missing("MANYTASK_COURSE_TOKEN", "test_token")

    set_if_missing("RMS", "mock")

    set_if_missing("GITLAB_URL", "https://gitlab.com")
    set_if_missing("GITLAB_ADMIN_TOKEN", "test_admin_token")
    set_if_missing("GITLAB_CLIENT_ID", "test_client_id")
    set_if_missing("GITLAB_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("GITLAB_COURSE_GROUP", TEST_COURSE_NAME)
    monkeypatch.setenv("GITLAB_COURSE_PUBLIC_REPO", TEST_PUBLIC_REPO)
    monkeypatch.setenv("GITLAB_COURSE_STUDENTS_GROUP", TEST_STUDENTS_GROUP)
    set_if_missing("GITLAB_DEFAULT_BRANCH", "main")

    set_if_missing("REGISTRATION_SECRET", "test_reg_secret")
    set_if_missing("SHOW_ALLSCORES", "true")

    monkeypatch.setenv("CACHE_DIR", TEST_CACHE_DIR)
    monkeypatch.setenv("DATABASE_URL", postgres_container.get_connection_url())
    monkeypatch.setenv("INITIAL_INSTANCE_ADMIN", "instance_admin")
    monkeypatch.setenv("APPLY_MIGRATIONS", "true")

    os.makedirs(TEST_CACHE_DIR, exist_ok=True)

    return mock_env


def test_create_app_production_with_db(mock_env, monkeypatch):
    app = create_app()
    assert isinstance(app, CustomFlask)
    assert app.debug is False
    assert app.testing == os.getenv("TESTING")
    assert app.secret_key == os.getenv("FLASK_SECRET_KEY")

    assert "root" in app.blueprints
    assert "course" in app.blueprints
    assert "api" in app.blueprints

    assert hasattr(app, "oauth")
    assert "auth_provider" in app.oauth._clients

    assert hasattr(app, "storage_api")
    assert hasattr(app, "rms_api")
    assert hasattr(app, "auth_api")


def test_create_app_debug(mock_env):
    app = create_app(debug=True)
    assert isinstance(app, CustomFlask)
    assert app.debug is True
    assert app.testing == os.getenv("TESTING")


def test_create_app_missing_secret_key(mock_env):
    os.environ.pop("FLASK_SECRET_KEY", None)
    with pytest.raises(EnvironmentError):
        create_app()


def test_store_config_schedules_reconcile_when_pending():
    app = CustomFlask(__name__)
    app.storage_api = MagicMock()
    app.storage_api.rms_settings_reconcile_needed.return_value = True
    app.rms_api = MagicMock()

    with patch("manytask.main.schedule_rms_settings_reconcile") as mock_schedule:
        app.store_config(TEST_COURSE_NAME, _minimal_config())

    app.storage_api.update_course.assert_called_once()
    app.storage_api.rms_settings_reconcile_needed.assert_called_once_with(TEST_COURSE_NAME)
    mock_schedule.assert_called_once_with(app.storage_api, app.rms_api, TEST_COURSE_NAME)


def test_store_config_skips_reconcile_when_not_pending():
    app = CustomFlask(__name__)
    app.storage_api = MagicMock()
    app.storage_api.rms_settings_reconcile_needed.return_value = False
    app.rms_api = MagicMock()

    with patch("manytask.main.schedule_rms_settings_reconcile") as mock_schedule:
        app.store_config(TEST_COURSE_NAME, _minimal_config())

    app.storage_api.update_course.assert_called_once()
    mock_schedule.assert_not_called()

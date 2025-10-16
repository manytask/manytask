import os

import pytest
from dotenv import load_dotenv

from manytask.main import CustomFlask, create_app
from tests.constants import (
    TEST_CACHE_DIR,
    TEST_COURSE_NAME,
    TEST_PUBLIC_REPO,
    TEST_STUDENTS_GROUP,
)


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
    assert "gitlab" in app.oauth._clients

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

import os
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

from manytask.config import ManytaskStorageType
from manytask.gdoc import GoogleDocApi
from manytask.main import CustomFlask, create_app

TEST_COURSE_NAME = "test_course"
TEST_STUDENTS_GROUP = "test_students"
TEST_PUBLIC_REPO = "test_public_repo"

TEST_CACHE_DIR = "/tmp/manytask_test_cache"
TEST_SOLUTIONS_DIR = "/tmp/manytask_test_solutions"


@pytest.fixture
def mock_gdoc():
    with patch("manytask.gdoc.GoogleDocApi") as mock:
        gdoc_instance = MagicMock(spec=GoogleDocApi)
        mock.return_value = gdoc_instance
        yield mock


@pytest.fixture
def mock_env(monkeypatch):
    load_dotenv()

    # Set env var only if not already present
    def set_if_missing(key, value):
        if not os.getenv(key):
            monkeypatch.setenv(key, value)

    set_if_missing("FLASK_SECRET_KEY", "test_secret_key")
    set_if_missing("TESTING", "true")
    set_if_missing("TESTER_TOKEN", "test_tester_token")

    set_if_missing("GITLAB_URL", "https://gitlab.com")
    set_if_missing("GITLAB_ADMIN_TOKEN", "test_admin_token")
    set_if_missing("GITLAB_CLIENT_ID", "test_client_id")
    set_if_missing("GITLAB_CLIENT_SECRET", "test_client_secret")
    monkeypatch.setenv("GITLAB_COURSE_GROUP", TEST_COURSE_NAME)
    monkeypatch.setenv("GITLAB_COURSE_PUBLIC_REPO", TEST_PUBLIC_REPO)
    monkeypatch.setenv("GITLAB_COURSE_STUDENTS_GROUP", TEST_STUDENTS_GROUP)
    set_if_missing("GITLAB_DEFAULT_BRANCH", "main")

    set_if_missing("GDOC_URL", "https://docs.google.com")
    set_if_missing("GDOC_ACCOUNT_CREDENTIALS_BASE64", "eyJ0ZXN0IjogInRlc3QifQ==")
    set_if_missing("GDOC_SPREADSHEET_ID", "test_spreadsheet")
    set_if_missing("GDOC_SCOREBOARD_SHEET", "0")

    set_if_missing("REGISTRATION_SECRET", "test_reg_secret")
    set_if_missing("SHOW_ALLSCORES", "true")

    monkeypatch.setenv("CACHE_DIR", TEST_CACHE_DIR)
    monkeypatch.setenv("SOLUTIONS_DIR", TEST_SOLUTIONS_DIR)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("STORAGE", ManytaskStorageType.DataBase.value)
    monkeypatch.setenv("UNIQUE_COURSE_NAME", "test_course")
    monkeypatch.setenv("CREATE_TABLES_IF_NOT_EXIST", "true")

    os.makedirs(TEST_CACHE_DIR, exist_ok=True)
    os.makedirs(TEST_SOLUTIONS_DIR, exist_ok=True)


@pytest.fixture
def mock_gitlab():
    with patch("gitlab.Gitlab") as mock:
        gitlab_instance = MagicMock()
        mock.return_value = gitlab_instance

        # Mock GitLab groups
        mock_course_group = MagicMock()
        mock_course_group.name = TEST_COURSE_NAME
        mock_course_group.full_name = TEST_COURSE_NAME

        mock_students_group = MagicMock()
        mock_students_group.name = TEST_STUDENTS_GROUP
        mock_students_group.full_name = TEST_STUDENTS_GROUP

        # Mock groups.list for search
        def mock_group_list_search(**kwargs):
            search = kwargs.get("search", "")
            if search == TEST_COURSE_NAME:
                return [mock_course_group]
            elif search == TEST_STUDENTS_GROUP:
                return [mock_students_group]
            return []

        gitlab_instance.groups.list.side_effect = mock_group_list_search

        # Mock GitLab projects
        mock_project_list = MagicMock()
        mock_project_list.name = TEST_PUBLIC_REPO
        mock_project_list.path = TEST_PUBLIC_REPO
        mock_project_list.path_with_namespace = TEST_PUBLIC_REPO

        # Mock projects.list for search
        def mock_project_list_search(**kwargs):
            search = kwargs.get("search", "")
            if search in [TEST_PUBLIC_REPO, f"{TEST_COURSE_NAME}/{TEST_PUBLIC_REPO}"]:
                return [mock_project_list]
            return []

        gitlab_instance.projects.list.side_effect = mock_project_list_search

        yield mock


def test_create_app_production_with_gsheets(mock_env, mock_gitlab, mock_gdoc, monkeypatch):
    monkeypatch.setenv("STORAGE", ManytaskStorageType.GoogleSheets.value)
    app = create_app()
    assert isinstance(app, CustomFlask)
    assert app.debug is False
    assert app.testing == os.getenv("TESTING")
    assert app.secret_key == os.getenv("FLASK_SECRET_KEY")

    assert hasattr(app.course, "storage_api")

    assert "web" in app.blueprints
    assert "api" in app.blueprints

    assert hasattr(app, "oauth")
    assert "gitlab" in app.oauth._clients

    assert hasattr(app, "course")
    assert hasattr(app.course, "viewer_api")
    assert hasattr(app.course, "storage_api")
    assert hasattr(app.course, "gitlab_api")
    assert hasattr(app.course, "solutions_api")


def test_create_app_production_with_db(mock_env, mock_gitlab, mock_gdoc, monkeypatch):
    monkeypatch.setenv("STORAGE", ManytaskStorageType.DataBase.value)
    app = create_app()
    assert isinstance(app, CustomFlask)
    assert app.debug is False
    assert app.testing == os.getenv("TESTING")
    assert app.secret_key == os.getenv("FLASK_SECRET_KEY")

    assert hasattr(app.course, "storage_api")

    assert "web" in app.blueprints
    assert "api" in app.blueprints

    assert hasattr(app, "oauth")
    assert "gitlab" in app.oauth._clients

    assert hasattr(app, "course")
    assert hasattr(app.course, "viewer_api")
    assert hasattr(app.course, "storage_api")
    assert hasattr(app.course, "gitlab_api")
    assert hasattr(app.course, "solutions_api")


def test_create_app_production_with_something_else(mock_env, mock_gitlab, mock_gdoc, monkeypatch):
    monkeypatch.setenv("STORAGE", "something_else")
    with pytest.raises(Exception):
        create_app()


def test_create_app_debug(mock_env, mock_gitlab, mock_gdoc):
    app = create_app(debug=True)
    assert isinstance(app, CustomFlask)
    assert app.debug is True
    assert app.testing == os.getenv("TESTING")


def test_create_app_missing_secret_key(mock_gitlab, mock_gdoc):
    os.environ.pop("FLASK_SECRET_KEY", None)
    with pytest.raises(KeyError):
        create_app()

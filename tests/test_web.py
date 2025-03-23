import os
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from authlib.integrations.base_client import OAuthError
from flask import Flask, url_for
from pydantic import AnyUrl

from manytask.abstract import StoredUser
from manytask.config import ManytaskConfig, ManytaskSettingsConfig, ManytaskUiConfig
from manytask.database import TaskDisabledError
from manytask.glab import Student
from manytask.web import bp as web_bp
from manytask.web import get_allscores_url

TEST_USERNAME = "test_user"
TEST_SECRET = "test_secret"
TEST_KEY = "test_key"
TEST_TOKEN = "test_token"
TEST_COURSE_NAME = "Test Course"
GITLAB_BASE_URL = "https://gitlab.com"
TEST_VERSION = 1.5
TEST_USER_ID = 123
TEST_REPO = "test_repo"
INVALID_TASK_NAME = "invalid_task"
TASK_NAME_WITH_DISABLED_TASK_OR_GROUP = "disabled_task"


@pytest.fixture
def app():
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = "test_key"
    app.register_blueprint(web_bp)
    return app


@pytest.fixture
def mock_gitlab_api():
    class MockGitlabApi:
        def __init__(self):
            self.course_admin = False
            self.base_url = GITLAB_BASE_URL

        @staticmethod
        def get_url_for_repo(username, course_students_group):
            return f"{GITLAB_BASE_URL}/{username}/repo"

        @staticmethod
        def get_url_for_task_base(course_public_repo, default_branch):
            return f"{GITLAB_BASE_URL}/{course_public_repo}/blob/{default_branch}"

        @staticmethod
        def register_new_user(user):
            if user.username == TEST_USERNAME:
                return True
            raise Exception("Registration failed")

        @staticmethod
        def get_student(user_id, course_group, course_students_group):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        def get_authenticated_student(self, gitlab_access_token, course_group, course_students_group):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=self.course_admin)

        @staticmethod
        def check_project_exists(student, course_students_group):
            return True

        @staticmethod
        def _parse_user_to_student(user: dict[str, Any], course_group, course_students_group):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

    return MockGitlabApi()


@pytest.fixture
def mock_storage_api():  # noqa: C901
    class MockStorageApi:
        def __init__(self):
            self.stored_user = StoredUser(username=TEST_USERNAME, course_admin=False)
            self.course_name = TEST_COURSE_NAME

        @staticmethod
        def get_scores_update_timestamp():
            return datetime.now(tz=ZoneInfo("UTC"))

        @staticmethod
        def get_scores(_username):
            return {"task1": 100, "task2": 90}

        @staticmethod
        def get_all_scores():
            return {TEST_USERNAME: {"task1": 100, "task2": 90}}

        @staticmethod
        def get_stats():
            return {"task1": {"mean": 95}, "task2": {"mean": 85}}

        @staticmethod
        def get_bonus_score(_username):
            return 10

        def sync_stored_user(self, student):
            if student.course_admin:
                self.stored_user.course_admin = True

        @staticmethod
        def get_groups(*_args, **_kwargs):
            return []

        @staticmethod
        def find_task(task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            if task_name == TASK_NAME_WITH_DISABLED_TASK_OR_GROUP:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            return None, None

        @staticmethod
        def get_now_with_timezone():
            return datetime.now(tz=ZoneInfo("UTC"))

        def get_stored_user(self, _student):
            return self.stored_user

        @staticmethod
        def update_cached_scores():
            pass

        @staticmethod
        def check_user_on_course(*a, **k):
            return True

        def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool:
            self.stored_user.course_admin = (
                student.course_admin
                if self.stored_user.course_admin != student.course_admin and student.course_admin
                else self.stored_user.course_admin
            )
            return self.stored_user.course_admin

        @property
        def max_score_started(self):
            return 100

    return MockStorageApi()


@pytest.fixture
def mock_viewer_api():
    class MockViewerApi:
        @staticmethod
        def get_scoreboard_url():
            return "https://docs.google.com/spreadsheets"

    return MockViewerApi()


@pytest.fixture
def mock_solutions_api():
    class MockSolutionsApi:
        def store_task_from_folder(self, task_name, username, folder_path):
            pass

    return MockSolutionsApi()


@pytest.fixture
def mock_course(mock_gitlab_api, mock_storage_api, mock_viewer_api, mock_solutions_api):
    class MockCourse:
        def __init__(self):
            self.name = TEST_COURSE_NAME
            self.config = ManytaskConfig(
                version=1,
                settings=ManytaskSettingsConfig(
                    course_name=TEST_COURSE_NAME,
                    gitlab_base_url=AnyUrl(GITLAB_BASE_URL),
                    public_repo="test/repo",
                    students_group="test/students",
                ),
                ui=ManytaskUiConfig(task_url_template=f"{GITLAB_BASE_URL}/test/$GROUP_NAME/$TASK_NAME", links={}),
            )
            self.show_allscores = True
            self.manytask_version = "1.0.0"
            self.favicon = "test_favicon"
            self.registration_secret = TEST_SECRET
            self.debug = False
            self.storage_api = mock_storage_api
            self.viewer_api = mock_viewer_api
            self.gitlab_api = mock_gitlab_api
            self.solutions_api = mock_solutions_api
            self.gitlab_course_group = "test_group"
            self.gitlab_course_public_repo = "public_2025_spring"
            self.gitlab_course_students_group = "students_2025_spring"
            self.gitlab_default_branch = "main"

    return MockCourse()


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    monkeypatch.setenv("MANYTASK_COURSE_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("REGISTRATION_SECRET", TEST_SECRET)
    monkeypatch.setenv("FLASK_SECRET_KEY", TEST_KEY)
    monkeypatch.setenv("TESTING", "true")
    yield


def test_course_page_not_ready(app, mock_course):
    mock_course.config = None
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get("/")
        assert response.status_code == HTTPStatus.FOUND
        assert response.headers["Location"] == "/not_ready"


def test_course_page_invalid_session(app, mock_course, mock_gitlab_oauth):
    with app.test_request_context():
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get("/")
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/login"


def test_course_page_only_with_valid_session(app, mock_course, mock_gitlab_oauth):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(mock_course.storage_api, "check_user_on_course") as mock_check_user_on_course,
        ):
            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "access_token": TEST_TOKEN,
                }
            app.course = mock_course
            app.oauth = mock_gitlab_oauth
            mock_check_user_on_course.return_value = False
            response = client.get("/")
            assert response.status_code == HTTPStatus.OK
            assert b"Secret Code" in response.data


def test_signup_get(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get("/signup")
        assert response.status_code == HTTPStatus.OK


def test_signup_post_invalid_secret(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().post(
            "/signup",
            data={
                "username": TEST_USERNAME,
                "firstname": "Test",
                "lastname": "User",
                "email": "test@example.com",
                "password": "password123",
                "password2": "password123",
                "secret": "wrong_secret",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert b"Invalid registration secret" in response.data


def test_signup_post_password_mismatch(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().post(
            "/signup",
            data={
                "username": TEST_USERNAME,
                "firstname": "Test",
                "lastname": "User",
                "email": "test@example.com",
                "password": "password123",
                "password2": "password456",
                "secret": mock_course.registration_secret,
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert b"Passwords don&#39;t match" in response.data


def test_logout(app):
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["gitlab"] = {"version": TEST_VERSION, "username": TEST_USERNAME}
            response = client.get("/logout")
            assert response.status_code == HTTPStatus.FOUND
            assert response.headers["Location"] == "/signup"
            with client.session_transaction() as sess:
                assert "gitlab" not in sess


def test_not_ready(app, mock_course):
    with app.test_request_context():
        app.course = mock_course
        response = app.test_client().get("/not_ready")
        assert response.status_code == HTTPStatus.FOUND


def test_get_allscores_url(app, mock_course):
    with app.test_request_context():
        test_url = "https://docs.google.com/spreadsheets"

        class viewer_api_gsheets:
            @staticmethod
            def get_scoreboard_url():
                return test_url

        class viewer_api_db:
            @staticmethod
            def get_scoreboard_url():
                return ""

        assert get_allscores_url(viewer_api_gsheets) == test_url
        assert get_allscores_url(viewer_api_db) == url_for("web.show_database")


def check_admin_in_data(response, check_true):
    assert response.status_code == HTTPStatus.OK
    if check_true:
        assert b'class="admin-label' in response.data
    else:
        assert b'class="admin-label' not in response.data


def check_admin_status_code(response, check_true):
    if check_true:
        assert response.status_code != HTTPStatus.FORBIDDEN
    else:
        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    "path_and_func",
    [["/", check_admin_in_data], ["/solutions", check_admin_status_code], ["/database", check_admin_in_data]],
)
@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("get_param_admin", ["true", "1", "yes", None, "false", "0", "no", "random_value"])
def test_course_page_user_sync(app, mock_gitlab_oauth, mock_course, path_and_func, debug, get_param_admin):
    path, check_func = path_and_func

    if get_param_admin is not None:
        path += f"?admin={get_param_admin}"

    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "access_token": TEST_TOKEN,
                }
                sess["course"] = {
                    "secret": TEST_SECRET,
                }
            app.course = mock_course
            app.oauth = mock_gitlab_oauth
            app.debug = debug

            # not admin in gitlab, not admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, False)

            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": True,
                    "access_token": TEST_TOKEN,
                }
                sess["course"] = {
                    "secret": TEST_SECRET,
                }
            mock_course.gitlab_api.course_admin = True

            # admin in gitlab, not admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)

            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "access_token": TEST_TOKEN,
                }
                sess["course"] = {
                    "secret": TEST_SECRET,
                }
            mock_course.gitlab_api.course_admin = False

            app.course.storage_api.stored_user.course_admin = True

            # not admin in gitlab, admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)

            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "repo": TEST_REPO,
                    "course_admin": False,
                    "access_token": TEST_TOKEN,
                }
                sess["course"] = {
                    "secret": TEST_SECRET,
                }

            # admin in gitlab, admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)


def test_login_sync(app, mock_course, mock_gitlab_oauth):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(mock_course.gitlab_api, "check_project_exists") as mock_check_project_exists,
            patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        ):
            app.course = mock_course
            app.oauth = mock_gitlab_oauth
            mock_check_project_exists.return_value = True
            mock_authorize_access_token.return_value = {
                "access_token": "test_token",
                "refresh_token": "test_token",
            }
            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": 1.5,
                    "username": "test_user",
                    "user_id": 123,
                    "repo": "test_repo",
                    "course_admin": False,
                    "access_token": TEST_TOKEN,
                }
                sess.permanent = True

            assert not app.course.storage_api.stored_user.course_admin

            # not admin in gitlab so stored value shouldn't change
            client.post("/login")

            with client.session_transaction() as sess:
                assert "gitlab" in sess
                assert not sess["gitlab"]["course_admin"]

            assert not app.course.storage_api.stored_user.course_admin

            app.course.gitlab_api.course_admin = True

            # admin in gitlab so stored value should change
            client.post("/login")

            with client.session_transaction() as sess:
                assert "gitlab" in sess
                assert sess["gitlab"]["course_admin"]

            assert app.course.storage_api.stored_user.course_admin

            app.course.gitlab_api.course_admin = False

            # not admin in gitlab but also stored that admin
            client.post("/login")

            with client.session_transaction() as sess:
                assert "gitlab" in sess
                assert not sess["gitlab"]["course_admin"]

            assert app.course.storage_api.stored_user.course_admin


def test_signup_post_success(app, mock_course, mock_gitlab_oauth):
    data = {
        "username": TEST_USERNAME,
        "firstname": "Test",
        "lastname": "User",
        "email": "test@example.com",
        "password": "password",
        "password2": "password",
        "secret": mock_course.registration_secret,
    }
    with (
        patch.object(mock_course.gitlab_api, "register_new_user") as mock_register_new_user,
        patch.object(mock_course.storage_api, "sync_stored_user") as mock_sync_stored_user,
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.gitlab_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        app.test_request_context(),
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_student.return_value = Student(
            id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=False
        )
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }

        response = app.test_client().post(url_for("web.signup"), data=data)
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("web.login")

        mock_register_new_user.assert_called_once()
        args, _ = mock_register_new_user.call_args
        assert args[0].username == TEST_USERNAME
        assert args[0].firstname == "Test"
        assert args[0].lastname == "User"
        assert args[0].email == "test@example.com"
        assert args[0].password == "password"

        mock_sync_stored_user.assert_called_once()
        args, _ = mock_sync_stored_user.call_args
        assert isinstance(args[0], Student)
        assert args[0].username == TEST_USERNAME


def test_login_get_redirect_to_gitlab(app, mock_course, mock_gitlab_oauth):
    with app.test_request_context():
        app.course = mock_course
        app.oauth = mock_gitlab_oauth

        with (
            patch.object(mock_gitlab_oauth.gitlab, "authorize_redirect") as mock_authorize_redirect,
            app.test_request_context(),
        ):
            app.test_client().get(url_for("web.login"))
            mock_authorize_redirect.assert_called_once()
            args, _ = mock_authorize_redirect.call_args
            assert args[0] == url_for("web.login", _external=True)


def test_login_get_with_code(app, mock_course, mock_gitlab_oauth):
    with (
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.gitlab_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        app.test_request_context(),
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_student.return_value = Student(
            id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=False
        )
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }

        response = app.test_client().get(url_for("web.login"), query_string={"code": "test_code"})

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("web.login")

        mock_authorize_access_token.assert_called_once()

        mock_get_authenticated_student.assert_called_once()
        args, _ = mock_get_authenticated_student.call_args
        assert args[0] == "test_token"


def test_login_oauth_error(app, mock_gitlab_oauth, mock_course):
    with (
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token", side_effect=OAuthError("OAuth error")),
        app.test_request_context(),
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(url_for("web.login"), query_string={"code": "test_code"})
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("web.login")


@pytest.mark.parametrize("task_name", [INVALID_TASK_NAME, TASK_NAME_WITH_DISABLED_TASK_OR_GROUP])
def test_solutions_invalid_or_disabled_task(app, mock_gitlab_oauth, mock_course, task_name):
    with app.test_request_context():
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        app.debug = True  # course_admin = True

        data = {"task": task_name}

        response = app.test_client().get(url_for("web.get_solutions"), query_string=data)

        assert response.status_code == HTTPStatus.NOT_FOUND

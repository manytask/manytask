import os
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from authlib.integrations.base_client import OAuthError
from flask import Flask, url_for

from manytask.abstract import StoredUser
from manytask.api import bp as api_bp
from manytask.database import TaskDisabledError
from manytask.glab import Student, User
from manytask.web import course_bp, root_bp

TEST_USERNAME = "test_user"
TEST_STUDENT_NAME = "User Name"
TEST_STUDENT_REPO = "students/test_user"
TEST_SECRET = "test_secret"
TEST_KEY = "test_key"
TEST_TOKEN = "test_token"
TEST_COURSE_NAME = "Test_Course"
GITLAB_BASE_URL = "https://gitlab.com"
TEST_VERSION = 1.5
TEST_USER_ID = 123
TEST_REPO = "test_repo"
INVALID_TASK_NAME = "invalid_task"
TASK_NAME_WITH_DISABLED_TASK_OR_GROUP = "disabled_task"


@pytest.fixture
def app(mock_gitlab_api, mock_storage_api):
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.course_name = TEST_COURSE_NAME
    app.secret_key = "test_key"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    app.gitlab_api = mock_gitlab_api
    app.storage_api = mock_storage_api
    app.manytask_version = "1.0.0"
    app.favicon = "test_favicon"
    return app


@pytest.fixture
def mock_gitlab_api():
    class MockGitlabApi:
        def __init__(self):
            self.course_admin = False
            self.base_url = GITLAB_BASE_URL

        @staticmethod
        def get_url_for_repo(username: str, course_students_group: str):
            return f"{GITLAB_BASE_URL}/{username}/repo"

        @staticmethod
        def get_url_for_task_base(course_public_repo: str, default_branch: str):
            return f"{GITLAB_BASE_URL}/{course_public_repo}/blob/{default_branch}"

        @staticmethod
        def register_new_user(user: User):
            if user.username == TEST_USERNAME:
                return True
            raise Exception("Registration failed")

        @staticmethod
        def get_student(user_id: int):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        def get_student_by_username(self, username: str) -> Student:
            return Student(
                id=1,
                username=username,
                name=TEST_STUDENT_NAME,
            )

        def get_authenticated_student(self, gitlab_access_token: str):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        @staticmethod
        def check_project_exists(student: Student, course_students_group: str):
            return True

        @staticmethod
        def _parse_user_to_student(user: dict[str, Any]):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        def check_is_course_admin(self, _user_id, _course_group):
            return self.course_admin

    return MockGitlabApi()


@pytest.fixture
def mock_storage_api(mock_course):  # noqa: C901
    class MockStorageApi:
        def __init__(self):
            self.stored_user = StoredUser(username=TEST_USERNAME, course_admin=False)
            self.course_name = TEST_COURSE_NAME

        @staticmethod
        def get_scores_update_timestamp(_course_name):
            return datetime.now(tz=ZoneInfo("UTC"))

        @staticmethod
        def get_scores(_course_name, _username):
            return {"task1": 100, "task2": 90}

        @staticmethod
        def get_all_scores(_course_name):
            return {TEST_USERNAME: {"task1": 100, "task2": 90}}

        @staticmethod
        def get_stats(_course_name):
            return {"task1": {"mean": 95}, "task2": {"mean": 85}}

        @staticmethod
        def get_bonus_score(_course_name, _username):
            return 10

        def sync_stored_user(self, _course_name, student, repo_name, course_admin):
            self.stored_user.course_admin = self.stored_user.course_admin or course_admin

        @staticmethod
        def get_groups(*_args, **_kwargs):
            return []

        @staticmethod
        def get_course(_name):
            return mock_course

        @staticmethod
        def find_task(_course_name, task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            if task_name == TASK_NAME_WITH_DISABLED_TASK_OR_GROUP:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            return None, None

        @staticmethod
        def get_now_with_timezone(_course_name):
            return datetime.now(tz=ZoneInfo("UTC"))

        def get_stored_user(self, _course_name, _student):
            return self.stored_user

        @staticmethod
        def update_cached_scores(_course_name):
            pass

        @staticmethod
        def check_user_on_course(*a, **k):
            return True

        def sync_and_get_admin_status(self, course_name: str, student: Student, course_admin: bool) -> bool:
            self.stored_user.course_admin = self.stored_user.course_admin or course_admin
            return self.stored_user.course_admin

        def max_score_started(self, _course_name):
            return 100

    return MockStorageApi()


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.course_name = TEST_COURSE_NAME
            self.is_ready = True
            self.show_allscores = True
            self.registration_secret = TEST_SECRET
            self.gitlab_course_group = "test_group"
            self.gitlab_course_public_repo = "public_2025_spring"
            self.gitlab_course_students_group = "students_2025_spring"
            self.gitlab_default_branch = "main"
            self.task_url_template = "test_task_url_template"
            self.links = {}

    return MockCourse()


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    monkeypatch.setenv("MANYTASK_COURSE_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("REGISTRATION_SECRET", TEST_SECRET)
    monkeypatch.setenv("FLASK_SECRET_KEY", TEST_KEY)
    monkeypatch.setenv("TESTING", "true")
    yield


def test_healthcheck(app):
    with app.test_request_context():
        response = app.test_client().get("/healthcheck")
        assert response.status_code == HTTPStatus.OK
        assert response.data == b"OK"


def test_course_page_not_ready(app, mock_gitlab_oauth):
    with (
        app.test_request_context(),
        patch.object(app.storage_api, "get_course") as mock_get_course,
    ):

        @dataclass
        class Course:
            is_ready = False

        mock_get_course.return_value = Course()
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(f"/{TEST_COURSE_NAME}/")
        assert response.status_code == HTTPStatus.FOUND
        assert response.headers["Location"] == f"/{TEST_COURSE_NAME}/not_ready"


def test_course_page_invalid_session(app, mock_gitlab_oauth):
    with app.test_request_context():
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(f"/{TEST_COURSE_NAME}/")
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/login"


def test_course_page_only_with_valid_session(app, mock_gitlab_oauth):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.storage_api, "check_user_on_course") as mock_check_user_on_course,
        ):
            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "version": TEST_VERSION,
                    "username": TEST_USERNAME,
                    "user_id": TEST_USER_ID,
                    "access_token": TEST_TOKEN,
                }
            app.oauth = mock_gitlab_oauth
            mock_check_user_on_course.return_value = False
            response = client.get(f"/{TEST_COURSE_NAME}/")
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == f"/{TEST_COURSE_NAME}/create_project"


def test_signup_get(app):
    with app.test_request_context():
        response = app.test_client().get(f"/{TEST_COURSE_NAME}/signup")
        assert response.status_code == HTTPStatus.OK


def test_signup_post_invalid_secret(app):
    with app.test_request_context():
        response = app.test_client().post(
            f"/{TEST_COURSE_NAME}/signup",
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
        response = app.test_client().post(
            f"/{TEST_COURSE_NAME}/signup",
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
            assert response.headers["Location"] == f"/{TEST_COURSE_NAME}/signup"
            with client.session_transaction() as sess:
                assert "gitlab" not in sess


def test_not_ready(app):
    with app.test_request_context():
        response = app.test_client().get(f"/{TEST_COURSE_NAME}/not_ready")
        assert response.status_code == HTTPStatus.FOUND


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
    [[f"/{TEST_COURSE_NAME}/", check_admin_in_data], [f"/{TEST_COURSE_NAME}/database", check_admin_in_data]],
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
                    "access_token": TEST_TOKEN,
                }

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
                    "access_token": TEST_TOKEN,
                }
            app.gitlab_api.course_admin = True

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
                    "access_token": TEST_TOKEN,
                }
            app.gitlab_api.course_admin = False

            app.storage_api.stored_user.course_admin = True

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
                    "access_token": TEST_TOKEN,
                }

            # admin in gitlab, admin in manytask
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)


def test_signup_post_success(app, mock_gitlab_oauth, mock_course):
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
        patch.object(app.gitlab_api, "register_new_user") as mock_register_new_user,
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(app.gitlab_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }

        response = app.test_client().post(url_for("course.signup", course_name=TEST_COURSE_NAME), data=data)
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.login")

        mock_register_new_user.assert_called_once()
        args, _ = mock_register_new_user.call_args
        assert args[0].username == TEST_USERNAME
        assert args[0].firstname == "Test"
        assert args[0].lastname == "User"
        assert args[0].email == "test@example.com"
        assert args[0].password == "password"


def test_login_get_redirect_to_gitlab(app, mock_gitlab_oauth):
    with app.test_request_context():
        app.oauth = mock_gitlab_oauth

        with (
            patch.object(mock_gitlab_oauth.gitlab, "authorize_redirect") as mock_authorize_redirect,
            app.test_request_context(),
        ):
            app.test_client().get(url_for("root.login"))
            mock_authorize_redirect.assert_called_once()
            args, _ = mock_authorize_redirect.call_args
            assert args[0] == url_for("root.login", _external=True)


def test_login_get_with_code(app, mock_gitlab_oauth):
    with (
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(app.gitlab_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }

        response = app.test_client().get(url_for("root.login"), query_string={"code": "test_code"})

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.login")

        mock_authorize_access_token.assert_called_once()

        mock_get_authenticated_student.assert_called_once()
        args, _ = mock_get_authenticated_student.call_args
        assert args[0] == "test_token"


def test_login_oauth_error(app, mock_gitlab_oauth):
    with (
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token", side_effect=OAuthError("OAuth error")),
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(url_for("root.login"), query_string={"code": "test_code"})
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.login")

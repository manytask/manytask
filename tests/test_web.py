import os
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from authlib.integrations.base_client import OAuthError
from bs4 import BeautifulSoup
from flask import Flask, url_for
from flask_wtf import CSRFProtect

from manytask.abstract import AuthenticatedUser, RmsUser, StoredUser
from manytask.api import bp as api_bp
from manytask.course import CourseStatus, ManytaskDeadlinesType
from manytask.database import TaskDisabledError
from manytask.web import admin_bp, course_bp, root_bp
from tests.constants import (
    GITLAB_BASE_URL,
    INVALID_TASK_NAME,
    TASK_NAME_WITH_DISABLED_TASK_OR_GROUP,
    TEST_COURSE_NAME,
    TEST_FIRST_NAME,
    TEST_LAST_NAME,
    TEST_NAME,
    TEST_RMS_ID,
    TEST_SECRET,
    TEST_SECRET_KEY,
    TEST_TOKEN,
    TEST_USER_ID,
    TEST_USERNAME,
    TEST_VERSION,
)


@pytest.fixture
def app(mock_rms_api, mock_auth_api, mock_storage_api):
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = "test_key"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp)
    app.rms_api = mock_rms_api
    app.auth_api = mock_auth_api
    app.storage_api = mock_storage_api
    app.manytask_version = "1.0.0"
    app.favicon = "test_favicon"
    return app


@pytest.fixture
def mock_rms_api():
    class MockRmsApi:
        def __init__(self):
            self.base_url = GITLAB_BASE_URL

        @staticmethod
        def get_url_for_repo(username: str, destination: str):
            return f"{GITLAB_BASE_URL}/{username}/repo"

        @staticmethod
        def get_url_for_task_base(public_repo: str, default_branch: str):
            return f"{GITLAB_BASE_URL}/{public_repo}/blob/{default_branch}"

        @staticmethod
        def register_new_user(username: str, firstname: str, lastname: str, email: str, password: str) -> RmsUser:
            if username == TEST_USERNAME:
                return RmsUser(id=TEST_USER_ID, username=username, name=f"{firstname} {lastname}")
            raise Exception("Registration failed")

        @staticmethod
        def get_rms_user_by_id(user_id: int):
            return RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name=TEST_NAME)

        def check_user_authenticated_in_rms(self, oauth, oauth_access_token, oauth_refresh_token):
            return True

        def get_rms_user_by_username(self, username: str) -> RmsUser:
            return RmsUser(
                id=1,
                username=username,
                name=TEST_NAME,
            )

        def get_authenticated_rms_user(self, gitlab_access_token: str, name=TEST_NAME):
            return RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name=TEST_NAME)

        @staticmethod
        def check_project_exists(project_name: str, destination: str):
            return True

        @staticmethod
        def _construct_rms_user(user: dict[str, Any]):
            return RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name=TEST_NAME)

    return MockRmsApi()


@pytest.fixture
def mock_auth_api():
    class MockAuthApi:
        def check_user_is_authenticated(
            self,
            oauth,
            oauth_access_token: str,
            oauth_refresh_token: str,
        ) -> bool:
            return True

        def get_authenticated_user(self, access_token):
            return AuthenticatedUser(
                id=TEST_USER_ID, username=TEST_USERNAME, first_name=TEST_FIRST_NAME, last_name=TEST_LAST_NAME
            )

    return MockAuthApi()


@pytest.fixture
def mock_storage_api(mock_course):  # noqa: C901
    class MockFinalGradeConfig:
        def evaluate(self, *_args, **_kwargs):
            return 5

    class MockStorageApi:
        def __init__(self):
            self.stored_user = StoredUser(
                username=TEST_USERNAME,
                first_name=TEST_FIRST_NAME,
                last_name=TEST_LAST_NAME,
                rms_id=TEST_RMS_ID,
                instance_admin=False,
            )
            self.course_name = TEST_COURSE_NAME
            self.course_admin = False

        @staticmethod
        def get_scores_update_timestamp(_course_name):
            return datetime.now(tz=ZoneInfo("UTC"))

        @staticmethod
        def get_all_courses_names_with_statuses():
            return [("test_course_names", CourseStatus.CREATED)]

        @staticmethod
        def get_user_courses_names_with_statuses(_username):
            return [("test_course_names", CourseStatus.CREATED)]

        @staticmethod
        def get_scores(_course_name, _username):
            return {"task1": 100, "task2": 90}

        @staticmethod
        def get_all_scores_with_names(_course_name):
            return {
                TEST_USERNAME: (
                    {"task1": 100, "task2": 90},
                    (TEST_FIRST_NAME, TEST_LAST_NAME),
                )
            }

        @staticmethod
        def get_stats(_course_name):
            return {"task1": {"mean": 95}, "task2": {"mean": 85}}

        @staticmethod
        def get_bonus_score(_course_name, _username):
            return 10

        def sync_user_on_course(
            self,
            course_name: str,
            username: str,
            course_admin: bool,
        ) -> None:
            self.stored_user.username = username
            self.course_admin = self.course_admin or self.stored_user.instance_admin

        @staticmethod
        def get_groups(*_args, **_kwargs):
            return []

        @staticmethod
        def get_grades(*_args, **_kwargs):
            return MockFinalGradeConfig()

        @staticmethod
        def get_course(_name):
            return mock_course

        @staticmethod
        def find_task(_course_name, task_name):
            if task_name == INVALID_TASK_NAME:
                raise KeyError("Task not found")
            if task_name == TASK_NAME_WITH_DISABLED_TASK_OR_GROUP:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            return None, None, None

        @staticmethod
        def get_now_with_timezone(_course_name):
            return datetime.now(tz=ZoneInfo("UTC"))

        def get_stored_user(self, _username):
            return self.stored_user

        def check_if_instance_admin(self, _username):
            return self.stored_user.instance_admin

        def check_if_course_admin(self, _course_name, _username):
            return self.course_admin

        @staticmethod
        def update_cached_scores(_course_name):
            pass

        @staticmethod
        def check_user_on_course(*a, **k):
            return True

        def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool:
            self.course_admin = self.course_admin or course_admin
            return self.course_admin

        def max_score_started(self, _course_name):
            return 100

        def create_user_if_not_exist(self, username: str, firstname: str, lastname: str, rms_id: int):
            pass

    return MockStorageApi()


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.course_name = TEST_COURSE_NAME
            self.status = CourseStatus.IN_PROGRESS
            self.show_allscores = True
            self.registration_secret = TEST_SECRET
            self.gitlab_course_group = "test_group"
            self.gitlab_course_public_repo = "public_2025_spring"
            self.gitlab_course_students_group = "students_2025_spring"
            self.gitlab_default_branch = "main"
            self.task_url_template = "test_task_url_template"
            self.links = {}
            self.deadlines_type = ManytaskDeadlinesType.HARD

    return MockCourse()


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    monkeypatch.setenv("MANYTASK_COURSE_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("REGISTRATION_SECRET", TEST_SECRET)
    monkeypatch.setenv("FLASK_SECRET_KEY", TEST_SECRET_KEY)
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
            status = CourseStatus.CREATED

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
        assert response.location == url_for("root.signup")


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
                    "refresh_token": TEST_TOKEN,
                }
            app.oauth = mock_gitlab_oauth
            mock_check_user_on_course.return_value = False
            response = client.get(f"/{TEST_COURSE_NAME}/")
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == f"/{TEST_COURSE_NAME}/create_project"


def test_signup_get(app):
    CSRFProtect(app)
    with app.test_request_context():
        response = app.test_client().get("/signup")
        assert response.status_code == HTTPStatus.OK


def test_signup_post_password_mismatch(app, mock_course):
    CSRFProtect(app)
    with app.test_client() as client:
        response = client.get("/signup")
        soup = BeautifulSoup(response.data, "html.parser")
        csrf_token = soup.find("input", {"name": "csrf_token"})["value"]

        response = client.post(
            "/signup",
            data={
                "csrf_token": csrf_token,
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
            assert response.headers["Location"] == "/"
            with client.session_transaction() as sess:
                assert "gitlab" not in sess


def test_not_ready(app):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.storage_api, "check_if_instance_admin") as mock_check_if_instance_admin,
        ):
            with client.session_transaction() as sess:
                sess["gitlab"] = {
                    "username": TEST_USERNAME,
                }
            mock_check_if_instance_admin.return_value = True
            response = client.get(f"/{TEST_COURSE_NAME}/not_ready")
            assert response.status_code == HTTPStatus.FOUND


def check_admin_in_data(response, check_true):
    assert response.status_code == HTTPStatus.OK
    if check_true:
        assert b'class="adm-badge' in response.data
    else:
        assert b'class="adm-badge' not in response.data


def check_admin_status_code(response, check_true):
    if check_true:
        assert response.status_code != HTTPStatus.FORBIDDEN
    else:
        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    "path_and_func",
    [
        [f"/{TEST_COURSE_NAME}/", check_admin_in_data],
        [f"/{TEST_COURSE_NAME}/database", check_admin_in_data],
    ],
)
@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("get_param_admin", ["true", "1", "yes", None, "false", "0", "no", "random_value"])
def test_course_page_user_sync(app, mock_gitlab_oauth, mock_course, path_and_func, debug, get_param_admin):
    path, check_func = path_and_func
    CSRFProtect(app)

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
                    "refresh_token": TEST_TOKEN,
                }

            app.oauth = mock_gitlab_oauth
            app.debug = debug

            # not instance admin, not course admin
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
                    "refresh_token": TEST_TOKEN,
                }

            app.storage_api.course_admin = True

            # not instance admin, but course admin
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
                    "refresh_token": TEST_TOKEN,
                }
            app.storage_api.course_admin = False
            app.storage_api.stored_user.instance_admin = True

            # instance admin => course admin
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)


def test_signup_post_success(app, mock_gitlab_oauth, mock_storage_api, mock_course):
    CSRFProtect(app)
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
        patch.object(app.rms_api, "register_new_user") as mock_register_new_rms_user,
        patch.object(app.rms_api, "get_authenticated_rms_user") as mock_get_authenticated_rms_user,
        patch.object(app.rms_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        patch.object(mock_storage_api, "create_user_if_not_exist") as mock_register_new_mt_user,
        # app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_rms_user.return_value = RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name=TEST_NAME)
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }
        mock_register_new_rms_user.return_value = RmsUser(id=TEST_USER_ID, username=TEST_USERNAME, name="Test User")
        with app.test_client() as client:
            response = client.get("/signup")
            soup = BeautifulSoup(response.data, "html.parser")
            csrf_token = soup.find("input", {"name": "csrf_token"})["value"]
            data["csrf_token"] = csrf_token
            response = client.post(url_for("root.signup", course_name=TEST_COURSE_NAME), data=data)
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == url_for("root.login")

            mock_register_new_rms_user.assert_called_once_with(
                TEST_USERNAME,
                "Test",
                "User",
                "test@example.com",
                "password",
            )

            mock_register_new_mt_user.assert_called_once_with(TEST_USERNAME, "Test", "User", TEST_USER_ID)


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
            assert args[0] == url_for("root.login_finish", _external=True)


def test_login_finish_get_with_code(app, mock_gitlab_oauth):
    with (
        patch.object(app.auth_api, "get_authenticated_user") as mock_get_authenticated_user,
        patch.object(app.rms_api, "check_project_exists") as mock_check_project_exists,
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token") as mock_authorize_access_token,
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_user.return_value = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
        mock_check_project_exists.return_value = True
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }

        response = app.test_client().get(url_for("root.login_finish"), query_string={"code": "test_code"})

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.index")

        mock_authorize_access_token.assert_called_once()

        mock_get_authenticated_user.assert_called_once()
        args, _ = mock_get_authenticated_user.call_args
        assert args[0] == "test_token"


def test_login_oauth_error(app, mock_gitlab_oauth):
    with (
        patch.object(mock_gitlab_oauth.gitlab, "authorize_access_token", side_effect=OAuthError("OAuth error")),
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(url_for("root.login"), query_string={"code": "test_code"})
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.index")

import os
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from flask import Flask, request, session, url_for
from pydantic import AnyUrl

from manytask.abstract import StoredUser
from manytask.auth import requires_auth, requires_ready, set_oauth_session, valid_session
from manytask.config import ManytaskConfig, ManytaskSettingsConfig, ManytaskUiConfig
from manytask.glab import Student
from manytask.web import bp as web_bp

TEST_USERNAME = "test_user"
TEST_SECRET = "test_secret"
TEST_KEY = "test_key"
TEST_TOKEN = "test_token"
TEST_COURSE_NAME = "Test Course"
GITLAB_BASE_URL = "https://gitlab.com"
TEST_VERSION = 1.5
TEST_USER_ID = 123
TEST_REPO = "test_repo"


@pytest.fixture
def app():
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
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
        def get_student(_user_id, course_group, course_students_group):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        def get_authenticated_student(self, gitlab_access_token, course_group, course_students_group):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=self.course_admin)

        @staticmethod
        def check_project_exists(_student, course_students_group):
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

        def get_stored_user(self, _student):
            return self.stored_user

        def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool:
            self.stored_user.course_admin = (
                student.course_admin
                if self.stored_user.course_admin != student.course_admin and student.course_admin
                else self.stored_user.course_admin
            )
            return self.stored_user.course_admin

        def check_user_on_course(self, *a, **k):
            return True

        @staticmethod
        def update_cached_scores():
            pass

        @staticmethod
        def get_now_with_timezone():
            return datetime.now(tz=ZoneInfo("UTC"))

        @staticmethod
        def get_groups():
            return []

        @property
        def max_score_started(self):
            return 100  # Mock value for testing

    return MockStorageApi()


@pytest.fixture
def mock_solutions_api():
    class MockSolutionsApi:
        def store_task_from_folder(self, task_name, username, folder_path):
            pass

    return MockSolutionsApi()


@pytest.fixture
def mock_course(mock_gitlab_api, mock_storage_api, mock_solutions_api):
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
            self.gitlab_api = mock_gitlab_api
            self.solutions_api = mock_solutions_api
            self.gitlab_course_group = "test_group"
            self.gitlab_course_public_repo = "public_2025_spring"
            self.gitlab_course_students_group = "students_2025_spring"
            self.gitlab_default_branch = "main"

    return MockCourse()


def test_valid_session_with_valid_data(app):
    with app.test_request_context():
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "repo": "test_repo",
            "course_admin": False,
        }
        assert valid_session(session) is True


def test_valid_session_with_invalid_version(app):
    with app.test_request_context():
        session["gitlab"] = {
            "version": 1.0,
            "username": "test_user",
            "user_id": 123,
            "repo": "test_repo",
            "course_admin": False,
        }
        assert valid_session(session) is False


def test_valid_session_with_missing_data(app):
    # missing user_id
    with app.test_request_context():
        session["gitlab"] = {"version": 1.5, "username": "test_user", "repo": "test_repo", "course_admin": False}
        assert valid_session(session) is False


def test_valid_session_with_empty_session(app):
    with app.test_request_context():
        assert valid_session(session) is False


def test_requires_auth_in_debug_mode(app):
    @requires_auth
    def test_route():
        return "success"

    with app.test_request_context():
        app.config["DEBUG"] = True
        response = test_route()
        assert response == "success"


def test_requires_auth_with_valid_session_and_exist_on_course(app, mock_gitlab_oauth, mock_course):
    @requires_auth
    def test_route():
        return "success"

    with (
        app.test_request_context(),
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.storage_api, "check_user_on_course") as mock_check_user_on_course,
        patch.object(mock_course.storage_api, "sync_and_get_admin_status") as mock_user_on_course,
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        mock_check_user_on_course.return_value = True
        mock_get_authenticated_student.return_value = Student(
            id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=False
        )
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "repo": "test_repo",
            "course_admin": False,
            "access_token": TEST_TOKEN,
        }
        response = test_route()
        assert response == "success"
        mock_check_user_on_course.assert_called_once()
        mock_user_on_course.assert_called_once()


def test_requires_auth_with_valid_session_and_not_exist_on_course(app, mock_gitlab_oauth, mock_course):
    @requires_auth
    def test_route():
        return "success"

    with (
        app.test_request_context(),
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.storage_api, "check_user_on_course") as mock_check_user_on_course,
        patch.object(mock_course.storage_api, "sync_and_get_admin_status") as mock_user_on_course,
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        mock_check_user_on_course.return_value = True
        mock_get_authenticated_student.return_value = Student(
            id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=False
        )
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "repo": "test_repo",
            "course_admin": False,
            "access_token": TEST_TOKEN,
        }
        response = test_route()
        assert response == "success"
        mock_check_user_on_course.assert_called_once()
        mock_user_on_course.assert_called_once()


def test_requires_auth_with_invalid_session(app, mock_gitlab_oauth, mock_course):
    # Should redirect to signup
    @requires_auth
    def test_route():
        return "success"

    with (
        app.test_request_context(),
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.storage_api, "check_user_on_course") as mock_check_user_on_course,
    ):
        app.course = mock_course
        app.oauth = mock_gitlab_oauth
        mock_check_user_on_course.return_value = True
        mock_get_authenticated_student.return_value = Student(
            id=TEST_USER_ID, username=TEST_USERNAME, name="", course_admin=False
        )
        response = test_route()
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/login"


def test_requires_auth_callback_oauth(app, mock_gitlab_oauth, mock_course):
    # Should redirect to signup
    @requires_auth
    def test_route():
        return "success"

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

        request.args = {"code": "test_code"}
        response = test_route()
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("web.login")

        mock_authorize_access_token.assert_called_once()

        mock_get_authenticated_student.assert_called_once()
        args, _ = mock_get_authenticated_student.call_args
        assert args[0] == "test_token"


def test_requires_auth_callback_secret(app, mock_gitlab_oauth, mock_course):
    # Should redirect to signup
    @requires_auth
    def test_route():
        return "success"

    with (
        patch.object(mock_course.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(mock_course.storage_api, "sync_stored_user") as mock_sync_stored_user,
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
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "repo": "test_repo",
            "course_admin": False,
            "access_token": TEST_TOKEN,
        }

        request.form = {"secret": TEST_SECRET}
        response = test_route()
        assert response == "success"
        mock_sync_stored_user.assert_called_once()


def test_requires_ready_with_config(app):
    @requires_ready
    def test_route():
        return "success"

    class MockCourse:
        def __init__(self):
            self.config = {"test": "config"}

    with app.test_request_context():
        app.course = MockCourse()
        response = test_route()
        assert response == "success"


def test_requires_ready_without_config(app):
    # Should redirect to not_ready
    @requires_ready
    def test_route():
        return "success"

    class MockCourse:
        def __init__(self):
            self.config = None

    with app.test_request_context():
        app.course = MockCourse()
        response = test_route()
        assert response.status_code == HTTPStatus.FOUND


def test_set_oauth_session():
    tokens = {"access_token": "token", "refresh_token": "refresh_token"}
    student = Student(id=1, username="Test Name", name="Name", course_admin=True, repo="test_repo")
    result = set_oauth_session(student, tokens)
    assert result["access_token"] == tokens["access_token"]
    assert result["refresh_token"] == tokens["refresh_token"]
    assert result["username"] == student.username
    assert result["user_id"] == student.id
    assert result["course_admin"] == student.course_admin
    assert result["repo"] == student.repo


def test_set_oauth_session_only_student():
    student = Student(id=1, username="Test Name", name="Name", course_admin=True, repo="test_repo")
    result = set_oauth_session(student)
    assert "access_token" not in result
    assert "refresh_token" not in result
    assert result["username"] == student.username
    assert result["user_id"] == student.id
    assert result["course_admin"] == student.course_admin
    assert result["repo"] == student.repo

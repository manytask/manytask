import os
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from flask import Flask, Response, session, url_for
from werkzeug.exceptions import HTTPException

from manytask.abstract import StoredUser
from manytask.auth import requires_admin, requires_auth, requires_ready, set_oauth_session, valid_session
from manytask.glab import Student
from manytask.web import course_bp, root_bp

TEST_USERNAME = "test_user"
TEST_FIRST_NAME = "Ivan"
TEST_LAST_NAME = "Ivanov"
TEST_NAME = "Ivan Ivanov"
TEST_RMS_ID = 123
TEST_SECRET = "test_secret"
TEST_KEY = "test_key"
TEST_TOKEN = "test_token"
TEST_COURSE_NAME = "Test Course"
GITLAB_BASE_URL = "https://gitlab.com"
TEST_VERSION = 1.5
TEST_USER_ID = 123
TEST_REPO = "test_repo"


@pytest.fixture
def app(mock_gitlab_api, mock_storage_api):
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
    app.secret_key = "test_key"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
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
        def get_student(user_id: int):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        def get_authenticated_student(self, gitlab_access_token: str):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

        @staticmethod
        def check_project_exists(username: str, course_students_group: str):
            return True

        @staticmethod
        def _parse_user_to_student(user: dict[str, Any]):
            return Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")

    return MockGitlabApi()


@pytest.fixture
def mock_storage_api(mock_course):  # noqa: C901
    class MockStorageApi:
        def __init__(self):
            self.stored_user = StoredUser(
                username=TEST_USERNAME,
                first_name=TEST_FIRST_NAME,
                last_name=TEST_LAST_NAME,
                rms_id=TEST_RMS_ID,
                course_admin=False,
            )
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

        @staticmethod
        def get_course(_name):
            return mock_course

        def get_stored_user(self, _username):
            return self.stored_user

        def check_if_instance_admin(self, _username):
            return False

        def check_if_course_admin(self, _course_name, _username):
            return self.stored_user.course_admin

        def sync_and_get_admin_status(self, course_name: str, student: Student, course_admin: bool) -> bool:
            self.stored_user.course_admin = course_admin
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
def mock_course():
    class MockCourse:
        def __init__(self):
            self.course_name = TEST_COURSE_NAME
            self.is_ready = True
            self.show_allscores = True
            self.registration_secret = TEST_SECRET
            self.debug = False
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
        }
        assert valid_session(session) is True


def test_valid_session_with_invalid_version(app):
    with app.test_request_context():
        session["gitlab"] = {
            "version": 1.0,
            "username": "test_user",
            "user_id": 123,
        }
        assert valid_session(session) is False


def test_valid_session_with_missing_data(app):
    # missing user_id
    with app.test_request_context():
        session["gitlab"] = {"version": 1.5, "username": "test_user"}
        assert valid_session(session) is False


def test_valid_session_with_empty_session(app):
    with app.test_request_context():
        assert valid_session(session) is False


def test_requires_auth_in_debug_mode(app):
    @requires_auth
    def test_route(course_name: str):
        return "success"

    with app.test_request_context():
        app.config["DEBUG"] = True
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_auth_with_valid_session(app, mock_gitlab_oauth):
    @requires_auth
    def test_route(course_name: str):
        return "success"

    with (
        app.test_request_context(),
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "access_token": TEST_TOKEN,
        }
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_auth_with_invalid_session(app, mock_gitlab_oauth):
    # Should redirect to signup
    @requires_auth
    def test_route(course_name: str):
        return "success"

    with (
        app.test_request_context(),
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(app.storage_api, "check_user_on_course") as mock_check_user_on_course,
    ):
        app.oauth = mock_gitlab_oauth
        mock_check_user_on_course.return_value = True
        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.signup")


def test_requires_ready(app):
    @requires_ready
    def test_route(course_name: str):
        return "success"

    @dataclass
    class Course:
        is_ready = True

    with (
        app.test_request_context(),
        patch.object(app.storage_api, "get_course") as mock_get_course,
    ):
        mock_get_course.return_value = Course()
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_ready_but_not_ready(app):
    # Should redirect to not_ready
    @requires_ready
    def test_route(course_name: str):
        return "success"

    @dataclass
    class Course:
        is_ready = False

    with (
        app.test_request_context(),
        patch.object(app.storage_api, "get_course") as mock_get_course,
    ):
        mock_get_course.return_value = Course()

        with pytest.raises(HTTPException) as e:
            test_route(course_name=TEST_COURSE_NAME)
        assert isinstance(e.value.response, Response)
        assert e.value.response.status_code == HTTPStatus.FOUND
        assert e.value.response.location == url_for("course.not_ready", course_name=TEST_COURSE_NAME)


def test_set_oauth_session():
    tokens = {"access_token": "token", "refresh_token": "refresh_token"}
    student = Student(id=1, username="Test Name", name="Name")
    result = set_oauth_session(student, tokens)
    assert result["access_token"] == tokens["access_token"]
    assert result["refresh_token"] == tokens["refresh_token"]
    assert result["username"] == student.username
    assert result["user_id"] == student.id


def test_set_oauth_session_only_student():
    student = Student(id=1, username="Test Name", name="Name")
    result = set_oauth_session(student)
    assert "access_token" not in result
    assert "refresh_token" not in result
    assert result["username"] == student.username
    assert result["user_id"] == student.id


def test_requires_admin_in_debug_mode(app):
    @requires_admin
    def test_route(course_name: str):
        return "success"

    with app.test_request_context():
        app.config["DEBUG"] = True
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_admin_with_admin_rules(app, mock_gitlab_oauth):
    @requires_admin
    def test_route(course_name: str):
        return "success"

    with (
        app.test_request_context(),
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
        patch.object(app.storage_api, "check_if_instance_admin") as mock_check_if_instance_admin,
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        mock_check_if_instance_admin.return_value = True
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "access_token": TEST_TOKEN,
        }

        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_admin_with_no_admin_rules(app, mock_gitlab_oauth):
    @requires_admin
    def test_route(course_name: str):
        return "success"

    with (
        app.test_request_context(),
        patch.object(app.gitlab_api, "get_authenticated_student") as mock_get_authenticated_student,
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_student.return_value = Student(id=TEST_USER_ID, username=TEST_USERNAME, name="")
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "access_token": TEST_TOKEN,
        }

        with pytest.raises(HTTPException) as e:
            test_route(course_name=TEST_COURSE_NAME)

        assert e.value.code == HTTPStatus.FORBIDDEN

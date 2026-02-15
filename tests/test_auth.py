import os
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from flask import Flask, Response, session, url_for
from werkzeug.exceptions import HTTPException

from manytask.abstract import AuthenticatedUser, StoredUser
from manytask.auth import (
    requires_auth,
    requires_instance_admin,
    requires_ready,
    set_oauth_session,
    valid_client_profile_session,
    valid_gitlab_session,
)
from manytask.course import CourseStatus
from manytask.mock_auth import MockAuthApi
from manytask.web import course_bp, root_bp
from tests.constants import (
    TEST_COURSE_NAME,
    TEST_FIRST_NAME,
    TEST_LAST_NAME,
    TEST_RMS_ID,
    TEST_SECRET,
    TEST_TOKEN,
    TEST_USER_ID,
    TEST_USERNAME,
)


@pytest.fixture
def app(mock_storage_api):
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
    app.secret_key = "test_key"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.auth_api = MockAuthApi()
    app.storage_api = mock_storage_api
    app.manytask_version = "1.0.0"
    app.favicon = "test_favicon"
    return app


@pytest.fixture
def mock_storage_api(mock_course):  # noqa: C901
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

        def check_if_instance_admin(self, _username):
            return False

        def check_if_course_admin(self, _course_name, _username):
            return self.course_admin

        def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool:
            self.course_admin = course_admin
            return course_admin

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

        @staticmethod
        def get_namespace_admin_namespaces(_username):
            return []

        @staticmethod
        def get_courses_by_namespace_ids(_namespace_ids):
            return []

        @staticmethod
        def get_courses_where_course_admin(_username):
            return []

        @staticmethod
        def get_namespace_by_id(_namespace_id, _username):
            raise PermissionError("No access to namespace")

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
            self.namespace_id = None

    return MockCourse()


def test_valid_gitlab_session_with_valid_data(app):
    with app.test_request_context():
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
        }
        assert valid_gitlab_session(session) is True


def test_valid_gitlab_session_with_invalid_version(app):
    with app.test_request_context():
        session["gitlab"] = {
            "version": 1.0,
            "username": "test_user",
            "user_id": 123,
        }
        assert valid_gitlab_session(session) is False


def test_valid_gitlab_session_with_missing_data(app):
    # missing user_id
    with app.test_request_context():
        session["gitlab"] = {"version": 1.5, "username": "test_user"}
        assert valid_gitlab_session(session) is False


def test_valid_gitlab_session_with_empty_session(app):
    with app.test_request_context():
        assert valid_gitlab_session(session) is False


def test_valid_client_profile_session_with_valid_data(app):
    with app.test_request_context():
        session["profile"] = {
            "version": 1.0,
            "username": "test_user",
        }
        assert valid_client_profile_session(session) is True


def test_valid_client_profile_session_with_invalid_version(app):
    with app.test_request_context():
        session["profile"] = {
            "version": 0.5,
            "username": "test_user",
        }
        assert valid_client_profile_session(session) is False


def test_valid_client_profile_session_with_missing_data(app):
    with app.test_request_context():
        session["gitlab"] = {"username": "test_user"}
        assert valid_client_profile_session(session) is False


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
        patch.object(app.auth_api, "get_authenticated_user") as mock_get_authenticated_user,
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_user.return_value = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "access_token": TEST_TOKEN,
            "refresh_token": TEST_TOKEN,
        }
        session["profile"] = {
            "version": 1.0,
            "username": "test_user",
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
        patch.object(app.auth_api, "get_authenticated_user") as mock_get_authenticated_rms_user,
        patch.object(app.storage_api, "check_user_on_course") as mock_check_user_on_course,
    ):
        app.oauth = mock_gitlab_oauth
        mock_check_user_on_course.return_value = True
        mock_get_authenticated_rms_user.return_value = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.signup")


def test_requires_ready(app):
    @requires_ready
    def test_route(course_name: str):
        return "success"

    @dataclass
    class Course:
        status = CourseStatus.IN_PROGRESS

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
        status = CourseStatus.CREATED

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
    auth_user = AuthenticatedUser(id=1, username="Test Name")
    result = set_oauth_session(auth_user, tokens)
    assert result["access_token"] == tokens["access_token"]
    assert result["refresh_token"] == tokens["refresh_token"]
    assert result["username"] == auth_user.username
    assert result["user_id"] == auth_user.id


def test_set_oauth_session_only_student():
    auth_user = AuthenticatedUser(id=1, username="Test Name")
    result = set_oauth_session(auth_user)
    assert "access_token" not in result
    assert "refresh_token" not in result
    assert result["username"] == auth_user.username
    assert result["user_id"] == auth_user.id


def test_requires_admin_in_debug_mode(app):
    @requires_instance_admin
    def test_route(course_name: str):
        return "success"

    with app.test_request_context():
        app.config["DEBUG"] = True
        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_admin_with_admin_rules(app, mock_gitlab_oauth):
    @requires_instance_admin
    def test_route(course_name: str):
        return "success"

    with (
        app.test_request_context(),
        patch.object(app.auth_api, "get_authenticated_user") as mock_get_authenticated_user,
        patch.object(app.storage_api, "check_if_instance_admin") as mock_check_if_instance_admin,
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_user.return_value = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
        mock_check_if_instance_admin.return_value = True
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "access_token": TEST_TOKEN,
            "refresh_token": TEST_TOKEN,
        }
        session["profile"] = {
            "version": 1.0,
            "username": "test_user",
        }

        response = test_route(course_name=TEST_COURSE_NAME)
        assert response == "success"


def test_requires_admin_with_no_admin_rules(app, mock_gitlab_oauth):
    @requires_instance_admin
    def test_route(course_name: str):
        return "success"

    with (
        app.test_request_context(),
        patch.object(app.auth_api, "get_authenticated_user") as mock_get_authenticated_user,
    ):
        app.oauth = mock_gitlab_oauth
        mock_get_authenticated_user.return_value = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "access_token": TEST_TOKEN,
            "refresh_token": TEST_TOKEN,
        }
        session["profile"] = {
            "version": 1.0,
            "username": "test_user",
        }

        with pytest.raises(HTTPException) as e:
            test_route(course_name=TEST_COURSE_NAME)

        assert e.value.code == HTTPStatus.FORBIDDEN

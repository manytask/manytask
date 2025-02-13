from unittest.mock import MagicMock

import pytest
from flask import Flask, request, session

from manytask.auth import requires_auth, requires_ready, requires_secret, valid_session
from manytask.web import bp as web_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.secret_key = "test_key"
    app.register_blueprint(web_bp)
    return app


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


def test_requires_auth_with_valid_session(app):
    @requires_auth
    def test_route():
        return "success"

    with app.test_request_context():
        session["gitlab"] = {
            "version": 1.5,
            "username": "test_user",
            "user_id": 123,
            "repo": "test_repo",
            "course_admin": False,
        }
        response = test_route()
        assert response == "success"


def test_requires_auth_with_invalid_session(app):
    # Should redirect to signup
    @requires_auth
    def test_route():
        return "success"

    with app.test_request_context():
        response = test_route()
        assert response.status_code == 302


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
        assert response.status_code == 302


def test_requires_secret_with_valid_secret(app):
    # Should redirect to create_project
    @requires_secret()
    def test_route():
        return "success"

    with app.test_request_context():
        session["gitlab"] = {"oauth_access_token": "token"}
        app.course = MagicMock()
        app.course.registration_secret = "test_code"
        request.form = {"secret": "test_code"}
        app.course.gitlab_api.get_authenticated_student.return_value = None
        app.course.storage_api.check_user_on_course.return_value = False
        response = test_route()
        assert response.status_code == 302
        assert response.location == "/create_project?secret=test_code"

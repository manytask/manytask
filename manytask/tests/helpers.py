"""Shared test helpers to avoid copy-paste across test modules (issue #521)."""

from http import HTTPStatus
from unittest.mock import MagicMock

from flask import Flask, json

from manytask.abstract import RmsUser, StoredUser
from manytask.api import namespace_bp
from manytask.course import CourseStatus, ManytaskDeadlinesType
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.mock_rms import MockRmsApi
from manytask.models import User, UserOnNamespace
from manytask.web import root_bp
from tests.constants import (
    GITLAB_BASE_URL,
    TEST_AUTH_ID,
    TEST_CLIENT_PROFILE_SESSION_VERSION,
    TEST_COURSE_NAME,
    TEST_FIRST_NAME,
    TEST_GITLAB_SESSION_VERSION,
    TEST_LAST_NAME,
    TEST_MANYTASK_SESSION_VERSION,
    TEST_RMS_ID,
    TEST_SECRET_KEY,
    TEST_USER_ID,
    TEST_USERNAME,
)


def build_mock_session(username, *, user_auth_id, rms_id, user_id):
    """Build a Flask session dict (auth/rms/manytask) for a mock authenticated user."""
    return {
        "auth": {
            "username": username,
            "user_auth_id": user_auth_id,
            "version": TEST_GITLAB_SESSION_VERSION,
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        },
        "rms": {
            "username": username,
            "rms_id": rms_id,
            "version": TEST_CLIENT_PROFILE_SESSION_VERSION,
        },
        "manytask": {
            "username": username,
            "user_id": user_id,
            "version": TEST_MANYTASK_SESSION_VERSION,
        },
    }


def post_json(client, url, payload):
    """POST a JSON payload to the given URL."""
    return client.post(url, json=payload, content_type="application/json")


def assert_error_response(response, status):
    """Assert the response has the given status and an ``error`` key; return the parsed data."""
    assert response.status_code == status
    data = json.loads(response.data)
    assert "error" in data
    return data


def create_namespace(client, *, name, slug, description=None):
    """POST /api/namespaces, assert 201 Created and return the parsed namespace payload."""
    payload = {"name": name, "slug": slug}
    if description is not None:
        payload["description"] = description
    response = post_json(client, "/api/namespaces", payload)
    assert response.status_code == HTTPStatus.CREATED
    return json.loads(response.data)


def assert_not_json_rejected(client, url):
    """Assert that a non-JSON POST to ``url`` is rejected with 400 and a JSON error."""
    response = client.post(url, data="not json", content_type="text/plain")
    data = assert_error_response(response, HTTPStatus.BAD_REQUEST)
    assert "JSON" in data["error"]


def assert_slugs_rejected(client, url, slugs, build_payload):
    """Assert that each slug in ``slugs`` is rejected with 400 when POSTed via ``build_payload``."""
    for slug in slugs:
        response = post_json(client, url, build_payload(slug))
        assert response.status_code == HTTPStatus.BAD_REQUEST, f"Slug '{slug}' should be invalid"
        assert "error" in json.loads(response.data)


def assert_forbidden_admin_only(response):
    """Assert a 403 response whose error message mentions the Instance/Namespace Admin requirement."""
    data = assert_error_response(response, HTTPStatus.FORBIDDEN)
    assert "Instance Admin or Namespace Admin" in data["error"]


def make_user(username, first_name, last_name, rms_id, auth_id, *, is_instance_admin=False):
    """Construct a User ORM object with the common test defaults."""
    return User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        rms_id=rms_id,
        auth_id=auth_id,
        is_instance_admin=is_instance_admin,
    )


def assign_namespace_role(session, *, user_id, namespace_id, role, assigned_by_id):
    """Create, persist and return a UserOnNamespace role assignment."""
    user_on_namespace = UserOnNamespace(
        user_id=user_id,
        namespace_id=namespace_id,
        role=role,
        assigned_by_id=assigned_by_id,
    )
    session.add(user_on_namespace)
    session.commit()
    return user_on_namespace


def register_rms_user(app, user):
    """Register a User in the app's mock RMS so it can be resolved by rms_id."""
    app.rms_api.users[user.rms_id] = RmsUser(
        id=user.rms_id,
        username=user.username,
        name=f"{user.first_name} {user.last_name}",
    )


def make_flask_app(*blueprints, secret_key=TEST_SECRET_KEY):
    """Create a Flask app with the common test config and the given blueprints registered."""
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = secret_key
    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return app


def build_namespace_app(session, postgres_container, *, apply_migrations, auth_api):
    """Create a Flask app wired to a real DB for namespace/course API tests."""
    app = make_flask_app(root_bp, namespace_bp)

    def session_factory():
        return session

    db_config = DatabaseConfig(
        database_url=postgres_container.get_connection_url(),
        instance_admin_username="admin",
        apply_migrations=apply_migrations,
        session_factory=session_factory,
    )

    app.storage_api = DataBaseApi(db_config)
    app.rms_api = MockRmsApi(GITLAB_BASE_URL)
    app.auth_api = auth_api
    app.oauth = MagicMock()
    return app


def make_test_stored_user():
    """Construct the default StoredUser test double used by mock storage APIs."""
    return StoredUser(
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
        auth_id=TEST_AUTH_ID,
        user_id=TEST_USER_ID,
        instance_admin=False,
    )


class MockCourseBase:
    """Base test double for a course, holding the attributes shared across mock fixtures."""

    def __init__(self):
        self.course_name = TEST_COURSE_NAME
        self.status = CourseStatus.IN_PROGRESS
        self.show_allscores = True
        self.gitlab_default_branch = "main"
        self.deadlines_type = ManytaskDeadlinesType.HARD
        self.namespace_id = None


class MockStorageApiBase:
    """Base for MockStorageApi test doubles: shared init and namespace stubs."""

    def __init__(self):
        self.stored_user = make_test_stored_user()
        self.course_name = TEST_COURSE_NAME
        self.course_admin = False

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

"""Tests for course creation API endpoint."""

from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from dotenv import load_dotenv
from flask import Flask, json

from manytask.api import namespace_bp
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.mock_auth import MockAuthApi
from manytask.mock_rms import MockRmsApi
from manytask.models import Course, Namespace, User, UserOnNamespace, UserOnNamespaceRole
from manytask.web import root_bp
from tests.constants import GITLAB_BASE_URL, TEST_SECRET_KEY


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    load_dotenv()
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_key")
    monkeypatch.setenv("TESTING", "true")
    yield


@pytest.fixture
def app_with_db(engine, session, postgres_container):
    """Create Flask app with real database."""
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = TEST_SECRET_KEY
    app.register_blueprint(root_bp)
    app.register_blueprint(namespace_bp)

    def session_factory():
        return session

    db_config = DatabaseConfig(
        database_url=postgres_container.get_connection_url(),
        instance_admin_username="admin",
        instance_admin_rms_id=-1,
        apply_migrations=False,
        session_factory=session_factory,
    )

    app.storage_api = DataBaseApi(db_config)
    app.rms_api = MockRmsApi(GITLAB_BASE_URL)
    app.auth_api = MockAuthApi()
    app.oauth = MagicMock()

    # Create a regular user
    regular_user = User(
        username="regular_user",
        first_name="Regular",
        last_name="User",
        rms_id=2,
        is_instance_admin=False,
    )
    session.add(regular_user)

    # Create a namespace_admin user
    namespace_admin_user = User(
        username="namespace_admin_user",
        first_name="Namespace",
        last_name="Admin",
        rms_id=3,
        is_instance_admin=False,
    )
    session.add(namespace_admin_user)

    # Create a program_manager user
    pm_user = User(
        username="pm_user",
        first_name="PM",
        last_name="User",
        rms_id=4,
        is_instance_admin=False,
    )
    session.add(pm_user)

    session.commit()

    return app


@pytest.fixture
def client_with_db(app_with_db):
    """Flask test client with database."""
    with app_with_db.test_client() as client:
        yield client


@pytest.fixture
def mock_session_admin(session):
    """Mock session for admin user."""
    admin = session.query(User).filter_by(username="admin").first()
    return {
        "gitlab": {
            "username": "admin",
            "user_id": admin.rms_id,
            "version": 1.5,
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        },
        "profile": {
            "username": "admin",
            "version": 1.0,
        },
    }


@pytest.fixture
def mock_session_namespace_admin(session):
    """Mock session for namespace admin user."""
    user = session.query(User).filter_by(username="namespace_admin_user").first()
    return {
        "gitlab": {
            "username": "namespace_admin_user",
            "user_id": user.rms_id,
            "version": 1.5,
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        },
        "profile": {
            "username": "namespace_admin_user",
            "version": 1.0,
        },
    }


@pytest.fixture
def mock_session_pm(session):
    """Mock session for program manager user."""
    user = session.query(User).filter_by(username="pm_user").first()
    return {
        "gitlab": {
            "username": "pm_user",
            "user_id": user.rms_id,
            "version": 1.5,
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        },
        "profile": {
            "username": "pm_user",
            "version": 1.0,
        },
    }


@pytest.fixture
def mock_session_regular(session):
    """Mock session for regular user."""
    user = session.query(User).filter_by(username="regular_user").first()
    return {
        "gitlab": {
            "username": "regular_user",
            "user_id": user.rms_id,
            "version": 1.5,
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        },
        "profile": {
            "username": "regular_user",
            "version": 1.0,
        },
    }


@pytest.fixture
def test_namespace(session, client_with_db, mock_session_admin):
    """Create a test namespace."""
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "Test University",
            "slug": "test-university",
            "description": "Test namespace",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)
    return data


def test_create_course_as_instance_admin(client_with_db, session, mock_session_admin, test_namespace):
    """Test that Instance Admin can create a course in any namespace."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    namespace_id = test_namespace["id"]

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Algorithms 2024 Spring",
            "slug": "algorithms-2024-spring",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)

    assert data["course_name"] == "Algorithms 2024 Spring"
    assert data["slug"] == "algorithms-2024-spring"
    assert data["namespace_id"] == namespace_id
    assert "test-university/algorithms-2024-spring" in data["gitlab_course_group"]
    assert "public" in data["gitlab_course_public_repo"]
    assert "students" in data["gitlab_course_students_group"]
    assert data["status"] == "created"
    assert data["owners"] == []

    # Verify course was created in database
    course = session.query(Course).filter_by(name="Algorithms 2024 Spring").first()
    assert course is not None
    assert course.namespace_id == namespace_id


def test_create_course_as_namespace_admin_in_own_namespace(
    client_with_db, session, mock_session_admin, mock_session_namespace_admin, test_namespace
):
    """Test that Namespace Admin can create course in their own namespace."""

    # First add namespace_admin_user as namespace admin
    namespace_id = test_namespace["id"]
    admin_user = session.query(User).filter_by(username="admin").first()
    ns_admin_user = session.query(User).filter_by(username="namespace_admin_user").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=ns_admin_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.NAMESPACE_ADMIN,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Register user in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[ns_admin_user.rms_id] = RmsUser(
        id=ns_admin_user.rms_id,
        username=ns_admin_user.username,
        name=f"{ns_admin_user.first_name} {ns_admin_user.last_name}",
    )

    # Switch to namespace admin
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_namespace_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Machine Learning 2024",
            "slug": "ml-2024",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)
    assert data["course_name"] == "Machine Learning 2024"


def test_create_course_as_namespace_admin_in_other_namespace(
    client_with_db, session, mock_session_admin, mock_session_namespace_admin
):
    """Test that Namespace Admin cannot create course in another namespace."""

    # Create two namespaces
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response1 = client_with_db.post(
        "/api/namespaces",
        json={"name": "Namespace 1", "slug": "ns1"},
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.CREATED
    ns1_data = json.loads(response1.data)

    response2 = client_with_db.post(
        "/api/namespaces",
        json={"name": "Namespace 2", "slug": "ns2"},
        content_type="application/json",
    )
    assert response2.status_code == HTTPStatus.CREATED
    ns2_data = json.loads(response2.data)

    # Add user as namespace admin to ns1 only
    admin_user = session.query(User).filter_by(username="admin").first()
    ns_admin_user = session.query(User).filter_by(username="namespace_admin_user").first()
    ns1 = session.query(Namespace).filter_by(id=ns1_data["id"]).first()

    user_on_namespace = UserOnNamespace(
        user_id=ns_admin_user.id,
        namespace_id=ns1.id,
        role=UserOnNamespaceRole.NAMESPACE_ADMIN,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[ns_admin_user.rms_id] = RmsUser(
        id=ns_admin_user.rms_id,
        username=ns_admin_user.username,
        name=f"{ns_admin_user.first_name} {ns_admin_user.last_name}",
    )

    # Try to create course in ns2
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_namespace_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": ns2_data["id"],
            "course_name": "Unauthorized Course",
            "slug": "unauthorized",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_as_program_manager_forbidden(
    client_with_db, session, mock_session_admin, mock_session_pm, test_namespace
):
    """Test that Program Manager cannot create courses."""

    namespace_id = test_namespace["id"]

    # Add pm_user as program manager
    admin_user = session.query(User).filter_by(username="admin").first()
    pm_user = session.query(User).filter_by(username="pm_user").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=pm_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[pm_user.rms_id] = RmsUser(
        id=pm_user.rms_id, username=pm_user.username, name=f"{pm_user.first_name} {pm_user.last_name}"
    )

    # Try to create course
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_pm)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Forbidden Course",
            "slug": "forbidden",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert "Instance Admin or Namespace Admin" in data["error"]


def test_create_course_as_regular_user_forbidden(client_with_db, session, mock_session_regular, test_namespace):
    """Test that regular user without namespace role cannot create courses."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_regular)

    namespace_id = test_namespace["id"]

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Forbidden Course",
            "slug": "forbidden",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_with_valid_owners(client_with_db, session, mock_session_admin, test_namespace):
    """Test creating course with valid owners (namespace admins)."""

    namespace_id = test_namespace["id"]
    admin_user = session.query(User).filter_by(username="admin").first()
    ns_admin_user = session.query(User).filter_by(username="namespace_admin_user").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    # Add namespace_admin_user as namespace admin
    user_on_namespace = UserOnNamespace(
        user_id=ns_admin_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.NAMESPACE_ADMIN,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[ns_admin_user.rms_id] = RmsUser(
        id=ns_admin_user.rms_id,
        username=ns_admin_user.username,
        name=f"{ns_admin_user.first_name} {ns_admin_user.last_name}",
    )

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Course with Owners",
            "slug": "course-with-owners",
            "owners": [ns_admin_user.rms_id],
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)
    assert ns_admin_user.rms_id in data["owners"]

    # Verify owner has is_course_admin=True
    course = session.query(Course).filter_by(name="Course with Owners").first()
    from manytask.models import UserOnCourse

    user_on_course = session.query(UserOnCourse).filter_by(user_id=ns_admin_user.id, course_id=course.id).first()
    assert user_on_course is not None
    assert user_on_course.is_course_admin is True


def test_create_course_with_invalid_owners_not_in_namespace(
    client_with_db, session, mock_session_admin, test_namespace
):
    """Test creating course with owners that are not in the namespace."""

    namespace_id = test_namespace["id"]
    regular_user = session.query(User).filter_by(username="regular_user").first()

    # Register in mock RMS but don't add to namespace
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[regular_user.rms_id] = RmsUser(
        id=regular_user.rms_id,
        username=regular_user.username,
        name=f"{regular_user.first_name} {regular_user.last_name}",
    )

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Course with Invalid Owners",
            "slug": "course-invalid-owners",
            "owners": [regular_user.rms_id],
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_with_invalid_owners_not_namespace_admin(
    client_with_db, session, mock_session_admin, test_namespace
):
    """Test creating course with owners that have program_manager role instead of namespace_admin."""

    namespace_id = test_namespace["id"]
    admin_user = session.query(User).filter_by(username="admin").first()
    pm_user = session.query(User).filter_by(username="pm_user").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    # Add pm_user as program manager (not namespace admin)
    user_on_namespace = UserOnNamespace(
        user_id=pm_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[pm_user.rms_id] = RmsUser(
        id=pm_user.rms_id, username=pm_user.username, name=f"{pm_user.first_name} {pm_user.last_name}"
    )

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Course PM Owner",
            "slug": "course-pm-owner",
            "owners": [pm_user.rms_id],
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data
    assert "namespace_admin" in data["error"]


def test_create_course_duplicate_course_name(client_with_db, session, mock_session_admin, test_namespace):
    """Test that creating course with duplicate name returns 409 Conflict."""

    namespace_id = test_namespace["id"]

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create first course
    response1 = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Duplicate Course",
            "slug": "duplicate-course-1",
        },
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.CREATED

    # Try to create second course with same name but different slug
    response2 = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Duplicate Course",
            "slug": "duplicate-course-2",
        },
        content_type="application/json",
    )

    assert response2.status_code == HTTPStatus.CONFLICT
    data = json.loads(response2.data)
    assert "error" in data


def test_create_course_duplicate_slug(client_with_db, session, mock_session_admin, test_namespace):
    """Test that creating course with duplicate slug returns 409 Conflict."""

    namespace_id = test_namespace["id"]

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create first course
    response1 = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "First Course",
            "slug": "same-slug",
        },
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.CREATED

    # Try to create second course with same slug but different name
    response2 = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Second Course",
            "slug": "same-slug",
        },
        content_type="application/json",
    )

    assert response2.status_code == HTTPStatus.CONFLICT
    data = json.loads(response2.data)
    assert "error" in data


def test_create_course_invalid_slug(client_with_db, mock_session_admin, test_namespace):
    """Test that invalid slug returns 400 Bad Request."""

    namespace_id = test_namespace["id"]

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    invalid_slugs = [
        "invalid..slug",  # Consecutive dots
        "-invalid",  # Starts with dash
        "invalid-",  # Ends with dash
        "invalid slug",  # Contains space
        "",  # Empty
    ]

    for invalid_slug in invalid_slugs:
        response = client_with_db.post(
            "/api/admin/courses",
            json={
                "namespace_id": namespace_id,
                "course_name": "Test Course",
                "slug": invalid_slug,
            },
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, f"Slug '{invalid_slug}' should be invalid"
        data = json.loads(response.data)
        assert "error" in data


def test_create_course_missing_fields(client_with_db, mock_session_admin):
    """Test that missing required fields returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Missing course_name
    response1 = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": 1,
            "slug": "test-slug",
        },
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.BAD_REQUEST

    # Missing slug
    response2 = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": 1,
            "course_name": "Test Course",
        },
        content_type="application/json",
    )
    assert response2.status_code == HTTPStatus.BAD_REQUEST

    # Missing namespace_id
    response3 = client_with_db.post(
        "/api/admin/courses",
        json={
            "course_name": "Test Course",
            "slug": "test-slug",
        },
        content_type="application/json",
    )
    assert response3.status_code == HTTPStatus.BAD_REQUEST


def test_create_course_not_json(client_with_db, mock_session_admin):
    """Test that non-JSON request returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        data="not json",
        content_type="text/plain",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data
    assert "JSON" in data["error"]


def test_create_course_nonexistent_namespace(client_with_db, mock_session_admin):
    """Test creating course in non-existent namespace returns 404."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": 99999,
            "course_name": "Test Course",
            "slug": "test-course",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_with_nonexistent_owner(client_with_db, mock_session_admin, test_namespace):
    """Test creating course with non-existent owner returns 400."""

    namespace_id = test_namespace["id"]

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/admin/courses",
        json={
            "namespace_id": namespace_id,
            "course_name": "Test Course",
            "slug": "test-course",
            "owners": [99999],  # Non-existent user
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data

"""Tests for namespace API endpoints."""

from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, json

from manytask.abstract import AuthApi, AuthenticatedUser
from manytask.api import namespace_bp
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.mock_rms import MockRmsApi
from manytask.models import (
    ROLE_NAMESPACE_ADMIN,
    ROLE_PROGRAM_MANAGER,
    Namespace,
    User,
    UserOnNamespace,
    UserOnNamespaceRole,
)
from manytask.web import root_bp
from tests.constants import GITLAB_BASE_URL, TEST_SECRET_KEY


class MockAuthApi(AuthApi):
    """Mock AuthApi for testing."""

    def check_user_is_authenticated(
        self,
        oauth: OAuth,
        oauth_access_token: str,
        oauth_refresh_token: str,
    ) -> bool:
        # For testing, always return True
        return True

    def get_authenticated_user(
        self,
        oauth_access_token: str,
    ) -> AuthenticatedUser:
        # For testing, return a dummy user
        return AuthenticatedUser(id=1, username="test_user")


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

    # Setup storage_api with test database
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
    app.oauth = MagicMock()  # Mock OAuth object

    # DataBaseApi already created admin user with username="admin" and rms_id=-1
    # Just create a regular user
    regular_user = User(
        username="regular_user",
        first_name="Regular",
        last_name="User",
        rms_id=2,
        is_instance_admin=False,
    )
    session.add(regular_user)
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
    # Get the actual admin user created by DataBaseApi
    admin = session.query(User).filter_by(username="admin").first()
    return {
        "gitlab": {
            "username": "admin",
            "user_id": admin.id,
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
def mock_session_regular(session):
    """Mock session for regular user."""
    # Get the regular user we created
    regular = session.query(User).filter_by(username="regular_user").first()
    return {
        "gitlab": {
            "username": "regular_user",
            "user_id": regular.id,
            "version": 1.5,
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
        },
        "profile": {
            "username": "regular_user",
            "version": 1.0,
        },
    }


def test_create_namespace_as_instance_admin(client_with_db, session, mock_session_admin):
    """Test that Instance Admin can successfully create a namespace."""

    admin_user = session.query(User).filter_by(username="admin").first()

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "HSE",
            "slug": "hse-namespace",
            "description": "Namespace for Higher School of Economics courses",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)

    assert "id" in data
    assert data["name"] == "HSE"
    assert data["slug"] == "hse-namespace"
    assert data["description"] == "Namespace for Higher School of Economics courses"
    assert "gitlab_group_id" in data
    assert data["gitlab_group_id"] > 0

    # Check database
    namespace = session.query(Namespace).filter_by(slug="hse-namespace").first()
    assert namespace is not None
    assert namespace.name == "HSE"
    assert namespace.description == "Namespace for Higher School of Economics courses"
    assert namespace.gitlab_group_id == data["gitlab_group_id"]

    # Check user is assigned as namespace_admin
    user_on_namespace = (
        session.query(UserOnNamespace).filter_by(namespace_id=namespace.id, user_id=admin_user.id).first()
    )
    assert user_on_namespace is not None
    assert user_on_namespace.role == UserOnNamespaceRole.NAMESPACE_ADMIN
    assert user_on_namespace.assigned_by_id == admin_user.id  # Self-assigned


def test_create_namespace_as_regular_user(client_with_db, mock_session_regular):
    """Test that regular user cannot create a namespace (403 Forbidden)."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_regular)

    response = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "HSE",
            "slug": "hse-namespace",
            "description": "Test",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert "Instance Admin" in data["error"]


def test_create_namespace_duplicate_slug(client_with_db, session, mock_session_admin):
    """Test that creating namespace with existing slug returns 409 Conflict."""

    # Create first namespace
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response1 = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "HSE",
            "slug": "hse-namespace",
            "description": "First namespace",
        },
        content_type="application/json",
    )

    assert response1.status_code == HTTPStatus.CREATED

    # Try to create second namespace with same slug
    response2 = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "Another HSE",
            "slug": "hse-namespace",
            "description": "Second namespace",
        },
        content_type="application/json",
    )

    assert response2.status_code == HTTPStatus.CONFLICT
    data = json.loads(response2.data)
    assert "error" in data


def test_create_namespace_invalid_slug(client_with_db, mock_session_admin):
    """Test that invalid slug returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Test various invalid slugs
    invalid_slugs = [
        "invalid..slug",  # Consecutive dots
        "-invalid",  # Starts with dash
        "invalid-",  # Ends with dash
        "invalid slug",  # Contains space
        "invalid/slug",  # Contains slash
        "",  # Empty
    ]

    for invalid_slug in invalid_slugs:
        response = client_with_db.post(
            "/api/namespaces",
            json={
                "name": "Test",
                "slug": invalid_slug,
                "description": "Test",
            },
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, f"Slug '{invalid_slug}' should be invalid"
        data = json.loads(response.data)
        assert "error" in data


def test_create_namespace_missing_fields(client_with_db, mock_session_admin):
    """Test that missing required fields returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Missing name
    response1 = client_with_db.post(
        "/api/namespaces",
        json={
            "slug": "test-slug",
            "description": "Test",
        },
        content_type="application/json",
    )

    assert response1.status_code == HTTPStatus.BAD_REQUEST

    # Missing slug
    response2 = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "Test",
            "description": "Test",
        },
        content_type="application/json",
    )

    assert response2.status_code == HTTPStatus.BAD_REQUEST


def test_create_namespace_not_json(client_with_db, mock_session_admin):
    """Test that non-JSON request returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        data="not json",
        content_type="text/plain",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data
    assert "JSON" in data["error"]


def test_create_namespace_without_description(client_with_db, session, mock_session_admin):
    """Test that description is optional."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={
            "name": "HSE",
            "slug": "hse-namespace",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)

    assert data["description"] is None

    # Check database
    namespace = session.query(Namespace).filter_by(slug="hse-namespace").first()
    assert namespace is not None
    assert namespace.description is None


def test_create_namespace_valid_slugs(client_with_db, session, mock_session_admin):
    """Test that various valid slugs are accepted."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    valid_slugs = [
        "simple",
        "with-dashes",
        "with_underscores",
        "with.dots",
        "MixedCase123",
        "123numeric",
    ]

    for i, valid_slug in enumerate(valid_slugs):
        response = client_with_db.post(
            "/api/namespaces",
            json={
                "name": f"Test {i}",
                "slug": valid_slug,
                "description": "Test",
            },
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.CREATED, f"Slug '{valid_slug}' should be valid"

        # Verify in database
        namespace = session.query(Namespace).filter_by(slug=valid_slug).first()
        assert namespace is not None


def test_get_namespaces_as_instance_admin(client_with_db, session, mock_session_admin):
    """Test that Instance Admin sees all namespaces."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create multiple namespaces
    response1 = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse", "description": "HSE namespace"},
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.CREATED

    response2 = client_with_db.post(
        "/api/namespaces",
        json={"name": "MIT", "slug": "mit", "description": "MIT namespace"},
        content_type="application/json",
    )
    assert response2.status_code == HTTPStatus.CREATED

    response3 = client_with_db.post(
        "/api/namespaces",
        json={"name": "Stanford", "slug": "stanford"},
        content_type="application/json",
    )
    assert response3.status_code == HTTPStatus.CREATED

    # Get all namespaces
    response = client_with_db.get("/api/namespaces")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "namespaces" in data
    assert len(data["namespaces"]) == 3  # noqa: PLR2004

    # Check that namespaces are returned correctly
    slugs = {ns["slug"] for ns in data["namespaces"]}
    assert slugs == {"hse", "mit", "stanford"}

    # Check that role field is NOT present for Instance Admin
    for ns in data["namespaces"]:
        assert "role" not in ns
        assert "id" in ns
        assert "name" in ns
        assert "slug" in ns
        assert "gitlab_group_id" in ns


def test_get_namespaces_as_regular_user_with_roles(client_with_db, session, mock_session_admin, mock_session_regular):
    """Test that regular user sees only namespaces where they have a role."""

    # Create namespaces as admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response1 = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse", "description": "HSE namespace"},
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.CREATED
    ns1_data = json.loads(response1.data)

    response2 = client_with_db.post(
        "/api/namespaces",
        json={"name": "MIT", "slug": "mit", "description": "MIT namespace"},
        content_type="application/json",
    )
    assert response2.status_code == HTTPStatus.CREATED

    # Assign regular user a role on HSE namespace
    regular_user = session.query(User).filter_by(username="regular_user").first()
    hse_namespace = session.query(Namespace).filter_by(slug="hse").first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=hse_namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=regular_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Get namespaces as regular user
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    response = client_with_db.get("/api/namespaces")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "namespaces" in data
    assert len(data["namespaces"]) == 1

    # Check that only HSE namespace is returned
    ns = data["namespaces"][0]
    assert ns["slug"] == "hse"
    assert ns["name"] == "HSE"
    assert ns["id"] == ns1_data["id"]

    # Check that role field IS present for regular user
    assert "role" in ns
    assert ns["role"] == ROLE_PROGRAM_MANAGER


def test_get_namespaces_as_regular_user_without_roles(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that regular user without roles sees empty list."""

    # Create namespaces as admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response1 = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse"},
        content_type="application/json",
    )
    assert response1.status_code == HTTPStatus.CREATED

    # Get namespaces as regular user (without any roles)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    response = client_with_db.get("/api/namespaces")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "namespaces" in data
    assert len(data["namespaces"]) == 0


def test_get_namespaces_empty_list(client_with_db, mock_session_admin):
    """Test that Instance Admin gets empty list when no namespaces exist."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.get("/api/namespaces")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "namespaces" in data
    assert len(data["namespaces"]) == 0
    assert data["namespaces"] == []


def test_get_namespace_by_id_as_instance_admin(client_with_db, session, mock_session_admin):
    """Test that Instance Admin can access any namespace without role field."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create a namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse", "description": "HSE namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Get namespace by ID
    response = client_with_db.get(f"/api/namespaces/{namespace_id}")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert data["id"] == namespace_id
    assert data["name"] == "HSE"
    assert data["slug"] == "hse"
    assert data["description"] == "HSE namespace"
    assert data["gitlab_group_id"] == namespace_data["gitlab_group_id"]

    # Instance Admin should NOT have role field
    assert "role" not in data


def test_get_namespace_by_id_as_regular_user_with_access(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that regular user can access namespace where they have a role."""

    # Create namespace as admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse", "description": "HSE namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Assign regular user a role
    regular_user = session.query(User).filter_by(username="regular_user").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=regular_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Get namespace as regular user
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    response = client_with_db.get(f"/api/namespaces/{namespace_id}")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert data["id"] == namespace_id
    assert data["name"] == "HSE"
    assert data["slug"] == "hse"

    # Regular user should have role field
    assert "role" in data
    assert data["role"] == ROLE_PROGRAM_MANAGER


def test_get_namespace_by_id_as_regular_user_without_access(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that regular user gets 403 for namespace where they don't have a role."""

    # Create namespace as admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Try to get namespace as regular user (without role)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    response = client_with_db.get(f"/api/namespaces/{namespace_id}")

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Access denied"


def test_get_namespace_by_id_nonexistent(client_with_db, mock_session_admin):
    """Test that accessing non-existent namespace returns 403 (not 404)."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Try to access non-existent namespace
    response = client_with_db.get("/api/namespaces/99999")

    # Should return 403 to not reveal existence
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Access denied"


def test_add_user_to_namespace_as_instance_admin(client_with_db, session, mock_session_admin):
    """Test that Instance Admin can add a user to namespace."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Create a regular user
    regular_user = User(
        username="new_user",
        first_name="New",
        last_name="User",
        rms_id=100,
        is_instance_admin=False,
    )
    session.add(regular_user)
    session.commit()

    # Register user in mock RMS
    app = client_with_db.application
    app.rms_api.users[regular_user.rms_id] = (
        app.rms_api.get_rms_user_by_id.__func__(app.rms_api, regular_user.rms_id)
        if regular_user.rms_id in app.rms_api.users
        else None
    )
    if app.rms_api.users[regular_user.rms_id] is None:
        from manytask.abstract import RmsUser

        app.rms_api.users[regular_user.rms_id] = RmsUser(
            id=regular_user.rms_id,
            username=regular_user.username,
            name=f"{regular_user.first_name} {regular_user.last_name}",
        )

    # Add user to namespace with program_manager role
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": regular_user.rms_id, "role": ROLE_PROGRAM_MANAGER},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)

    assert "id" in data
    assert data["user_id"] == regular_user.id
    assert data["namespace_id"] == namespace_id
    assert data["role"] == ROLE_PROGRAM_MANAGER

    # Verify in database
    user_on_namespace = (
        session.query(UserOnNamespace).filter_by(user_id=regular_user.id, namespace_id=namespace_id).first()
    )
    assert user_on_namespace is not None
    assert user_on_namespace.role == UserOnNamespaceRole.PROGRAM_MANAGER


def test_add_user_to_namespace_as_namespace_admin(client_with_db, session, mock_session_admin, mock_session_regular):
    """Test that Namespace Admin can add users to their namespace."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Make regular_user a namespace admin
    regular_user = session.query(User).filter_by(username="regular_user").first()
    admin_user = session.query(User).filter_by(username="admin").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.NAMESPACE_ADMIN,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Create another user to add
    new_user = User(
        username="another_user",
        first_name="Another",
        last_name="User",
        rms_id=101,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Switch to regular_user (who is now namespace admin)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Add new user to namespace
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": ROLE_NAMESPACE_ADMIN},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)
    assert data["role"] == ROLE_NAMESPACE_ADMIN


def test_add_user_to_namespace_as_program_manager_forbidden(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that Program Manager cannot add users (403 Forbidden)."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Make regular_user a program manager
    regular_user = session.query(User).filter_by(username="regular_user").first()
    admin_user = session.query(User).filter_by(username="admin").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Create another user to add
    new_user = User(
        username="another_user",
        first_name="Another",
        last_name="User",
        rms_id=102,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Switch to regular_user (who is program manager)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Try to add new user - should fail
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": ROLE_PROGRAM_MANAGER},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data


def test_add_user_to_namespace_duplicate_role(client_with_db, session, mock_session_admin):
    """Test that adding user with existing role returns 409 Conflict."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Create user
    new_user = User(
        username="new_user",
        first_name="New",
        last_name="User",
        rms_id=103,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Add user first time
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": ROLE_PROGRAM_MANAGER},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED

    # Try to add same user again with different role - should fail
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": ROLE_NAMESPACE_ADMIN},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CONFLICT
    data = json.loads(response.data)
    assert "error" in data
    assert "already has a role" in data["error"]


def test_add_user_to_namespace_invalid_role(client_with_db, session, mock_session_admin):
    """Test that invalid role returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Create user
    new_user = User(
        username="new_user",
        first_name="New",
        last_name="User",
        rms_id=104,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Try invalid roles
    invalid_roles = ["student", "invalid", ""]

    for invalid_role in invalid_roles:
        response = client_with_db.post(
            f"/api/namespaces/{namespace_id}/users",
            json={"user_id": new_user.rms_id, "role": invalid_role},
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST, f"Role '{invalid_role}' should be invalid"
        data = json.loads(response.data)
        assert "error" in data


def test_add_user_to_namespace_missing_fields(client_with_db, mock_session_admin):
    """Test that missing required fields returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Missing user_id
    response = client_with_db.post(
        "/api/namespaces/1/users",
        json={"role": ROLE_NAMESPACE_ADMIN},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST

    # Missing role
    response = client_with_db.post(
        "/api/namespaces/1/users",
        json={"user_id": 1},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST

    # Empty JSON
    response = client_with_db.post(
        "/api/namespaces/1/users",
        json={},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_add_user_to_namespace_not_json(client_with_db, mock_session_admin):
    """Test that non-JSON request returns 400 Bad Request."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces/1/users",
        data="not json",
        content_type="text/plain",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data
    assert "JSON" in data["error"]


def test_add_user_to_namespace_nonexistent_user(client_with_db, session, mock_session_admin):
    """Test that adding non-existent user returns 404."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Try to add non-existent user
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": 99999, "role": ROLE_NAMESPACE_ADMIN},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_add_user_to_namespace_nonexistent_namespace(client_with_db, session, mock_session_admin):
    """Test that adding user to non-existent namespace returns 404."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create user
    new_user = User(
        username="new_user",
        first_name="New",
        last_name="User",
        rms_id=105,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Try to add user to non-existent namespace
    response = client_with_db.post(
        "/api/namespaces/99999/users",
        json={"user_id": new_user.rms_id, "role": ROLE_NAMESPACE_ADMIN},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_get_namespace_users_as_instance_admin(client_with_db, session, mock_session_admin):
    """Test that Instance Admin can get list of users in any namespace."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Create another user and add to namespace
    new_user = User(
        username="test_user",
        first_name="Test",
        last_name="User",
        rms_id=200,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Add user to namespace
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": ROLE_PROGRAM_MANAGER},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED

    # Get users list
    response = client_with_db.get(f"/api/namespaces/{namespace_id}/users")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "users" in data
    assert len(data["users"]) == 2  # admin + new_user  # noqa: PLR2004

    # Check that both users are present
    user_ids = {user["user_id"] for user in data["users"]}
    admin_user = session.query(User).filter_by(username="admin").first()
    assert admin_user.id in user_ids
    assert new_user.id in user_ids

    # Check roles
    users_by_id = {user["user_id"]: user["role"] for user in data["users"]}
    assert users_by_id[admin_user.id] == "namespace_admin"
    assert users_by_id[new_user.id] == "program_manager"


def test_get_namespace_users_as_namespace_admin(client_with_db, session, mock_session_admin, mock_session_regular):
    """Test that Namespace Admin can get list of users in their namespace."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Make regular_user a namespace admin
    regular_user = session.query(User).filter_by(username="regular_user").first()
    admin_user = session.query(User).filter_by(username="admin").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.NAMESPACE_ADMIN,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Switch to regular_user (who is now namespace admin)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Get users list
    response = client_with_db.get(f"/api/namespaces/{namespace_id}/users")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "users" in data
    assert len(data["users"]) == 2  # admin + regular_user  # noqa: PLR2004

    # Check that both users are present
    user_ids = {user["user_id"] for user in data["users"]}
    assert admin_user.id in user_ids
    assert regular_user.id in user_ids


def test_get_namespace_users_as_program_manager_forbidden(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that Program Manager cannot view users list (403 Forbidden)."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Make regular_user a program manager
    regular_user = session.query(User).filter_by(username="regular_user").first()
    admin_user = session.query(User).filter_by(username="admin").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Switch to regular_user (who is program manager)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Try to get users list - should fail
    response = client_with_db.get(f"/api/namespaces/{namespace_id}/users")

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert "Instance Admin or Namespace Admin" in data["error"]


def test_get_namespace_users_without_access(client_with_db, session, mock_session_admin, mock_session_regular):
    """Test that user without access gets 403 Forbidden."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Switch to regular_user (who has no access)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Try to get users list - should fail
    response = client_with_db.get(f"/api/namespaces/{namespace_id}/users")

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Access denied"


def test_get_namespace_users_nonexistent_namespace(client_with_db, mock_session_admin):
    """Test that accessing non-existent namespace returns 403."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Try to get users from non-existent namespace
    response = client_with_db.get("/api/namespaces/99999/users")

    # Should return 403 to not reveal existence
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Access denied"


def test_get_namespace_users_empty_list(client_with_db, session, mock_session_admin):
    """Test that namespace with only the creator returns just that user."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace (admin becomes namespace_admin automatically)
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Get users list
    response = client_with_db.get(f"/api/namespaces/{namespace_id}/users")

    assert response.status_code == HTTPStatus.OK
    data = json.loads(response.data)

    assert "users" in data
    assert len(data["users"]) == 1  # Only admin

    admin_user = session.query(User).filter_by(username="admin").first()
    assert data["users"][0]["user_id"] == admin_user.id
    assert data["users"][0]["role"] == "namespace_admin"


def test_remove_user_from_namespace_as_instance_admin(client_with_db, session, mock_session_admin):
    """Test that Instance Admin can remove a user from namespace."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Create a user and add to namespace
    new_user = User(
        username="test_user",
        first_name="Test",
        last_name="User",
        rms_id=300,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Add user to namespace
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": "program_manager"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED

    # Verify user is in namespace
    user_on_namespace = session.query(UserOnNamespace).filter_by(user_id=new_user.id, namespace_id=namespace_id).first()
    assert user_on_namespace is not None
    assert user_on_namespace.role == UserOnNamespaceRole.PROGRAM_MANAGER

    # Remove user from namespace
    response = client_with_db.delete(f"/api/namespaces/{namespace_id}/users/{new_user.id}")

    assert response.status_code == HTTPStatus.NO_CONTENT

    # Verify user is removed from database
    user_on_namespace = session.query(UserOnNamespace).filter_by(user_id=new_user.id, namespace_id=namespace_id).first()
    assert user_on_namespace is None


def test_remove_user_from_namespace_as_namespace_admin(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that Namespace Admin can remove users from their namespace."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Make regular_user a namespace admin
    regular_user = session.query(User).filter_by(username="regular_user").first()
    admin_user = session.query(User).filter_by(username="admin").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.NAMESPACE_ADMIN,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Create another user to remove
    new_user = User(
        username="another_user",
        first_name="Another",
        last_name="User",
        rms_id=301,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Add user to namespace
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": "program_manager"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED

    # Switch to regular_user (who is namespace admin)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Remove user from namespace
    response = client_with_db.delete(f"/api/namespaces/{namespace_id}/users/{new_user.id}")

    assert response.status_code == HTTPStatus.NO_CONTENT

    # Verify user is removed from database
    user_on_namespace = session.query(UserOnNamespace).filter_by(user_id=new_user.id, namespace_id=namespace_id).first()
    assert user_on_namespace is None


def test_remove_user_from_namespace_as_program_manager_forbidden(
    client_with_db, session, mock_session_admin, mock_session_regular
):
    """Test that Program Manager cannot remove users (403 Forbidden)."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Make regular_user a program manager
    regular_user = session.query(User).filter_by(username="regular_user").first()
    admin_user = session.query(User).filter_by(username="admin").first()
    namespace = session.query(Namespace).filter_by(id=namespace_id).first()

    user_on_namespace = UserOnNamespace(
        user_id=regular_user.id,
        namespace_id=namespace.id,
        role=UserOnNamespaceRole.PROGRAM_MANAGER,
        assigned_by_id=admin_user.id,
    )
    session.add(user_on_namespace)
    session.commit()

    # Create another user to try to remove
    new_user = User(
        username="another_user",
        first_name="Another",
        last_name="User",
        rms_id=302,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Register in mock RMS
    from manytask.abstract import RmsUser

    app = client_with_db.application
    app.rms_api.users[new_user.rms_id] = RmsUser(
        id=new_user.rms_id, username=new_user.username, name=f"{new_user.first_name} {new_user.last_name}"
    )

    # Add user to namespace
    response = client_with_db.post(
        f"/api/namespaces/{namespace_id}/users",
        json={"user_id": new_user.rms_id, "role": "namespace_admin"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED

    # Switch to regular_user (who is program manager)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Try to remove user - should fail
    response = client_with_db.delete(f"/api/namespaces/{namespace_id}/users/{new_user.id}")

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert "Instance Admin or Namespace Admin" in data["error"]


def test_remove_user_from_namespace_nonexistent_user(client_with_db, session, mock_session_admin):
    """Test that removing non-existent user returns 404 Not Found."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Create namespace
    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Try to remove non-existent user
    response = client_with_db.delete(f"/api/namespaces/{namespace_id}/users/99999")

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data
    assert "not found" in data["error"].lower()


def test_remove_user_from_namespace_without_access(client_with_db, session, mock_session_admin, mock_session_regular):
    """Test that user without access gets 403 Forbidden."""

    # Create namespace as instance admin
    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    response = client_with_db.post(
        "/api/namespaces",
        json={"name": "HSE", "slug": "hse-namespace"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.CREATED
    namespace_data = json.loads(response.data)
    namespace_id = namespace_data["id"]

    # Create another user
    new_user = User(
        username="another_user",
        first_name="Another",
        last_name="User",
        rms_id=303,
        is_instance_admin=False,
    )
    session.add(new_user)
    session.commit()

    # Switch to regular_user (who has no access to namespace)
    with client_with_db.session_transaction() as sess:
        sess.clear()
        sess.update(mock_session_regular)

    # Try to remove user - should fail
    response = client_with_db.delete(f"/api/namespaces/{namespace_id}/users/{new_user.id}")

    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Access denied"


def test_remove_user_from_namespace_nonexistent_namespace(client_with_db, mock_session_admin):
    """Test that accessing non-existent namespace returns 403."""

    with client_with_db.session_transaction() as sess:
        sess.update(mock_session_admin)

    # Try to remove user from non-existent namespace
    response = client_with_db.delete("/api/namespaces/99999/users/1")

    # Should return 403 to not reveal existence
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Access denied"

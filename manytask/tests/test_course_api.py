"""Tests for course creation API endpoint."""

from http import HTTPStatus

import pytest
from flask import json

from manytask.mock_auth import MockAuthApi
from manytask.models import Course, User, UserOnNamespaceRole
from tests.helpers import (
    assert_forbidden_admin_only,
    assert_not_json_rejected,
    assert_slugs_rejected,
    assign_namespace_role_for_user,
    build_mock_session,
    build_namespace_app,
    create_namespace,
    get_user,
    make_user,
    post_json,
    post_json_as,
    register_rms_user,
    set_session,
)


@pytest.fixture
def app_with_db(engine, session, postgres_container):
    """Create Flask app with real database."""
    app = build_namespace_app(session, postgres_container, apply_migrations=True, auth_api=MockAuthApi())

    session.add(make_user("regular_user", "Regular", "User", "2", 2))
    session.add(make_user("namespace_admin_user", "Namespace", "Admin", "3", 3))
    session.add(make_user("pm_user", "PM", "User", "4", 4))
    session.commit()

    return app


@pytest.fixture
def mock_session_admin(session):
    """Mock session for admin user."""
    admin = session.query(User).filter_by(username="admin").first()
    return build_mock_session("admin", user_auth_id=admin.auth_id, rms_id=admin.rms_id, user_id=admin.id)


@pytest.fixture
def mock_session_namespace_admin(session):
    """Mock session for namespace admin user."""
    user = session.query(User).filter_by(username="namespace_admin_user").first()
    return build_mock_session("namespace_admin_user", user_auth_id=user.auth_id, rms_id=user.rms_id, user_id=user.id)


@pytest.fixture
def mock_session_pm(session):
    """Mock session for program manager user."""
    user = session.query(User).filter_by(username="pm_user").first()
    return build_mock_session("pm_user", user_auth_id=user.auth_id, rms_id=user.rms_id, user_id=user.id)


@pytest.fixture
def mock_session_regular(session):
    """Mock session for regular user."""
    user = session.query(User).filter_by(username="regular_user").first()
    return build_mock_session("regular_user", user_auth_id=user.auth_id, rms_id=user.rms_id, user_id=user.id)


@pytest.fixture
def test_namespace(session, client_with_db, mock_session_admin):
    """Create a test namespace."""
    set_session(client_with_db, mock_session_admin)

    return create_namespace(
        client_with_db, name="Test University", slug="test-university", description="Test namespace"
    )


def test_create_course_as_instance_admin(client_with_db, session, mock_session_admin, test_namespace):
    """Test that Instance Admin can create a course in any namespace."""

    namespace_id = test_namespace["id"]

    response = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Algorithms 2024 Spring",
            "slug": "algorithms-2024-spring",
        },
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
    ns_admin_user = get_user(session, "namespace_admin_user")
    assign_namespace_role_for_user(
        session, username="namespace_admin_user", namespace_id=namespace_id, role=UserOnNamespaceRole.NAMESPACE_ADMIN,
    )

    # Register user in mock RMS
    register_rms_user(client_with_db.application, ns_admin_user)

    # Switch to namespace admin
    set_session(client_with_db, mock_session_namespace_admin, clear=True)

    response = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Machine Learning 2024",
            "slug": "ml-2024",
        },
    )

    assert response.status_code == HTTPStatus.CREATED
    data = json.loads(response.data)
    assert data["course_name"] == "Machine Learning 2024"


def test_create_course_as_namespace_admin_in_other_namespace(
    client_with_db, session, mock_session_admin, mock_session_namespace_admin
):
    """Test that Namespace Admin cannot create course in another namespace."""

    # Create two namespaces
    set_session(client_with_db, mock_session_admin)

    response1 = post_json(client_with_db, "/api/namespaces", {"name": "Namespace 1", "slug": "ns1"})
    assert response1.status_code == HTTPStatus.CREATED
    ns1_data = json.loads(response1.data)

    response2 = post_json(client_with_db, "/api/namespaces", {"name": "Namespace 2", "slug": "ns2"})
    assert response2.status_code == HTTPStatus.CREATED
    ns2_data = json.loads(response2.data)

    # Add user as namespace admin to ns1 only
    ns_admin_user = get_user(session, "namespace_admin_user")
    assign_namespace_role_for_user(
        session, username="namespace_admin_user", namespace_id=ns1_data["id"], role=UserOnNamespaceRole.NAMESPACE_ADMIN,
    )

    # Register in mock RMS
    register_rms_user(client_with_db.application, ns_admin_user)

    # Try to create course in ns2
    set_session(client_with_db, mock_session_namespace_admin, clear=True)

    response = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "namespace_id": ns2_data["id"],
            "course_name": "Unauthorized Course",
            "slug": "unauthorized",
        },
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
    pm_user = get_user(session, "pm_user")
    assign_namespace_role_for_user(
        session, username="pm_user", namespace_id=namespace_id, role=UserOnNamespaceRole.PROGRAM_MANAGER,
    )

    # Register in mock RMS
    register_rms_user(client_with_db.application, pm_user)

    # Try to create course
    set_session(client_with_db, mock_session_pm, clear=True)

    response = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Forbidden Course",
            "slug": "forbidden",
        },
    )

    assert_forbidden_admin_only(response)


def test_create_course_as_regular_user_forbidden(client_with_db, session, mock_session_regular, test_namespace):
    """Test that regular user without namespace role cannot create courses."""

    namespace_id = test_namespace["id"]

    response = post_json_as(
        client_with_db,
        mock_session_regular,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Forbidden Course",
            "slug": "forbidden",
        },
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_with_valid_owners(client_with_db, session, mock_session_admin, test_namespace):
    """Test creating course with valid owners (namespace admins)."""

    namespace_id = test_namespace["id"]
    ns_admin_user = get_user(session, "namespace_admin_user")

    # Add namespace_admin_user as namespace admin
    assign_namespace_role_for_user(
        session, username="namespace_admin_user", namespace_id=namespace_id, role=UserOnNamespaceRole.NAMESPACE_ADMIN,
    )

    # Register in mock RMS
    register_rms_user(client_with_db.application, ns_admin_user)

    response = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Course with Owners",
            "slug": "course-with-owners",
            "owners": [ns_admin_user.rms_id],
        },
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
    register_rms_user(client_with_db.application, regular_user)

    response = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Course with Invalid Owners",
            "slug": "course-invalid-owners",
            "owners": [regular_user.rms_id],
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_with_invalid_owners_not_namespace_admin(
    client_with_db, session, mock_session_admin, test_namespace
):
    """Test creating course with owners that have program_manager role instead of namespace_admin."""

    namespace_id = test_namespace["id"]
    pm_user = get_user(session, "pm_user")

    # Add pm_user as program manager (not namespace admin)
    assign_namespace_role_for_user(
        session, username="pm_user", namespace_id=namespace_id, role=UserOnNamespaceRole.PROGRAM_MANAGER,
    )

    # Register in mock RMS
    register_rms_user(client_with_db.application, pm_user)

    response = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Course PM Owner",
            "slug": "course-pm-owner",
            "owners": [pm_user.rms_id],
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data
    assert "namespace_admin" in data["error"]


def test_create_course_duplicate_course_name(client_with_db, session, mock_session_admin, test_namespace):
    """Test that creating course with duplicate name returns 409 Conflict."""

    namespace_id = test_namespace["id"]

    # Create first course
    response1 = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Duplicate Course",
            "slug": "duplicate-course-1",
        },
    )
    assert response1.status_code == HTTPStatus.CREATED

    # Try to create second course with same name but different slug
    response2 = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Duplicate Course",
            "slug": "duplicate-course-2",
        },
    )

    assert response2.status_code == HTTPStatus.CONFLICT
    data = json.loads(response2.data)
    assert "error" in data


def test_create_course_duplicate_slug(client_with_db, session, mock_session_admin, test_namespace):
    """Test that creating course with duplicate slug returns 409 Conflict."""

    namespace_id = test_namespace["id"]

    # Create first course
    response1 = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "First Course",
            "slug": "same-slug",
        },
    )
    assert response1.status_code == HTTPStatus.CREATED

    # Try to create second course with same slug but different name
    response2 = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Second Course",
            "slug": "same-slug",
        },
    )

    assert response2.status_code == HTTPStatus.CONFLICT
    data = json.loads(response2.data)
    assert "error" in data


def test_create_course_invalid_slug(client_with_db, mock_session_admin, test_namespace):
    """Test that invalid slug returns 400 Bad Request."""

    namespace_id = test_namespace["id"]

    set_session(client_with_db, mock_session_admin)

    invalid_slugs = ["invalid..slug", "-invalid", "invalid-", "invalid slug", ""]
    assert_slugs_rejected(
        client_with_db,
        "/api/admin/courses",
        invalid_slugs,
        lambda slug: {"namespace_id": namespace_id, "course_name": "Test Course", "slug": slug},
    )


def test_create_course_missing_fields(client_with_db, mock_session_admin):
    """Test that missing required fields returns 400 Bad Request."""

    # Missing course_name
    response1 = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": 1,
            "slug": "test-slug",
        },
    )
    assert response1.status_code == HTTPStatus.BAD_REQUEST

    # Missing slug
    response2 = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "namespace_id": 1,
            "course_name": "Test Course",
        },
    )
    assert response2.status_code == HTTPStatus.BAD_REQUEST

    # Missing namespace_id
    response3 = post_json(
        client_with_db,
        "/api/admin/courses",
        {
            "course_name": "Test Course",
            "slug": "test-slug",
        },
    )
    assert response3.status_code == HTTPStatus.BAD_REQUEST


def test_create_course_not_json(client_with_db, mock_session_admin):
    """Test that non-JSON request returns 400 Bad Request."""

    set_session(client_with_db, mock_session_admin)

    assert_not_json_rejected(client_with_db, "/api/admin/courses")


def test_create_course_nonexistent_namespace(client_with_db, mock_session_admin):
    """Test creating course in non-existent namespace returns 404."""

    response = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": 99999,
            "course_name": "Test Course",
            "slug": "test-course",
        },
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    data = json.loads(response.data)
    assert "error" in data


def test_create_course_with_nonexistent_owner(client_with_db, mock_session_admin, test_namespace):
    """Test creating course with non-existent owner returns 400."""

    namespace_id = test_namespace["id"]

    response = post_json_as(
        client_with_db,
        mock_session_admin,
        "/api/admin/courses",
        {
            "namespace_id": namespace_id,
            "course_name": "Test Course",
            "slug": "test-course",
            "owners": [99999],  # Non-existent user
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(response.data)
    assert "error" in data

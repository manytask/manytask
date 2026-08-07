from unittest.mock import MagicMock

import pytest
from flask import Flask

from manytask.course import CourseStatus
from manytask.utils.flask import can_edit_course, get_courses, get_user_roles
from tests.constants import TEST_COURSE_NAME, TEST_USERNAME


@pytest.fixture
def app():
    """Minimal Flask app with a storage_api mock sufficient for get_user_roles."""
    app = Flask(__name__)
    app.config["DEBUG"] = False
    app.secret_key = "test_key"

    storage_api = MagicMock()
    storage_api.check_if_instance_admin.return_value = False
    storage_api.check_if_course_admin.return_value = False
    storage_api.get_namespace_admin_namespaces.return_value = []
    # Course with no namespace so check_if_current_user_is_namespace_admin short-circuits to False.
    course = MagicMock()
    course.namespace_id = None
    storage_api.get_course.return_value = course
    app.storage_api = storage_api

    return app


@pytest.mark.parametrize(
    "is_instance_admin,course_name,expected_roles",
    [
        # Regression: instance admin on a route without course_name (e.g.
        # /instance_admin/panel) must still receive the instance_admin role.
        (True, None, ["instance_admin"]),
        # Instance admin on a course-scoped route keeps all applicable roles.
        (True, TEST_COURSE_NAME, ["instance_admin", "student"]),
        # Non-admin without course context has no roles (unchanged behavior).
        (False, None, []),
    ],
    ids=["instance_admin_without_course", "instance_admin_with_course", "non_admin_without_course"],
)
def test_get_user_roles_instance_admin_visibility(app, is_instance_admin, course_name, expected_roles):
    app.storage_api.check_if_instance_admin.return_value = is_instance_admin

    with app.test_request_context():
        # get_user_roles may reach into session via check_if_current_user_is_namespace_admin;
        # only need to seed session when a course_name is supplied.
        if course_name is not None:
            from flask import session

            session["manytask"] = {"username": TEST_USERNAME}

        roles = get_user_roles(app, TEST_USERNAME, course_name=course_name)

    assert roles == expected_roles


@pytest.mark.parametrize(
    "debug,is_instance_admin,namespace_id,namespace_role,expected",
    [
        # Debug mode always grants edit access.
        (True, False, None, None, True),
        # Instance admin can edit any course.
        (False, True, None, None, True),
        (False, True, 5, None, True),
        # Namespace admin of the course's namespace can edit.
        (False, False, 5, "namespace_admin", True),
        # A non-admin role in the namespace (e.g. program manager) cannot edit.
        (False, False, 5, "program_manager", False),
        # No role resolved in the namespace cannot edit.
        (False, False, 5, None, False),
        # Course without a namespace is not editable by non-instance-admins,
        # even if some role string leaks through.
        (False, False, None, "namespace_admin", False),
    ],
    ids=[
        "debug_always_true",
        "instance_admin_no_namespace",
        "instance_admin_with_namespace",
        "namespace_admin",
        "non_admin_namespace_role",
        "no_namespace_role",
        "no_namespace_id",
    ],
)
def test_can_edit_course(debug, is_instance_admin, namespace_id, namespace_role, expected):
    app = MagicMock()
    app.debug = debug

    assert (
        can_edit_course(
            app,
            is_instance_admin=is_instance_admin,
            namespace_id=namespace_id,
            namespace_role=namespace_role,
        )
        is expected
    )


def _course(namespace_id):
    course = MagicMock()
    course.namespace_id = namespace_id
    return course


ADMIN_NAMESPACE_ID = 5
NON_ADMIN_NAMESPACE_ID = 7


def test_get_courses_populates_can_edit_and_edit_url(app, monkeypatch):
    """get_courses must attach can_edit / edit_url mirroring edit_course()."""
    # url_for is exercised without a full app; stub it to a stable value.
    monkeypatch.setattr("manytask.utils.flask.url_for", lambda endpoint, **kw: f"/{endpoint}")

    app.debug = False
    app.storage_api.check_if_instance_admin.return_value = False
    # User is a namespace admin only for ADMIN_NAMESPACE_ID.
    app.storage_api.get_user_courses_names_with_statuses.return_value = [
        ("editable", CourseStatus.IN_PROGRESS),
        ("readonly", CourseStatus.IN_PROGRESS),
        ("no_namespace", CourseStatus.IN_PROGRESS),
    ]

    courses = {
        "editable": _course(ADMIN_NAMESPACE_ID),
        "readonly": _course(NON_ADMIN_NAMESPACE_ID),
        "no_namespace": _course(None),
    }
    app.storage_api.get_course.side_effect = lambda name: courses[name]

    def get_namespace_by_id(namespace_id, _username):
        namespace = MagicMock()
        namespace.slug = f"ns-{namespace_id}"
        role = "namespace_admin" if namespace_id == ADMIN_NAMESPACE_ID else "program_manager"
        return namespace, role

    app.storage_api.get_namespace_by_id.side_effect = get_namespace_by_id

    with app.test_request_context():
        from flask import session

        session["manytask"] = {"username": TEST_USERNAME}
        result = get_courses(app)

    by_name = {c["name"]: c for c in result}
    assert by_name["editable"]["can_edit"] is True
    assert by_name["editable"]["namespace_slug"] == "ns-5"
    assert by_name["editable"]["edit_url"] == "/instance_admin.edit_course"
    assert by_name["readonly"]["can_edit"] is False
    assert by_name["no_namespace"]["can_edit"] is False
    assert by_name["no_namespace"]["namespace_slug"] == ""


def test_get_courses_instance_admin_can_edit_all(app, monkeypatch):
    monkeypatch.setattr("manytask.utils.flask.url_for", lambda endpoint, **kw: f"/{endpoint}")

    app.debug = False
    app.storage_api.check_if_instance_admin.return_value = True
    app.storage_api.get_all_courses_names_with_statuses.return_value = [
        ("some_course", CourseStatus.HIDDEN),
    ]
    app.storage_api.get_course.return_value = _course(None)

    with app.test_request_context():
        from flask import session

        session["manytask"] = {"username": TEST_USERNAME}
        result = get_courses(app)

    assert len(result) == 1
    # Instance admin edits even a course without a namespace.
    assert result[0]["can_edit"] is True

from unittest.mock import MagicMock

import pytest
from flask import Flask

from manytask.utils.flask import get_user_roles
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

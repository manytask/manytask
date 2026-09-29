import json
import os
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import patch

import gitlab
import pytest
from authlib.integrations.base_client import OAuthError
from bs4 import BeautifulSoup
from flask import Flask, url_for
from flask_wtf import CSRFProtect
from wtforms import ValidationError

from manytask import ui
from manytask.abstract import AuthenticatedUser, RmsApiException, StudentCourseScores, TaskScore
from manytask.api import bp as api_bp
from manytask.api import namespace_bp
from manytask.course import CourseStatus
from manytask.local_config import LocalConfig
from manytask.mock_auth import MockAuthApi
from manytask.mock_rms import MockRmsApi
from manytask.web import course_bp, instance_admin_bp, root_bp
from tests.constants import (
    GITLAB_BASE_URL,
    TEST_CLIENT_PROFILE_SESSION_VERSION,
    TEST_COURSE_NAME,
    TEST_EMAIL,
    TEST_FIRST_NAME,
    TEST_FIRST_NAME_1,
    TEST_GITLAB_SESSION_VERSION,
    TEST_GROUP_NAME,
    TEST_LAST_NAME,
    TEST_LAST_NAME_1,
    TEST_PASSWORD,
    TEST_PUBLIC_REPO,
    TEST_RMS_ID,
    TEST_SECRET,
    TEST_SECRET_KEY,
    TEST_STUDENTS_GROUP,
    TEST_TOKEN,
    TEST_USER_ID,
    TEST_USERNAME,
    TEST_USERNAME_1,
)
from tests.helpers import (
    MockCourseBase,
    MockStorageApiBase,
    build_test_session,
    make_created_course_mock,
    raise_for_invalid_task,
    set_session,
)


@pytest.fixture
def app(mock_storage_api):
    app = Flask(
        __name__, template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "manytask/templates")
    )
    app.config["DEBUG"] = False
    app.config["TESTING"] = True
    app.secret_key = "test_key"
    app.register_blueprint(root_bp)
    app.register_blueprint(course_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(namespace_bp)
    app.register_blueprint(instance_admin_bp)
    app.rms_api = MockRmsApi(GITLAB_BASE_URL)
    rms_user = app.rms_api.register_new_user(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_EMAIL, TEST_PASSWORD)
    app.rms_api.create_project(rms_user, TEST_STUDENTS_GROUP, TEST_PUBLIC_REPO)
    app.auth_api = MockAuthApi()
    app.auth_api.user = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
    app.storage_api = mock_storage_api
    app.manytask_version = "1.0.0"
    app.favicon = "test_favicon"
    app.signup_template = "signup.html"
    app.signup_finish_template = "signup_finish.html"
    app.create_course_template = "create_course.html"
    app.app_config = LocalConfig.from_env()  # TODO: init with test data instead of env
    return app


@pytest.fixture
def mock_storage_api(mock_course):  # noqa: C901
    class MockStorageApi(MockStorageApiBase):
        @staticmethod
        def get_all_courses_names_with_statuses():
            return [("test_course_names", CourseStatus.CREATED)]

        @staticmethod
        def get_user_courses_names_with_statuses(_username):
            return [("test_course_names", CourseStatus.CREATED)]

        @staticmethod
        def get_scores(_course_name, _username):
            return {"task1": 100, "task2": 90}

        @staticmethod
        def get_all_scores_with_names(_course_name):
            return {
                TEST_USERNAME: StudentCourseScores(
                    username=TEST_USERNAME,
                    first_name=TEST_FIRST_NAME,
                    last_name=TEST_LAST_NAME,
                    task_scores={
                        "task1": TaskScore(100, False),
                        "task2": TaskScore(90, False),
                    },
                )
            }

        @staticmethod
        def get_stats(_course_name):
            return {"task1": {"mean": 95}, "task2": {"mean": 85}}

        @staticmethod
        def get_bonus_score(_course_name, _username):
            return 10

        def sync_user_on_course(
            self,
            course_name: str,
            username: str,
            course_admin: bool,
        ) -> None:
            self.stored_user.username = username
            self.course_admin = self.course_admin or self.stored_user.instance_admin

        @staticmethod
        def get_groups(*_args, **_kwargs):
            return []

        @staticmethod
        def get_course(_name):
            return mock_course

        @staticmethod
        def find_task(_course_name, task_name):
            raise_for_invalid_task(task_name)
            return None, None, None

        def check_if_instance_admin(self, _username):
            return self.stored_user.instance_admin

        def check_if_course_admin(self, _course_name, _username):
            return self.course_admin

        def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool:
            self.course_admin = self.course_admin or course_admin
            return self.course_admin

        def max_score_started(self, _course_name):
            return 100

        def update_or_create_user(self, username: str, first_name: str, last_name: str, rms_id: int, auth_id: int):
            pass

    return MockStorageApi()


@pytest.fixture
def mock_course():
    class MockCourse(MockCourseBase):
        def __init__(self):
            super().__init__()
            self.registration_secret = TEST_SECRET
            self.gitlab_course_group = TEST_GROUP_NAME
            self.gitlab_course_public_repo = TEST_PUBLIC_REPO
            self.gitlab_course_students_group = TEST_STUDENTS_GROUP
            self.task_url_template = "https://gitlab.example.com/$GROUP_NAME/$USER_NAME/$TASK_NAME"
            self.links = {}

    return MockCourse()


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    monkeypatch.setenv("MANYTASK_COURSE_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("REGISTRATION_SECRET", TEST_SECRET)
    monkeypatch.setenv("FLASK_SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("TESTING", "true")
    yield


def test_healthcheck(app):
    with app.test_request_context():
        response = app.test_client().get("/healthcheck")
        assert response.status_code == HTTPStatus.OK
        assert response.data == b"OK"


def test_course_page_not_ready(app, mock_gitlab_oauth):
    with (
        app.test_request_context(),
        patch.object(app.storage_api, "get_course") as mock_get_course,
    ):
        mock_get_course.return_value = make_created_course_mock()
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(f"/{TEST_COURSE_NAME}/")
        assert response.status_code == HTTPStatus.FOUND
        assert response.headers["Location"] == f"/{TEST_COURSE_NAME}/not_ready"


def test_course_page_invalid_session(app, mock_gitlab_oauth):
    with app.test_request_context():
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(f"/{TEST_COURSE_NAME}/")
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.signup")


def test_course_page_only_with_valid_session(app, mock_gitlab_oauth):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.storage_api, "check_user_on_course") as mock_check_user_on_course,
        ):
            with client.session_transaction() as sess:
                sess.update(build_test_session())
            app.oauth = mock_gitlab_oauth
            mock_check_user_on_course.return_value = False
            response = client.get(f"/{TEST_COURSE_NAME}/")
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == f"/{TEST_COURSE_NAME}/create_project"


@pytest.mark.parametrize("page,template", [("", "tasks.html"), ("database", "database.html")])
@pytest.mark.parametrize("score_case", [({"task1": 60, "bonus_score": 5}, 5, 100, 65), ({"task1": 0}, 0, 0, 0)])
def test_course_page_payload_includes_authorized_score_maximum(
    app, mock_gitlab_oauth, monkeypatch, page, template, score_case
):
    scores, bonus_score, maximum, total_score = score_case
    monkeypatch.setitem(ui.PAGE_SERIALIZERS, template, ("assignments", lambda _context: {}))
    app.oauth = mock_gitlab_oauth
    with (
        patch.object(app.storage_api, "get_scores", return_value=scores),
        patch.object(app.storage_api, "get_bonus_score", return_value=bonus_score),
        patch.object(app.storage_api, "max_score_started", return_value=maximum),
        app.test_client() as client,
    ):
        set_session(client, build_test_session(include_manytask=True))
        response = client.get(f"/{TEST_COURSE_NAME}/{page}")
    assert response.status_code == HTTPStatus.OK
    assert ui_payload(response)["shared"]["course"] == {
        "name": TEST_COURSE_NAME,
        "status": "in_progress",
        "score": total_score,
        "bonusScore": bonus_score,
        "maxStartedScore": maximum,
    }


def test_database_page_offers_personal_task_order_in_react_payload(app, mock_gitlab_oauth):
    CSRFProtect(app)
    app.oauth = mock_gitlab_oauth
    with app.test_client() as client:
        set_session(client, build_test_session(include_manytask=True))
        response = client.get(f"/{TEST_COURSE_NAME}/database")
    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["page"] == "grades"
    assert payload["data"]["courseName"] == TEST_COURSE_NAME
    assert payload["shared"]["username"] == TEST_USERNAME
    assert "students" not in payload["data"]
    assert b"tabulator" not in response.data.lower()


def test_course_assignments_page_uses_react_payload(app, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    with app.test_client() as client:
        set_session(client, build_test_session(include_manytask=True))
        response = client.get(f"/{TEST_COURSE_NAME}/")
    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["page"] == "assignments"
    assert payload["data"]["courseName"] == TEST_COURSE_NAME
    assert payload["data"]["groups"] == []
    assert payload["shared"]["username"] == TEST_USERNAME


def test_course_page_uses_rms_username_for_project_existence_check(app, mock_gitlab_oauth):
    """Regression for the SourceCraft ``SlugIsNotAvailable`` 500 on enrollment.

    ``check_project_exists`` must be called with the RMS-native username (as stored in
    ``session['rms']['username']``), not the auth-provider login (``session['auth']['username']``).
    Otherwise, for users whose SC username differs from their Yandex login (e.g. Yandex ``Ps5``
    -> SC ``ps5-1``), the existence check produces a false negative and the flow redirects to
    ``create_project``, which 500s trying to re-create the already-existing repo.
    """
    CSRFProtect(app)
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.rms_api, "check_project_exists", return_value=False) as mock_check,
        ):
            # Simulate divergent identities: auth session has Yandex login, RMS session has SC username.
            session_data = build_test_session()
            session_data["rms"]["username"] = "ps5-1"
            session_data["auth"]["username"] = "Ps5"
            session_data["manytask"] = {
                "version": 1.0,
                "user_id": TEST_USER_ID,
                "username": "Ps5",  # stored username is auth login
            }
            with client.session_transaction() as sess:
                sess.update(session_data)
            app.oauth = mock_gitlab_oauth

            client.get(f"/{TEST_COURSE_NAME}/")

            mock_check.assert_called_once()
            call_kwargs = mock_check.call_args.kwargs
            assert call_kwargs["project_name"] == "ps5-1", (
                "Existence check must use the RMS-native username so the slug matches what "
                "create_project builds; got the auth login instead, which is the reported bug."
            )


def test_signup_get(app):
    CSRFProtect(app)
    with app.test_request_context():
        response = app.test_client().get("/signup")
        assert response.status_code == HTTPStatus.OK


def test_signup_invalid_csrf_renders_error_without_full_template_context(app):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["auth"] = {"access_token": "session-token-sentinel"}
        response = client.post(
            "/signup", data={"csrf_token": "invalid", "username": "alice", "password": "password-sentinel"}
        )
    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["page"] == "signup"
    assert payload["shared"]["errorMessage"] == "CSRF Error"
    assert payload["data"]["values"] == {"username": "alice"}
    assert "session-token-sentinel" not in str(payload)
    assert "password-sentinel" not in str(payload)


def test_signup_get_disabled_redirects_to_login(app):
    CSRFProtect(app)
    app.app_config.disable_signup = True
    with app.test_request_context():
        response = app.test_client().get("/signup")
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.login")


def test_signup_post_password_mismatch(app, mock_course):
    CSRFProtect(app)
    with app.test_client() as client:
        response = client.get("/signup")
        csrf_token = ui_payload(response)["shared"]["csrfToken"]

        response = client.post(
            "/signup",
            data={
                "csrf_token": csrf_token,
                "username": TEST_USERNAME,
                "firstname": "Test",
                "lastname": "User",
                "email": "test@example.com",
                "password": "password123",
                "password2": "password456",
                "secret": mock_course.registration_secret,
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert ui_payload(response)["shared"]["errorMessage"] == "Passwords don't match"


def test_logout(app):
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth"] = {"version": TEST_GITLAB_SESSION_VERSION, "username": TEST_USERNAME}
            response = client.get("/logout")
            assert response.status_code == HTTPStatus.FOUND
            assert response.headers["Location"] == "/"
            with client.session_transaction() as sess:
                assert "auth" not in sess


def test_index_shows_profile_menu(app, mock_gitlab_oauth):
    """
    The course list page should show the user menu
    """
    CSRFProtect(app)
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["auth"] = {
                    "version": TEST_GITLAB_SESSION_VERSION,
                    "username": TEST_USERNAME,
                    "user_auth_id": TEST_USER_ID,
                    "access_token": TEST_TOKEN,
                    "refresh_token": TEST_TOKEN,
                }
                sess["rms"] = {
                    "version": TEST_CLIENT_PROFILE_SESSION_VERSION,
                    "rms_id": TEST_RMS_ID,
                    "username": TEST_USERNAME,
                }
                sess["manytask"] = {
                    "version": 1.5,
                    "user_id": TEST_USER_ID,
                    "username": TEST_USERNAME,
                }
            app.oauth = mock_gitlab_oauth
            response = client.get("/")
            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            assert payload["shared"]["username"] == TEST_USERNAME
            assert payload["shared"]["urls"]["updateProfile"] == "/update_profile"


def test_profile_csrf_error_renders_course_directory_without_full_context(app, mock_gitlab_oauth):
    """A failed profile POST has only error_message and must still render the directory."""
    CSRFProtect(app)
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth
            csrf_token = ui_payload(client.get("/"))["shared"]["csrfToken"]
            with patch("manytask.web.validate_csrf", side_effect=ValidationError("expired")):
                response = client.post(
                    "/update_profile",
                    data={"username": TEST_USERNAME, "first_name": "A", "last_name": "B", "csrf_token": csrf_token},
                )
    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["page"] == "courses"
    assert payload["shared"]["errorMessage"] == "CSRF Error"
    assert payload["data"]["courses"] == []
    assert payload["data"]["adminNamespaces"] == []
    assert payload["data"]["createCourseUrl"] is None


def test_index_renders_list_and_table_views(app, mock_gitlab_oauth):
    """The course directory payload keeps the allowed course and lifecycle order."""
    CSRFProtect(app)
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth
            response = client.get("/")
            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            assert payload["page"] == "courses"
            assert payload["data"]["courses"] == [
                {
                    "name": "test_course_names",
                    "status": "created",
                    "href": "/test_course_names/",
                    "owners": "",
                    "namespaceSlug": "",
                    "editHref": None,
                }
            ]
            assert payload["data"]["statusOrder"] == [status.value for status in CourseStatus]
            assert "tabulator" not in response.data.decode().lower()


def test_index_edit_flag_hidden_for_regular_user(app, mock_gitlab_oauth):
    """A regular user must not receive an editable course in the table data."""
    CSRFProtect(app)
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth
            response = client.get("/")
            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            assert payload["data"]["courses"][0]["editHref"] is None
            assert payload["data"]["createCourseUrl"] is None
            assert payload["data"]["instanceAdminUrl"] is None
            assert payload["data"]["namespacesUrl"] is None
            assert payload["data"]["adminNamespaces"] == []
            assert "/instance_admin/courses/test_course_names/edit" not in str(payload)


def test_index_edit_flag_present_for_instance_admin(app, mock_gitlab_oauth):
    """An instance admin sees an editable course in the table data."""
    CSRFProtect(app)
    app.storage_api.stored_user.instance_admin = True
    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth
            response = client.get("/")
            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            assert payload["data"]["courses"][0]["editHref"] == "/instance_admin/courses/test_course_names/edit"
            assert payload["data"]["createCourseUrl"] == "/instance_admin/courses/new"
            assert payload["data"]["instanceAdminUrl"] == "/instance_admin/panel"


def test_index_renders_namespace_table_for_namespace_admin(app, mock_gitlab_oauth):
    CSRFProtect(app)
    namespace = MockCourseBase()
    namespace.id = 1
    namespace.name = "Test namespace"
    namespace.slug = "test-namespace"
    namespace.description = "Namespace description"
    namespace.gitlab_group_id = 1

    app.storage_api.get_namespace_admin_namespaces = lambda _username: [namespace.id]
    app.storage_api.get_user_namespaces = lambda _username: [(namespace, "namespace_admin")]
    app.storage_api.get_namespace_users = lambda _namespace_id: [1, 2]
    app.storage_api.get_namespace_courses = lambda _namespace_id: [{"name": "course"}]

    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth

            response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["data"]["adminNamespaces"] == [
        {
            "id": 1,
            "name": "Test namespace",
            "href": "/instance_admin/namespaces/1",
            "slug": "test-namespace",
            "description": "Namespace description",
            "coursesCount": 1,
            "usersCount": 2,
        }
    ]
    assert payload["data"]["namespacesUrl"] == "/instance_admin/namespaces"
    assert payload["data"]["instanceAdminUrl"] is None


def test_index_renders_namespace_table_for_instance_admin(app, mock_gitlab_oauth):
    CSRFProtect(app)
    namespace = MockCourseBase()
    namespace.id = 1
    namespace.name = "Test namespace"
    namespace.slug = "test-namespace"
    namespace.description = None
    namespace.gitlab_group_id = 1

    app.storage_api.stored_user.instance_admin = True
    app.storage_api.get_all_namespaces = lambda: [namespace]
    app.storage_api.get_namespace_users = lambda _namespace_id: []
    app.storage_api.get_namespace_courses = lambda _namespace_id: []

    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth

            response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["data"]["adminNamespaces"][0]["name"] == "Test namespace"
    assert payload["data"]["instanceAdminUrl"] == "/instance_admin/panel"


def test_namespace_admin_can_access_namespace_panel(app, mock_gitlab_oauth):
    """Namespace admins can open the panel where they manage their namespace."""
    namespace = MockCourseBase()
    namespace.id = 1
    namespace.name = "Test namespace"
    namespace.slug = "test-namespace"
    namespace.description = None
    namespace.gitlab_group_id = 1

    app.storage_api.get_namespace_by_id = lambda _namespace_id, _username: (namespace, "namespace_admin")
    app.storage_api.get_namespace_users = lambda _namespace_id: []
    app.storage_api.get_namespace_courses = lambda _namespace_id: []
    app.storage_api.get_all_users = lambda: []

    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth

            response = client.get(f"/instance_admin/namespaces/{namespace.id}")

    assert response.status_code == HTTPStatus.OK


def test_namespace_admin_cannot_access_another_namespace_panel(app, mock_gitlab_oauth):
    """Namespace admin access is limited to the requested namespace."""
    app.storage_api.get_namespace_by_id = lambda namespace_id, _username: (
        MockCourseBase(),
        "namespace_admin" if namespace_id == 1 else "program_manager",
    )

    with app.test_request_context():
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth

            response = client.get("/instance_admin/namespaces/2")

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert b"manytask-page" not in response.data
    assert b"availableUsers" not in response.data


def test_not_ready(app):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.storage_api, "check_if_instance_admin") as mock_check_if_instance_admin,
        ):
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            mock_check_if_instance_admin.return_value = True
            response = client.get(f"/{TEST_COURSE_NAME}/not_ready")
            assert response.status_code == HTTPStatus.FOUND


def test_not_ready_anonymous(app, mock_course):
    """Anonymous users (no session) must see the not_ready page, not a 500."""
    with app.test_request_context():
        with patch.object(mock_course, "status", CourseStatus.CREATED):
            response = app.test_client().get(f"/{TEST_COURSE_NAME}/not_ready")
            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            assert payload["page"] == "not-ready"
            assert payload["data"]["links"] == [
                {"label": "Refresh", "href": f"/{TEST_COURSE_NAME}/"},
                {"label": "Back to courses list", "href": "/"},
            ]
            assert "auth" not in response.get_data(as_text=True)
            assert "access_token" not in response.get_data(as_text=True)
            soup = BeautifulSoup(response.data, "html.parser")
            assert soup.select_one('script[type="module"]')["src"].startswith("/static/dist/assets/main-")
            assert soup.select_one('link[rel="stylesheet"]')["href"].startswith("/static/dist/assets/main-")


def test_not_ready_admin_actions_follow_server_permissions(app, mock_course):
    with (
        patch.object(mock_course, "status", CourseStatus.CREATED),
        patch("manytask.web.check_if_current_user_is_instance_admin", return_value=True),
        patch("manytask.web.has_role", return_value=True),
        app.test_client() as client,
    ):
        with client.session_transaction() as sess:
            sess.update(build_test_session(include_manytask=True))
        response = client.get(f"/{TEST_COURSE_NAME}/not_ready")

    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["data"]["links"] == [
        {"label": "Refresh", "href": f"/{TEST_COURSE_NAME}/"},
        {"label": "Back to courses list", "href": "/"},
        {"label": "Back to editing course", "href": f"/instance_admin/courses/{TEST_COURSE_NAME}/edit"},
        {"label": "Instance Admin panel", "href": "/instance_admin/panel"},
    ]
    assert payload["shared"]["capabilities"]["canEditCourse"] is True
    assert "access_token" not in response.get_data(as_text=True)


def test_not_ready_namespace_admin_capability(app, mock_course):
    with (
        patch.object(mock_course, "status", CourseStatus.CREATED),
        patch("manytask.web.check_if_current_user_is_instance_admin", return_value=False),
        patch("manytask.web.has_role", return_value=True),
        app.test_client() as client,
    ):
        with client.session_transaction() as sess:
            sess.update(build_test_session(include_manytask=True))
        response = client.get(f"/{TEST_COURSE_NAME}/not_ready")

    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["shared"]["capabilities"]["namespaceAdmin"] is True
    assert payload["shared"]["capabilities"]["instanceAdmin"] is False
    assert all(link["label"] != "Instance Admin panel" for link in payload["data"]["links"])


def test_not_ready_flashes_are_delivered_once(app, mock_course):
    with patch.object(mock_course, "status", CourseStatus.CREATED), app.test_client() as client:
        with client.session_transaction() as sess:
            sess["_flashes"] = [("error", "Retry course setup")]

        first = client.get(f"/{TEST_COURSE_NAME}/not_ready")
        second = client.get(f"/{TEST_COURSE_NAME}/not_ready")

    assert ui_payload(first)["shared"]["flashes"] == [{"category": "error", "message": "Retry course setup"}]
    assert ui_payload(second)["shared"]["flashes"] == []


def ui_payload(response):
    soup = BeautifulSoup(response.data, "html.parser")
    return json.loads(soup.select_one("#manytask-page").text)


def check_admin_in_data(response, check_true):
    assert response.status_code == HTTPStatus.OK
    if BeautifulSoup(response.data, "html.parser").select_one("#manytask-page"):
        assert ui_payload(response)["shared"]["capabilities"]["courseAdmin"] is check_true
        return
    if check_true:
        assert b'class="adm-badge' in response.data
    else:
        assert b'class="adm-badge' not in response.data


def check_admin_status_code(response, check_true):
    if check_true:
        assert response.status_code != HTTPStatus.FORBIDDEN
    else:
        assert response.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.parametrize(
    "path_and_func",
    [
        [f"/{TEST_COURSE_NAME}/", check_admin_in_data],
        [f"/{TEST_COURSE_NAME}/database", check_admin_in_data],
    ],
)
@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("get_param_admin", ["true", "1", "yes", None, "false", "0", "no", "random_value"])
def test_course_page_user_sync(app, mock_gitlab_oauth, mock_course, path_and_func, debug, get_param_admin):
    path, check_func = path_and_func
    CSRFProtect(app)

    if get_param_admin is not None:
        path += f"?admin={get_param_admin}"

    with app.test_request_context():
        with app.test_client() as client:
            set_session(client, build_test_session())

            app.oauth = mock_gitlab_oauth
            app.debug = debug

            # not instance admin, not course admin
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, False)

            set_session(client, build_test_session())

            app.storage_api.course_admin = True

            # not instance admin, but course admin
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)

            set_session(client, build_test_session())

            app.storage_api.course_admin = False
            app.storage_api.stored_user.instance_admin = True

            # instance admin => course admin
            response = client.get(path)

            if app.debug:
                # in debug admin flag is the same as get param
                check_func(response, get_param_admin in ("true", "1", "yes", None))
            else:
                check_func(response, True)


def test_signup_post_success(app, mock_gitlab_oauth, mock_storage_api, mock_course):
    CSRFProtect(app)
    data = {
        "username": TEST_USERNAME_1,
        "firstname": TEST_FIRST_NAME_1,
        "lastname": TEST_LAST_NAME_1,
        "email": "test@example.com",
        "password": "password",
        "password2": "password",
    }

    with (
        patch.object(mock_gitlab_oauth.auth_provider, "authorize_access_token") as mock_authorize_access_token,
        patch.object(mock_storage_api, "update_or_create_user") as mock_register_new_mt_user,
        # app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }
        with app.test_client() as client:
            response = client.get("/signup")
            csrf_token = ui_payload(response)["shared"]["csrfToken"]
            data["csrf_token"] = csrf_token
            response = client.post(url_for("root.signup", course_name=TEST_COURSE_NAME), data=data)
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == url_for("root.login")

            rms_user = app.rms_api.get_rms_user_by_username(TEST_USERNAME_1)

            mock_register_new_mt_user.assert_called_once_with(
                username=TEST_USERNAME_1,
                first_name=TEST_FIRST_NAME_1,
                last_name=TEST_LAST_NAME_1,
                rms_id=rms_user.id,
                auth_id=int(rms_user.id),
            )


def test_login_get_redirect_to_gitlab(app, mock_gitlab_oauth):
    with app.test_request_context():
        app.oauth = mock_gitlab_oauth

        with (
            patch.object(mock_gitlab_oauth.auth_provider, "authorize_redirect") as mock_authorize_redirect,
            app.test_request_context(),
        ):
            app.test_client().get(url_for("root.login"))
            mock_authorize_redirect.assert_called_once()
            args, _ = mock_authorize_redirect.call_args
            assert args[0] == url_for("root.login_finish", _external=True)


def test_login_finish_get_with_code(app, mock_gitlab_oauth):
    with (
        patch.object(app.auth_api, "get_authenticated_user") as mock_get_authenticated_user,
        patch.object(mock_gitlab_oauth.auth_provider, "authorize_access_token") as mock_authorize_access_token,
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth

        mock_get_authenticated_user.return_value = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
        mock_authorize_access_token.return_value = {
            "access_token": "test_token",
            "refresh_token": "test_token",
        }

        response = app.test_client().get(url_for("root.login_finish"), query_string={"code": "test_code"})

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.signup_finish")

        mock_authorize_access_token.assert_called_once()

        mock_get_authenticated_user.assert_called_once()
        args, _ = mock_get_authenticated_user.call_args
        assert args[0] == "test_token"


def test_login_oauth_error(app, mock_gitlab_oauth):
    with (
        patch.object(mock_gitlab_oauth.auth_provider, "authorize_access_token", side_effect=OAuthError("OAuth error")),
        app.test_request_context(),
    ):
        app.oauth = mock_gitlab_oauth
        response = app.test_client().get(url_for("root.login"), query_string={"code": "test_code"})
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == url_for("root.index")


def test_signup_finish_with_valid_session(app, mock_gitlab_oauth):
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.storage_api, "get_stored_user_by_auth_id") as mock_get_stored_user_by_auth_id,
        ):
            with client.session_transaction() as sess:
                sess.update(build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth
            response = client.post(url_for("root.signup_finish"))
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == url_for("root.index")
            mock_get_stored_user_by_auth_id.assert_not_called()


def test_signup_finish_with_existing_user_in_db(app, mock_gitlab_oauth):
    with app.test_request_context():
        with (
            app.test_client() as client,
        ):
            set_session(client, build_test_session(include_rms=False))
            app.oauth = mock_gitlab_oauth
            response = client.post(url_for("root.signup_finish"))
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == url_for("root.index")

            with client.session_transaction() as sess:
                assert "version" in sess["rms"]
                assert sess["rms"]["username"] == TEST_USERNAME


def test_signup_finish_existing_user_uses_rms_username_not_auth_login(app, mock_gitlab_oauth):
    """Regression: on stale-session restoration, ``session['rms']['username']`` must be the
    RMS-native username (fetched from the RMS API by ``rms_id``), not the auth-provider login.

    On SourceCraft the two can differ (e.g. Yandex login ``Ps5`` vs SC username ``ps5-1`` when
    the natural slug is taken). Aliasing the auth login here poisons downstream slug lookups
    such as ``check_project_exists`` and eventually surfaces as a 500 ``SlugIsNotAvailable``
    from ``create_project``.
    """
    from manytask.abstract import RmsUser as _RmsUser
    from tests.constants import TEST_RMS_ID as _TEST_RMS_ID

    # Simulate SourceCraft assigning a fallback slug: auth login differs from RMS username.
    app.rms_api.users[_TEST_RMS_ID] = _RmsUser(id=_TEST_RMS_ID, username="ps5-1", name="Test User")

    with app.test_request_context():
        with app.test_client() as client:
            set_session(client, build_test_session(include_rms=False))
            app.oauth = mock_gitlab_oauth
            response = client.post(url_for("root.signup_finish"))
            assert response.status_code == HTTPStatus.FOUND

            with client.session_transaction() as sess:
                # RMS-native username was fetched from the API, not aliased from auth session.
                assert sess["rms"]["username"] == "ps5-1"
                assert sess["auth"]["username"] == TEST_USERNAME  # sanity: auth login unchanged


def test_signup_finish_with_new_user_in_db(app, mock_gitlab_oauth):
    CSRFProtect(app)
    data = {
        "firstname": "Test",
        "lastname": "User",
    }

    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(app.storage_api, "get_stored_user_by_auth_id") as mock_get_stored_user_by_auth_id,
            patch.object(app.storage_api, "update_or_create_user") as mock_update_or_create_user,
        ):
            set_session(client, build_test_session(include_rms=False))
            app.oauth = mock_gitlab_oauth
            mock_get_stored_user_by_auth_id.side_effect = [None, None, app.storage_api.stored_user]

            response = client.get(url_for("root.signup_finish"))
            csrf_token = ui_payload(response)["shared"]["csrfToken"]
            data["csrf_token"] = csrf_token
            response = client.post(url_for("root.signup_finish"), data=data)
            assert response.status_code == HTTPStatus.FOUND
            assert response.location == url_for("root.index")

            with client.session_transaction() as sess:
                assert "version" in sess["rms"]
                assert sess["rms"]["username"] == TEST_USERNAME
                rms_id = sess["rms"]["rms_id"]

            mock_update_or_create_user.assert_called_once_with(
                username=TEST_USERNAME,
                first_name="Test",
                last_name="User",
                rms_id=rms_id,
                auth_id=TEST_USER_ID,
            )


# ----- Course access table on the edit page -----


def _get_edit_course_page(app, mock_gitlab_oauth, course_users=None):
    """Open the course edit page as an instance admin and return its page data."""
    CSRFProtect(app)  # the settings form renders a csrf_token
    app.storage_api.stored_user.instance_admin = True
    app.storage_api.course_admin = True  # required by the requires_course_admin guard
    app.storage_api.get_course_users_with_admin_status = lambda _course_name: course_users or []

    with app.test_request_context(), app.test_client() as client:
        app.oauth = mock_gitlab_oauth
        set_session(client, build_test_session(include_manytask=True))
        response = client.get(url_for("instance_admin.edit_course", course_name=TEST_COURSE_NAME))
        assert response.status_code == HTTPStatus.OK
        soup = BeautifulSoup(response.data, "html.parser")
        return json.loads(soup.find(id="manytask-page").text)["data"]


def test_edit_course_renders_access_table(app, mock_gitlab_oauth):
    data = _get_edit_course_page(app, mock_gitlab_oauth)
    assert data["accessUrls"] == {
        "users": f"/api/{TEST_COURSE_NAME}/access_users",
        "courseAdmin": f"/api/{TEST_COURSE_NAME}/course_admin",
    }


def test_edit_course_serializes_enrolled_nonadmin_candidate(app, mock_gitlab_oauth):
    member = SimpleNamespace(username="alice", first_name="Alice", last_name="A", email="private@example.com")
    data = _get_edit_course_page(app, mock_gitlab_oauth, [(member, False)])
    assert data["courseUsers"] == [{"username": "alice", "firstName": "Alice", "lastName": "A"}]
    assert "private@example.com" not in str(data)


def test_edit_course_has_no_program_manager_control(app, mock_gitlab_oauth):
    """Program managers are managed on the namespace panel, not from the course page."""
    data = _get_edit_course_page(app, mock_gitlab_oauth)
    assert "programManager" not in data.get("accessUrls", {})


def test_create_course_native_post_namespace_zero_redirects(app, mock_gitlab_oauth):
    app.storage_api.check_if_instance_admin = lambda _username: True
    saved = []
    app.storage_api.create_course = lambda settings: saved.append(settings) or True
    app.oauth = mock_gitlab_oauth
    with app.test_client() as client, patch("manytask.web.validate_csrf"):
        set_session(client, build_test_session(include_manytask=True))
        response = client.post("/instance_admin/courses/new", data={
            "csrf_token": "token", "namespace_id": "0", "unique_course_name": "new-course",
            "registration_secret": "join", "token": "admin-secret", "show_allscores": "on",
            "course_group": "new-course", "course_public_repo": "new-course/public-2026-fall",
            "course_students_group": "new-course/students-2026-fall", "default_branch": "main",
        })
    assert response.status_code == HTTPStatus.FOUND
    assert response.location.endswith("/new-course/")
    assert len(saved) == 1
    assert saved[0].namespace_id is None
    assert saved[0].token == "admin-secret"


def test_create_course_native_post_regular_user_is_forbidden_before_rms(app, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    app.storage_api.check_if_instance_admin = lambda _username: False
    with app.test_client() as client, patch.object(app.rms_api, "create_course_group") as create_group:
        set_session(client, build_test_session(include_manytask=True))
        response = client.post("/instance_admin/courses/new", data={"namespace_id": "0"})
    assert response.status_code == HTTPStatus.FORBIDDEN
    create_group.assert_not_called()


def test_create_course_bad_csrf_keeps_values_without_creating_resources(app, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    app.create_course_labels = {}
    app.storage_api.check_if_instance_admin = lambda _username: True
    with (
        app.test_client() as client,
        patch.object(app.rms_api, "create_course_group") as create_group,
        patch.object(app.rms_api, "create_public_repo") as create_public_repo,
        patch.object(app.rms_api, "create_students_group") as create_students_group,
        patch.object(app.storage_api, "create_course", create=True) as create_course,
    ):
        set_session(client, build_test_session(include_manytask=True))
        response = client.post("/instance_admin/courses/new", data={
            "csrf_token": "bad", "namespace_id": "0", "unique_course_name": "draft-course",
            "registration_secret": "draft-secret", "token": "draft-token",
            "course_group": "draft-group", "course_public_repo": "draft-group/public",
            "course_students_group": "draft-group/students", "default_branch": "dev",
        })
    assert response.status_code == HTTPStatus.OK
    payload = json.loads(BeautifulSoup(response.data, "html.parser").find(id="manytask-page").text)
    assert payload["shared"]["errorMessage"] == "CSRF Error"
    assert payload["data"]["values"] == {
        "namespace_id": "0", "unique_course_name": "draft-course", "registration_secret": "draft-secret",
        "token": "draft-token", "course_group": "draft-group", "course_public_repo": "draft-group/public",
        "course_students_group": "draft-group/students", "default_branch": "dev",
    }
    create_group.assert_not_called()
    create_public_repo.assert_not_called()
    create_students_group.assert_not_called()
    create_course.assert_not_called()


def test_create_course_native_post_foreign_namespace_is_denied_before_rms(app, mock_gitlab_oauth):
    app.oauth = mock_gitlab_oauth
    app.create_course_labels = {}
    app.storage_api.check_if_instance_admin = lambda _username: False
    app.storage_api.get_namespace_admin_namespaces = lambda _username: [4]
    with app.test_client() as client, patch("manytask.web.validate_csrf"), patch.object(
        app.rms_api, "create_course_group"
    ) as create_group:
        set_session(client, build_test_session(include_manytask=True))
        response = client.post("/instance_admin/courses/new", data={"namespace_id": "999"})
    assert response.status_code == HTTPStatus.OK
    payload = json.loads(BeautifulSoup(response.data, "html.parser").find(id="manytask-page").text)
    assert payload["shared"]["errorMessage"] == "Namespace not found or access denied"
    create_group.assert_not_called()


def test_edit_course_bad_csrf_keeps_form_values_and_server_token(app, mock_gitlab_oauth, mock_course):
    app.oauth = mock_gitlab_oauth
    mock_course.token = "server-token"
    app.storage_api.course_admin = True
    app.storage_api.get_course_users_with_admin_status = lambda _course: []
    with app.test_client() as client:
        set_session(client, build_test_session(include_manytask=True))
        response = client.post(f"/instance_admin/courses/{TEST_COURSE_NAME}/edit", data={
            "csrf_token": "bad", "registration_secret": "draft", "token": "forged",
            "gitlab_course_public_repo": "draft/public",
        })
    assert response.status_code == HTTPStatus.OK
    soup = BeautifulSoup(response.data, "html.parser")
    payload = json.loads(soup.find(id="manytask-page").text)
    assert payload["shared"]["errorMessage"] == "CSRF Error"
    assert payload["data"]["values"]["registration_secret"] == "draft"
    assert payload["data"]["values"]["gitlab_course_public_repo"] == "draft/public"
    assert payload["data"]["values"]["token"] == app.storage_api.get_course(TEST_COURSE_NAME).token


def test_create_project_renders_error_instead_of_500_when_rms_fails(app, mock_course, mock_gitlab_oauth):
    """Regression: a failing RMS must not blow up the enrollment form with a 500.

    ``create_project`` used to catch only ``gitlab.GitlabError``. Every RMS backend raises
    ``RmsApiException`` instead, so on SourceCraft any backend failure (exhausted cloud quota,
    taken slug, API outage) escaped the handler and Flask returned a bare 500. Students saw a
    broken page with no idea whether it was their fault.
    """
    CSRFProtect(app)
    mock_course.token = TEST_TOKEN
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(
                app.rms_api,
                "create_project",
                side_effect=RmsApiException("Failed to create repo: {'error_code': 'ResourceExhausted'}"),
            ),
        ):
            set_session(client, build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth

            response = client.get(f"/{TEST_COURSE_NAME}/create_project")
            csrf_token = ui_payload(response)["shared"]["csrfToken"]

            response = client.post(
                f"/{TEST_COURSE_NAME}/create_project",
                data={"csrf_token": csrf_token, "secret": mock_course.registration_secret},
            )

            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            # The user stays on the enrollment form, not on the signup page.
            assert payload["page"] == "create-project"
            # Backend-internal detail is logged, not shown.
            assert "ResourceExhausted" not in str(payload)
            assert "course staff" in payload["shared"]["errorMessage"]


def test_create_project_still_reports_gitlab_errors(app, mock_course, mock_gitlab_oauth):
    """The GitLab path keeps surfacing its own message, now on the create_project page."""
    CSRFProtect(app)
    mock_course.token = TEST_TOKEN
    with app.test_request_context():
        with (
            app.test_client() as client,
            patch.object(
                app.rms_api,
                "create_project",
                side_effect=gitlab.GitlabError("boom", response_code=403),
            ),
        ):
            set_session(client, build_test_session(include_manytask=True))
            app.oauth = mock_gitlab_oauth

            response = client.get(f"/{TEST_COURSE_NAME}/create_project")
            csrf_token = ui_payload(response)["shared"]["csrfToken"]

            response = client.post(
                f"/{TEST_COURSE_NAME}/create_project",
                data={"csrf_token": csrf_token, "secret": mock_course.registration_secret},
            )

            assert response.status_code == HTTPStatus.OK
            payload = ui_payload(response)
            assert "boom" in payload["shared"]["errorMessage"]
            assert payload["page"] == "create-project"


@pytest.mark.parametrize("is_admin", [False, True])
def test_grades_payload_and_api_keep_personal_data_admin_only(app, mock_gitlab_oauth, is_admin):
    app.oauth = mock_gitlab_oauth
    student = StudentCourseScores(
        username="student",
        first_name="Private first",
        last_name="Private last",
        task_scores={"negative.score": TaskScore(-3, False), "zero": TaskScore(0, False)},
        comment="Private comment",
    )
    staff = StudentCourseScores(username="staff", first_name="Staff", last_name="Admin", is_admin=True)
    with (
        patch.object(app.storage_api, "check_if_course_admin", return_value=is_admin),
        patch.object(app.storage_api, "get_all_scores_with_names", return_value={"student": student, "staff": staff}),
        app.test_client() as client,
    ):
        set_session(client, build_test_session(include_manytask=True))
        page = client.get(f"/{TEST_COURSE_NAME}/database")
        response = client.get(f"/api/{TEST_COURSE_NAME}/database")
    assert response.status_code == HTTPStatus.OK
    assert ui_payload(page)["data"]["canEdit"] is is_admin
    assert "Private" not in page.get_data(as_text=True)
    rows = response.get_json()["students"]
    assert [row["username"] for row in rows] == (["student", "staff"] if is_admin else ["student"])
    assert rows[0]["scores"] == {"negative.score": -3, "zero": 0}
    assert rows[0]["total_score"] == -3  # noqa: PLR2004
    for field in ("first_name", "last_name", "repo_url", "comment"):
        assert (field in rows[0]) is is_admin


def test_instance_admin_invalid_csrf_returns_react_error_without_private_users(app, mock_gitlab_oauth):
    app.storage_api.stored_user.instance_admin = True
    app.oauth = mock_gitlab_oauth
    with app.test_client() as client, patch("manytask.web.validate_csrf", side_effect=ValidationError("expired")):
        with client.session_transaction() as sess:
            sess.update(build_test_session(include_manytask=True))
        response = client.post(
            "/instance_admin/panel", data={"csrf_token": "bad", "action": "grant", "username": "target"}
        )
    assert response.status_code == HTTPStatus.OK
    payload = ui_payload(response)
    assert payload["page"] == "instance-admin"
    assert payload["shared"]["errorMessage"] == "CSRF Error"
    assert payload["data"]["users"] == []
    assert payload["data"]["namespaces"] == []

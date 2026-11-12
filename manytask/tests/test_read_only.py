from dataclasses import replace
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from flask import redirect, render_template, url_for
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from manytask.abstract import AuthenticatedUser, StoredUser
from manytask.course import CourseConfig, CourseStatus
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.local_config import DebugLocalConfig, LocalConfig
from manytask.local_config import TestConfig as ManytaskTestConfig
from manytask.main import create_app
from manytask.mock_auth import MockAuthApi
from manytask.models import User
from manytask.read_only import READ_ONLY_MESSAGE, ReadOnlyModeError
from manytask.utils.rms_settings import reconcile_course_rms_settings, schedule_rms_settings_reconcile
from tests.constants import TEST_USER_ID, TEST_USERNAME
from tests.helpers import build_test_session, set_session


@pytest.fixture
def read_only_app(monkeypatch):
    monkeypatch.setenv("MANYTASK_READ_ONLY", "true")
    with patch("manytask.main._database_storage_setup", return_value=MagicMock()):
        app = create_app(test=True)
    app.rms_api = MagicMock()
    app.auth_api = MockAuthApi()
    app.auth_api.user = AuthenticatedUser(id=TEST_USER_ID, username=TEST_USERNAME)
    return app


@pytest.mark.parametrize("enabled", ["true", "1", "yes", "TRUE", "false", "0", "no"])
def test_flag_is_loaded_in_every_configuration(monkeypatch, enabled):
    monkeypatch.setenv("MANYTASK_READ_ONLY", enabled)
    expected = enabled.lower() in {"true", "1", "yes"}
    assert LocalConfig.from_env().read_only is expected
    assert DebugLocalConfig.from_env().read_only is expected
    assert ManytaskTestConfig().read_only is expected


def test_default_configuration_is_writable(monkeypatch):
    monkeypatch.delenv("MANYTASK_READ_ONLY", raising=False)
    assert LocalConfig.from_env().read_only is False


def test_every_mutating_route_is_rejected_before_csrf_or_side_effects(read_only_app):
    client = read_only_app.test_client()
    for rule in read_only_app.url_map.iter_rules():
        if rule.endpoint == "root.login":
            continue
        values = {name: 1 if name.endswith("_id") else "course" for name in rule.arguments}
        with read_only_app.test_request_context():
            url = url_for(rule.endpoint, **values)
        for method in rule.methods - {"GET", "HEAD", "OPTIONS"}:
            response = client.open(url, method=method)
            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE, (rule, method, response.data)
            assert response.headers["Cache-Control"] == "no-store"
            if url.startswith("/api/"):
                assert response.json == {"error": READ_ONLY_MESSAGE, "code": "read_only"}
            else:
                assert READ_ONLY_MESSAGE.encode() in response.data
    assert not read_only_app.storage_api.mock_calls
    assert not read_only_app.rms_api.mock_calls


def test_healthcheck_and_existing_user_login_still_work(read_only_app):
    client = read_only_app.test_client()
    assert client.get("/healthcheck").status_code == HTTPStatus.OK
    read_only_app.config["WTF_CSRF_ENABLED"] = False
    with patch.object(read_only_app.oauth.auth_provider, "authorize_redirect", return_value=redirect("/provider")):
        assert client.get("/login").location == "/provider"
        assert client.post("/login").location == "/provider"

    read_only_app.storage_api.get_stored_user_by_auth_id.return_value = StoredUser(
        user_id=TEST_USER_ID,
        username=TEST_USERNAME,
        first_name="Test",
        last_name="User",
        rms_id="123",
        auth_id=TEST_USER_ID,
        instance_admin=False,
    )
    read_only_app.rms_api.get_rms_user_by_id.return_value.username = TEST_USERNAME
    set_session(client, build_test_session(include_rms=False))
    assert client.get("/signup_finish").location == "/"
    with client.session_transaction() as session:
        assert session["manytask"]["username"] == TEST_USERNAME
    read_only_app.storage_api.update_or_create_user.assert_not_called()
    read_only_app.rms_api.register_new_user.assert_not_called()
    assert client.get("/logout").status_code == HTTPStatus.FOUND


def test_registration_requires_a_preexisting_account(read_only_app):
    client = read_only_app.test_client()
    read_only_app.storage_api.get_stored_user_by_auth_id.return_value = None
    set_session(client, build_test_session(include_rms=False))
    assert client.get("/signup").location == "/login"
    response = client.get("/signup_finish")
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    read_only_app.storage_api.update_or_create_user.assert_not_called()
    read_only_app.rms_api.register_new_user.assert_not_called()


def test_banner_is_rendered_only_when_enabled(read_only_app):
    with read_only_app.test_request_context():
        html = render_template("base.html")
        assert 'id="read-only-banner"' in html
        assert READ_ONLY_MESSAGE in html
        assert "js/read-only.js" in html
        read_only_app.config["MANYTASK_READ_ONLY"] = False
        html = render_template("base.html")
        assert 'id="read-only-banner"' not in html
        assert "js/read-only.js" not in html


def test_background_reconciliation_and_config_updates_are_rejected(read_only_app):
    storage = read_only_app.storage_api
    storage.read_only = True
    for reconcile in (reconcile_course_rms_settings, schedule_rms_settings_reconcile):
        with pytest.raises(ReadOnlyModeError, match="read-only"):
            reconcile(storage, read_only_app.rms_api, "course")
    with pytest.raises(ReadOnlyModeError):
        read_only_app.store_config("course", {})
    storage.get_course.assert_not_called()
    storage.update_course.assert_not_called()
    assert not read_only_app.rms_api.mock_calls


def test_debug_startup_does_not_seed_data(monkeypatch):
    monkeypatch.setenv("MANYTASK_READ_ONLY", "true")
    with patch("manytask.main._database_storage_setup") as setup, patch("manytask.main._create_debug_course") as seed:
        app = create_app(debug=True)
    setup.assert_called_once_with(read_only=True)
    seed.assert_not_called()
    app.storage_api.update_course.assert_not_called()


def test_read_only_rejects_automatic_migrations_before_connecting():
    with patch("manytask.database.create_engine") as connect:
        with pytest.raises(ValueError, match="APPLY_MIGRATIONS"):
            DataBaseApi(DatabaseConfig("unused", "unused", read_only=True, apply_migrations=True))
    connect.assert_not_called()


@pytest.fixture
def persisted_course(postgres_container, tables):
    url = postgres_container.get_connection_url()
    writable = DataBaseApi(DatabaseConfig(url, "instance_admin"))
    writable.update_or_create_user(TEST_USERNAME, "Test", "User", "123", TEST_USER_ID)
    course = CourseConfig(
        course_name="archived_course",
        namespace_id=None,
        gitlab_course_group="course",
        gitlab_course_public_repo="course/public",
        gitlab_course_students_group="course/students",
        gitlab_default_branch="main",
        registration_secret="test-secret",
        token="test-token",
        show_allscores=True,
        status=CourseStatus.IN_PROGRESS,
    )
    writable.create_course(course)
    writable.sync_user_on_course(course.course_name, TEST_USERNAME, False)
    try:
        yield writable, course
    finally:
        writable.engine.dispose()


@pytest.fixture
def read_only_storage(persisted_course):
    writable, _ = persisted_course
    storage = DataBaseApi(DatabaseConfig(writable.database_url, "must_not_be_created", read_only=True))
    try:
        yield storage
    finally:
        storage.engine.dispose()


def test_postgres_rejects_sql_and_orm_writes_even_after_pool_reuse(read_only_storage, persisted_course):
    writable, course = persisted_course
    storage = read_only_storage
    statements = [
        "UPDATE users SET first_name = 'Changed'",
        "DELETE FROM users",
        "INSERT INTO users (username) VALUES ('must_not_be_created')",
        "CREATE TABLE must_not_be_created (id integer)",
        "TRUNCATE users CASCADE",
    ]
    for statement in statements:
        with storage.engine.begin() as connection:
            assert connection.scalar(text("SHOW transaction_read_only")) == "on"
        with pytest.raises(DBAPIError) as failure:
            with storage.engine.begin() as connection:
                connection.execute(text(statement))
        assert failure.value.orig.pgcode == "25006"

    with pytest.raises(DBAPIError) as failure:
        with storage._session_create() as session:
            user = session.scalars(select(User).where(User.username == TEST_USERNAME)).one()
            user.first_name = "Changed"
            session.commit()
    assert failure.value.orig.pgcode == "25006"
    assert writable.get_stored_user_by_username(TEST_USERNAME).first_name == "Test"
    assert {user.username for user in writable.get_all_users()} == {TEST_USERNAME, "instance_admin"}
    assert storage.get_course(course.course_name) is not None


def test_storage_rejects_mutations_before_queries(read_only_storage, persisted_course):
    _, course = persisted_course
    with patch.object(read_only_storage, "_session_create") as queries:
        for write in (
            lambda: read_only_storage.store_score(course.course_name, TEST_USERNAME, "task", lambda *args: 100),
            lambda: read_only_storage.create_course(replace(course, course_name="new_course")),
            lambda: read_only_storage.update_user_profile(TEST_USERNAME, "Changed", None),
            lambda: read_only_storage.set_instance_admin_status(TEST_USERNAME, True),
            lambda: read_only_storage.sync_user_on_course(course.course_name, TEST_USERNAME, True),
            lambda: read_only_storage.override_grade(course.course_name, TEST_USERNAME, 5),
        ):
            with pytest.raises(ReadOnlyModeError):
                write()
        queries.assert_not_called()


def test_app_starts_against_read_only_database_without_bootstrap_admin(monkeypatch, persisted_course):
    writable, _ = persisted_course
    monkeypatch.setenv("MANYTASK_READ_ONLY", "true")
    monkeypatch.setenv("DATABASE_URL", writable.database_url)
    monkeypatch.setenv("APPLY_MIGRATIONS", "false")
    monkeypatch.delenv("INITIAL_INSTANCE_ADMIN", raising=False)
    app = create_app(test=True)
    try:
        assert app.config["MANYTASK_READ_ONLY"] is True
        with app.storage_api.engine.begin() as connection:
            assert connection.scalar(text("SHOW transaction_read_only")) == "on"
        assert app.test_client().get("/healthcheck").status_code == HTTPStatus.OK
    finally:
        app.storage_api.engine.dispose()


def test_browsing_persisted_data_needs_no_rms_repairs_or_database_writes(
    read_only_app, read_only_storage, persisted_course
):
    _, course = persisted_course
    read_only_app.storage_api = read_only_storage
    client = read_only_app.test_client()
    set_session(client, build_test_session(include_manytask=True))
    with patch.object(read_only_storage, "sync_user_on_course") as sync:
        for path in (
            "/",
            f"/{course.course_name}/",
            f"/{course.course_name}/database",
            f"/api/{course.course_name}/database",
        ):
            response = client.get(path)
            assert response.status_code == HTTPStatus.OK, (path, response.data)
        sync.assert_not_called()
    read_only_app.rms_api.check_project_exists.assert_not_called()
    read_only_app.rms_api.check_user_has_repo_access.assert_not_called()
    read_only_app.rms_api.create_project.assert_not_called()


def test_pending_migrations_prevent_read_only_startup(postgres_container, tables):
    url = postgres_container.get_connection_url()
    with patch.object(DataBaseApi, "_check_pending_migrations", return_value=True):
        with pytest.raises(ValueError, match="pending migrations"):
            DataBaseApi(DatabaseConfig(url, "unused", read_only=True))

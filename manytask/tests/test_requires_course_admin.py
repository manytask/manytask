"""Tests for the ``requires_course_admin`` decorator.

These tests deliberately avoid the database/testcontainers fixtures: the
decorator only depends on ``storage_api.check_if_course_admin``, so a light
stub is enough to pin down the access rules.
"""

from http import HTTPStatus
from typing import Any

import pytest
from flask import Flask, session

from manytask.auth import requires_course_admin

COURSE = "test-course"


class _StubStorageApi:
    """Minimal storage stub recording the course admin questions asked."""

    def __init__(self, course_admins: dict[tuple[str, str], bool]) -> None:
        self.course_admins = course_admins
        self.calls: list[tuple[str, str]] = []

    def check_if_course_admin(self, course_name: str, username: str) -> bool:
        self.calls.append((course_name, username))
        return self.course_admins.get((course_name, username), False)


class _AlwaysAuthenticatedAuthApi:
    """Auth stub so ``requires_auth`` lets the request through."""

    def check_user_is_authenticated(self, *_args: Any, **_kwargs: Any) -> bool:
        return True


@pytest.fixture(autouse=True)
def _bypass_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize ``requires_auth`` internals so only authorization is tested."""
    monkeypatch.setattr("manytask.auth.valid_auth_session", lambda _session: True)
    monkeypatch.setattr("manytask.auth.valid_rms_session", lambda _session: True)
    monkeypatch.setattr("manytask.auth.valid_manytask_session", lambda _session: True)


def _make_app(course_admins: dict[tuple[str, str], bool], username: str) -> Flask:
    """Build a non-debug app with one ``requires_course_admin`` protected route."""
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"
    flask_app.storage_api = _StubStorageApi(course_admins)  # type: ignore[attr-defined]
    flask_app.auth_api = _AlwaysAuthenticatedAuthApi()  # type: ignore[attr-defined]
    flask_app.oauth = None  # type: ignore[attr-defined]

    def view(course_name: str) -> str:
        return f"edit {course_name}"

    protected = requires_course_admin(view)

    def entry(course_name: str) -> Any:
        # Seed the session the decorator reads the username from.
        session["auth"] = {"access_token": "token", "refresh_token": "refresh"}
        session["manytask"] = {"username": username, "user_id": 1, "version": 1.0}
        return protected(course_name=course_name)

    entry.__name__ = "entry"
    flask_app.add_url_rule("/courses/<course_name>/edit", view_func=entry)

    return flask_app


def test_course_admin_is_allowed() -> None:
    """A per-course admin may open the edit page."""
    flask_app = _make_app({(COURSE, "course-admin"): True}, username="course-admin")

    response = flask_app.test_client().get(f"/courses/{COURSE}/edit")

    assert response.status_code == HTTPStatus.OK
    assert response.get_data(as_text=True) == f"edit {COURSE}"


def test_non_admin_is_forbidden() -> None:
    """A plain student gets 403."""
    flask_app = _make_app({(COURSE, "course-admin"): True}, username="student")

    response = flask_app.test_client().get(f"/courses/{COURSE}/edit")

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_admin_of_another_course_is_forbidden() -> None:
    """Being admin of one course grants no access to a different course."""
    flask_app = _make_app({("some-other-course", "course-admin"): True}, username="course-admin")

    response = flask_app.test_client().get(f"/courses/{COURSE}/edit")

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_permission_is_checked_for_the_requested_course() -> None:
    """The decorator asks about the course taken from the URL."""
    flask_app = _make_app({(COURSE, "course-admin"): True}, username="course-admin")

    flask_app.test_client().get("/courses/other-course/edit")

    storage: _StubStorageApi = flask_app.storage_api  # type: ignore[attr-defined]
    assert storage.calls == [("other-course", "course-admin")]

import logging
import secrets
from functools import wraps
from typing import Any, Callable

from authlib.integrations.flask_client import OAuth
from flask import current_app, redirect, render_template, request, session, url_for
from flask.sessions import SessionMixin
from sqlalchemy.exc import NoResultFound
from werkzeug import Response

from manytask.course import Course
from manytask.glab import Student
from manytask.main import CustomFlask

logger = logging.getLogger(__name__)


def valid_session(user_session: SessionMixin) -> bool:
    SESSION_VERSION = 1.5
    return (
        "gitlab" in user_session
        and "version" in user_session["gitlab"]
        and user_session["gitlab"]["version"] >= SESSION_VERSION
        and "username" in user_session["gitlab"]
        and "user_id" in user_session["gitlab"]
        and "repo" in user_session["gitlab"]
        and "course_admin" in user_session["gitlab"]
    )


def set_oauth_session(
    student: Student, oauth_tokens: dict[str, str] | None = None, version: float = 1.5
) -> dict[str, Any]:
    """Set oauth creds in session for student"""

    result: dict[str, Any] = {
        "username": student.username,
        "user_id": student.id,
        "course_admin": student.course_admin,
        "repo": student.repo,
        "version": version,
    }
    if oauth_tokens:
        result |= {
            "access_token": oauth_tokens.get("access_token", ""),
            "refresh_token": oauth_tokens.get("refresh_token", ""),
        }
    return result


def handle_course_membership(app: CustomFlask, student: Student) -> bool | str | Response:
    """Checking user on course and sync admin role"""

    try:
        if app.storage_api.check_user_on_course(app.course_name, student):
            # sync admin flag with gitlab
            app.storage_api.sync_and_get_admin_status(app.course_name, student)
            return True
        else:
            logger.info(f"No user {student.username} on course {app.course_name} asking secret")
            return False
    except NoResultFound:
        logger.info(f"Creating User: {student.username} that we already have in gitlab")
        app.storage_api.create_user_if_not_exist(student, app.course_name)
        return redirect(url_for("web.login"))

    except Exception:
        logger.error("Failed login while working with db", exc_info=True)
        return redirect(url_for("web.signup"))


def check_secret(app: CustomFlask, student: Student) -> str | None:
    """Checking course secret for user if he is entering"""

    course: Course = app.storage_api.get_course(app.course_name)  # type: ignore

    if "secret" in request.form:
        if secrets.compare_digest(request.form["secret"], course.registration_secret):
            app.storage_api.sync_stored_user(student)
        else:
            logger.error(f"Wrong secret user {student.username} on course {app.course_name}")
            return render_template(
                "create_project.html",
                error_message="Invalid registration secret",
                course_name=app.course_name,
                course_favicon=app.favicon,
                base_url=app.gitlab_api.base_url,
            )
    return None


def handle_oauth_callback(oauth: OAuth, app: CustomFlask, course: Course) -> None | Response:
    """Process oauth2 callback with code for auth, if success set auth session"""

    try:
        gitlab_oauth_token = oauth.gitlab.authorize_access_token()
        student = app.gitlab_api.get_authenticated_student(
            gitlab_oauth_token["access_token"], course.gitlab_course_group, course.gitlab_course_students_group
        )
    except Exception:
        logger.error("Gitlab authorization failed", exc_info=True)
        return redirect(url_for("web.login"))

    session.setdefault("gitlab", {}).update(set_oauth_session(student, gitlab_oauth_token))
    session.permanent = True
    return redirect(url_for("web.login"))


def get_authenticate_student(oauth: OAuth, app: CustomFlask, course: Course) -> Student:
    """Getting student and update session"""

    try:
        student = app.gitlab_api.get_authenticated_student(
            session["gitlab"]["access_token"], course.gitlab_course_group, course.gitlab_course_students_group
        )
        session["gitlab"].update(set_oauth_session(student))
        return student

    except Exception:
        logger.error("Failed login in gitlab, redirect to login", exc_info=True)
        session.pop("gitlab", None)
        redirect_uri = url_for("web.login", _external=True)
        return oauth.gitlab.authorize_redirect(redirect_uri)


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        course: Course = app.storage_api.get_course(app.course_name)  # type: ignore
        oauth = app.oauth

        if "code" in request.args:
            return handle_oauth_callback(oauth, app, course)

        if valid_session(session):
            student = get_authenticate_student(oauth, app, course)
            check_secret(app, student)
            if not handle_course_membership(app, student):
                return render_template(
                    "create_project.html",
                    course_name=app.course_name,
                    course_favicon=app.favicon,
                    base_url=app.gitlab_api.base_url,
                )
        else:
            logger.info("Redirect to login in Gitlab")
            redirect_uri = url_for("web.login", _external=True)
            return oauth.gitlab.authorize_redirect(redirect_uri)

        return f(*args, **kwargs)

    return decorated


def requires_ready(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore
        course: Course = app.storage_api.get_course(app.course_name)  # type: ignore
        if not course.is_ready:
            return redirect(url_for("web.not_ready"))
        return f(*args, **kwargs)

    return decorated

import logging
import secrets
from functools import wraps
from typing import Any, Callable

from authlib.integrations.flask_client import OAuth
from flask import Response, abort, current_app, redirect, render_template, request, session, url_for
from flask.sessions import SessionMixin
from sqlalchemy.exc import NoResultFound
from werkzeug.wrappers.response import Response as WerkzeugResponse

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
    )


def set_oauth_session(
    student: Student, oauth_tokens: dict[str, str] | None = None, version: float = 1.5
) -> dict[str, Any]:
    """Set oauth creds in session for student"""

    result: dict[str, Any] = {
        "username": student.username,
        "user_id": student.id,
        "version": version,
    }
    if oauth_tokens:
        result |= {
            "access_token": oauth_tokens.get("access_token", ""),
            "refresh_token": oauth_tokens.get("refresh_token", ""),
        }
    return result


def handle_course_membership(course: Course, student: Student) -> bool | str | Response | WerkzeugResponse:
    """Checking user on course and sync admin role"""

    try:
        if course.storage_api.check_user_on_course(course.course_name, student):  # type: ignore
            return True
        else:
            logger.info(f"No user {student.username} on course {course.course_name} asking secret")
            return False
    except NoResultFound:
        logger.info(f"Creating User: {student.username} that we already have in gitlab")
        course.storage_api.get_or_create_user(student, course.course_name)  # type: ignore
        return redirect(url_for("root.login", course_name=course.course_name))

    except Exception:
        logger.error("Failed login while working with db", exc_info=True)
        return redirect(url_for("root.login", course_name=course.course_name))


def check_secret(app: CustomFlask, course: Course, student: Student) -> str | None:
    """Checking course secret for user if he is entering"""

    if "secret" in request.form:
        if secrets.compare_digest(request.form["secret"], course.registration_secret):
            app.storage_api.sync_stored_user(
                course.course_name,
                student,
                app.gitlab_api.get_url_for_repo(student.username, course.gitlab_course_students_group),
                app.gitlab_api.check_is_course_admin(student.id, course.gitlab_course_group),
            )
        else:
            logger.error(f"Wrong secret user {student.username} on course {course.storage_api.course_name}")  # type: ignore
            return render_template(
                "create_project.html",
                error_message="Invalid registration secret",
                course=course,
                course_favicon=app.favicon,
                base_url=app.gitlab_api.base_url,
            )
    return None


def handle_oauth_callback(oauth: OAuth, app: CustomFlask) -> Response | WerkzeugResponse:
    """Process oauth2 callback with code for auth, if success set auth session"""

    try:
        gitlab_oauth_token = oauth.gitlab.authorize_access_token()
        student = app.gitlab_api.get_authenticated_student(gitlab_oauth_token["access_token"])
    except Exception:
        logger.error("Gitlab authorization failed", exc_info=True)
        return redirect(url_for("root.login"))

    session.setdefault("gitlab", {}).update(set_oauth_session(student, gitlab_oauth_token))
    session.permanent = True
    return redirect(url_for("root.login"))


def get_authenticate_student(oauth: OAuth, app: CustomFlask) -> Student | Response | WerkzeugResponse:
    """Getting student and update session"""

    try:
        student = app.gitlab_api.get_authenticated_student(session["gitlab"]["access_token"])
        session["gitlab"].update(set_oauth_session(student))
        return student

    except Exception:
        logger.error("Failed login in gitlab, redirect to login", exc_info=True)
        session.pop("gitlab", None)
        redirect_uri = url_for("root.login", _external=True)
        return oauth.gitlab.authorize_redirect(redirect_uri)


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        oauth = app.oauth

        if "code" in request.args:
            return handle_oauth_callback(oauth, app)

        if valid_session(session):
            student_or_resp = get_authenticate_student(oauth, app)

            if not isinstance(student_or_resp, Student):
                return student_or_resp
        else:
            logger.info("Redirect to login in Gitlab")
            redirect_uri = url_for("root.login", _external=True)
            return oauth.gitlab.authorize_redirect(redirect_uri)

        return f(*args, **kwargs)

    return decorated


def requires_ready(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        course_name = kwargs["course_name"]
        course = app.storage_api.get_course(course_name)

        if course is None:
            abort(redirect(url_for("root.index")))

        if not course.is_ready:
            abort(redirect(url_for("web.not_ready", course_name=course_name)))

        return f(*args, **kwargs)

    return decorated


def requires_course_participation(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        oauth = app.oauth

        course: Course = app.storage_api.get_course(kwargs["course_name"])  # type: ignore

        if valid_session(session):
            student_or_resp = get_authenticate_student(oauth, app)

            if not isinstance(student_or_resp, Student):
                return student_or_resp

            student = student_or_resp

            check_secret_or_none = check_secret(app, course, student)
            if check_secret_or_none is not None:
                return check_secret_or_none

            if not handle_course_membership(course, student) or not app.gitlab_api.check_project_exists(
                student=student, course_students_group=course.gitlab_course_students_group
            ):
                return render_template(
                    "create_project.html",
                    course=course,
                    course_favicon=app.favicon,
                    base_url=app.gitlab_api.base_url,
                )
        else:
            logger.info("Redirect to login in Gitlab")
            redirect_uri = url_for("root.login", _external=True)
            return oauth.gitlab.authorize_redirect(redirect_uri)

        return f(*args, **kwargs)

    return decorated


def requires_admin(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if current_app.debug:
            return f(*args, **kwargs)

        # TODO: checks that user is admin

        return f(*args, **kwargs)

    return decorated

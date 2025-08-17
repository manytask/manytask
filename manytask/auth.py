import logging
from functools import wraps
from http import HTTPStatus
from typing import Any, Callable

from authlib.integrations.flask_client import OAuth
from flask import abort, current_app, flash, redirect, request, session, url_for
from flask.sessions import SessionMixin
from sqlalchemy.exc import NoResultFound
from werkzeug import Response

from manytask.abstract import AuthenticatedUser
from manytask.course import Course
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
    auth_user: AuthenticatedUser, oauth_tokens: dict[str, str] | None = None, version: float = 1.5
) -> dict[str, Any]:
    """Set oauth creds in session for student"""

    result: dict[str, Any] = {
        "username": auth_user.username,
        "user_id": auth_user.id,
        "version": version,
    }
    if oauth_tokens:
        result |= {
            "access_token": oauth_tokens.get("access_token", ""),
            "refresh_token": oauth_tokens.get("refresh_token", ""),
        }
    return result


def handle_course_membership(app: CustomFlask, course: Course, username: str) -> bool | str | Response:
    """Checking user on course"""

    try:
        if app.storage_api.check_user_on_course(course.course_name, username):
            return True
        else:
            logger.info(f"No user {username} on course {course.course_name} asking secret")
            return False
    except NoResultFound:
        logger.info(f"User: {username} not in the database")
        return False
    except Exception:
        logger.error("Failed login while working with db", exc_info=True)
        return False


def handle_oauth_callback(oauth: OAuth, app: CustomFlask) -> Response:
    """Process oauth2 callback with code for auth, if success set auth session and sync user's data to database"""

    redirect_url = request.args.get("state") or url_for("root.index")

    try:
        # This is where the oath_api should be used
        gitlab_oauth_token = oauth.gitlab.authorize_access_token()
        rms_user = app.rms_api.get_authenticated_rms_user(gitlab_oauth_token["access_token"])
        auth_user = AuthenticatedUser(id=rms_user.id, username=rms_user.username)
    except Exception:
        logger.error("Gitlab authorization failed", exc_info=True)
        return redirect(redirect_url)

    session.setdefault("gitlab", {}).update(set_oauth_session(auth_user, gitlab_oauth_token))
    session.permanent = True

    return redirect(redirect_url)


def get_authenticated_user(oauth: OAuth, app: CustomFlask) -> AuthenticatedUser:
    """Getting student and update session"""

    # This is where the auth_api should be user instead of gitlab/rms
    rms_user = app.rms_api.get_authenticated_rms_user(session["gitlab"]["access_token"])
    auth_user = AuthenticatedUser(id=rms_user.id, username=rms_user.username)
    session["gitlab"].update(set_oauth_session(auth_user))
    return auth_user


def __redirect_to_login() -> Response:
    session.pop("gitlab", None)
    return redirect(url_for("root.signup"))


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check authentication"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        if valid_session(session):
            if not app.rms_api.check_user_authenticated_in_rms(
                app.oauth,
                session["gitlab"]["access_token"],
                session["gitlab"]["refresh_token"],
            ):
                return __redirect_to_login()
        else:
            logger.error("Failed to verify session.", exc_info=True)
            return __redirect_to_login()

        return f(*args, **kwargs)

    return decorated


def requires_ready(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check course readiness"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        course_name = kwargs["course_name"]
        course = app.storage_api.get_course(course_name)

        if course is None:
            flash("Course not found", "course_not_found")
            abort(redirect(url_for("root.index")))

        if not course.is_ready:
            abort(redirect(url_for("course.not_ready", course_name=course_name)))

        return f(*args, **kwargs)

    return decorated


def requires_course_access(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check course readiness, user authentication and access"""

    @requires_ready
    @requires_auth
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        oauth = app.oauth

        course: Course = app.storage_api.get_course(kwargs["course_name"])  # type: ignore
        auth_user: AuthenticatedUser = get_authenticated_user(oauth, app)

        if not handle_course_membership(app, course, auth_user.username) or not app.rms_api.check_project_exists(
            project_name=auth_user.username, project_group=course.gitlab_course_students_group
        ):
            abort(redirect(url_for("course.create_project", course_name=course.course_name)))

        # sync user's data from gitlab to database  TODO: optimize it
        app.storage_api.sync_user_on_course(
            course.course_name,
            auth_user.username,
            app.storage_api.check_if_instance_admin(auth_user.username),
        )

        return f(*args, **kwargs)

    return decorated


def requires_admin(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check user authentication and manytask admin access"""

    @requires_auth
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        username = session["gitlab"]["username"]
        if not app.storage_api.check_if_instance_admin(username):
            abort(HTTPStatus.FORBIDDEN)

        return f(*args, **kwargs)

    return decorated

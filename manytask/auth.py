import logging
from functools import wraps
from http import HTTPStatus
from typing import Any, Callable

from authlib.integrations.flask_client import OAuth
from flask import abort, current_app, flash, redirect, session, url_for
from flask.sessions import SessionMixin
from sqlalchemy.exc import NoResultFound
from werkzeug import Response

from manytask.abstract import AuthenticatedUser, ClientProfile
from manytask.course import Course, CourseStatus
from manytask.main import CustomFlask

logger = logging.getLogger(__name__)


def valid_auth_session(user_session: SessionMixin) -> bool:
    SESSION_VERSION = 1.6
    result = (
        "auth" in user_session
        and "version" in user_session["auth"]
        and user_session["auth"]["version"] >= SESSION_VERSION
        and "username" in user_session["auth"]
        and "user_auth_id" in user_session["auth"]
    )
    logger.debug("Auth_session_valid=%s", result)
    return result


def valid_rms_session(user_session: SessionMixin) -> bool:
    SESSION_VERSION = 1.1
    result = (
        "rms" in user_session
        and "version" in user_session["rms"]
        and user_session["rms"]["version"] >= SESSION_VERSION
        and "rms_id" in user_session["rms"]
        and "username" in user_session["rms"]
    )
    logger.debug("Rms_session_valid=%s", result)
    return result


def set_oauth_session(
    auth_user: AuthenticatedUser, oauth_tokens: dict[str, str] | None = None, version: float = 1.6
) -> dict[str, Any]:
    """Set oauth creds in session for student"""

    logger.debug("Setting session for user=%s, version=%s", auth_user.username, version)
    result: dict[str, Any] = {
        "username": auth_user.username,
        "user_auth_id": auth_user.id,
        "version": version,
    }
    if oauth_tokens:
        result |= {
            "access_token": oauth_tokens.get("access_token", ""),
            "refresh_token": oauth_tokens.get("refresh_token", ""),
        }
    return result


def set_rms_session(client_profile: ClientProfile, version: float = 1.1) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rms_id": client_profile.rms_id,
        "username": client_profile.username,
        "version": version,
    }
    return result


def handle_course_membership(app: CustomFlask, course: Course, rms_id: str) -> bool | str | Response:
    """Checking user on course"""

    try:
        if app.storage_api.check_user_on_course(course.course_name, rms_id):
            logger.info("User rms_id=%s is on course %s", rms_id, course.course_name)
            return True
        else:
            logger.info("No user rms_id=%s on course %s", rms_id, course.course_name)
            return False
    except NoResultFound:
        logger.info("User rms_id=%s not in the database", rms_id)
        return False
    except Exception:
        logger.error("Failed login while working with db", exc_info=True)
        return False


def __redirect_to_signup_finish() -> Response:
    return redirect(url_for("root.signup_finish"))


def handle_oauth_callback(oauth: OAuth, app: CustomFlask) -> Response:
    """Process oauth2 callback with code for auth, if success set auth session and sync user's data to database"""

    try:
        oauth_token = oauth.auth_provider.authorize_access_token()
        token = oauth_token["access_token"]
        logger.info("OAuth token received")

        auth_user = app.auth_api.get_authenticated_user(token)
    except Exception:
        logger.error("OAuth authorization failed", exc_info=True)
        return redirect(url_for("root.index"))

    session.pop("username", None)
    session.setdefault("auth", {}).update(set_oauth_session(auth_user, oauth_token))
    session.permanent = True
    logger.info("Session set for user=%s", auth_user.username)

    return __redirect_to_signup_finish()


def get_authenticated_user(oauth: OAuth, app: CustomFlask) -> AuthenticatedUser:
    """Getting student and update session"""
    auth_user = app.auth_api.get_authenticated_user(session["auth"]["access_token"])
    logger.info("Authenticated user=%s", auth_user.username)
    session["auth"].update(set_oauth_session(auth_user))
    return auth_user


def redirect_to_login_with_bad_session() -> Response:
    logger.debug("Clearing session and redirecting to signup")
    session.pop("auth", None)
    return redirect(url_for("root.signup"))


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check authentication"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        if not valid_auth_session(session):
            logger.error("Failed to verify auth session.", exc_info=True)
            return redirect_to_login_with_bad_session()

        if not app.auth_api.check_user_is_authenticated(
            app.oauth,
            session["auth"]["access_token"],
            session["auth"]["refresh_token"],
        ):
            logger.warning("Session not authenticated, redirecting to login")
            return redirect_to_login_with_bad_session()

        if not valid_rms_session(session):
            return __redirect_to_signup_finish()

        logger.debug("Auth check passed")
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
            flash("course not found!", "course_not_found")
            abort(redirect(url_for("root.index")))

        if course.status == CourseStatus.CREATED:
            abort(redirect(url_for("course.not_ready", course_name=course_name)))

        return f(*args, **kwargs)

    return decorated


def requires_course_access(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check course readiness, user authentication and access"""

    @requires_ready
    @requires_auth
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        from .utils.flask import can_access_course

        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        oauth = app.oauth

        course: Course = app.storage_api.get_course(kwargs["course_name"])  # type: ignore
        auth_user: AuthenticatedUser = get_authenticated_user(oauth, app)
        rms_id = session["rms"]["rms_id"]
        logger.info("User %s (rms_id=%s) accessing course=%s", auth_user.username, rms_id, course.course_name)

        if not can_access_course(app, rms_id, course.course_name):
            logger.warning(
                "User %s (rms_id=%s) attempted to access course %s without permission",
                auth_user.username,
                rms_id,
                course.course_name,
            )
            abort(HTTPStatus.FORBIDDEN)

        hidden_for_user = [CourseStatus.CREATED, CourseStatus.HIDDEN]
        if course.status in hidden_for_user and not app.storage_api.check_if_course_admin(course.course_name, rms_id):
            flash("course is hidden!", "course_hidden")
            abort(redirect(url_for("root.index")))

        if not handle_course_membership(app, course, rms_id) or not app.rms_api.check_project_exists(
            project_name=auth_user.username, project_group=course.gitlab_course_students_group
        ):
            logger.info("User %s (rms_id=%s) missing membership or project", auth_user.username, rms_id)
            abort(redirect(url_for("course.create_project", course_name=course.course_name)))

        # sync user's data from gitlab to database  TODO: optimize it
        app.storage_api.sync_user_on_course(
            course.course_name,
            rms_id,
            app.storage_api.check_if_instance_admin(rms_id),
        )
        logger.info("Synced user rms_id=%s on course %s", rms_id, course.course_name)

        return f(*args, **kwargs)

    return decorated


def requires_instance_admin(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check user authentication and manytask instance admin access"""

    @requires_auth
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        rms_id = session["rms"]["rms_id"]
        if not app.storage_api.check_if_instance_admin(rms_id):
            abort(HTTPStatus.FORBIDDEN)

        return f(*args, **kwargs)

    return decorated


def requires_instance_or_namespace_admin(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check user authentication and manytask instance admin or namespace admin access"""

    @requires_auth
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        from .utils.flask import is_namespace_admin

        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        rms_id = session["rms"]["rms_id"]
        is_instance_admin = app.storage_api.check_if_instance_admin(rms_id)
        is_namespace_admin_user = is_namespace_admin(app, rms_id)

        if not is_instance_admin and not is_namespace_admin_user:
            logger.warning(
                "User rms_id=%s attempted to access %s without instance admin or namespace admin privileges",
                rms_id,
                f.__name__,
            )
            abort(HTTPStatus.FORBIDDEN)

        return f(*args, **kwargs)

    return decorated


def role_required(required_roles: list[str] | str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to check if user has at least one of the required roles.

    Usage:
        @role_required(['instance_admin', 'namespace_admin'])
        def some_route():
            ...

    :param required_roles: Single role string or list of role strings
        Possible roles: 'instance_admin', 'namespace_admin', 'program_manager', 'student'
    """

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @requires_auth
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            from .utils.flask import has_role

            app: CustomFlask = current_app  # type: ignore

            if app.debug:
                return f(*args, **kwargs)

            rms_id = session["rms"]["rms_id"]
            course_name = kwargs.get("course_name", None)

            if not has_role(rms_id, required_roles, app, course_name):
                logger.warning(
                    "User rms_id=%s attempted to access %s without required role(s): %s",
                    rms_id,
                    f.__name__,
                    required_roles,
                )
                abort(HTTPStatus.FORBIDDEN)

            return f(*args, **kwargs)

        return decorated

    return decorator

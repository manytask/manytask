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
from manytask.utils.generic import sanitize_log_data

logger = logging.getLogger(__name__)


def valid_gitlab_session(user_session: SessionMixin) -> bool:
    SESSION_VERSION = 1.5
    result = (
        "gitlab" in user_session
        and "version" in user_session["gitlab"]
        and user_session["gitlab"]["version"] >= SESSION_VERSION
        and "username" in user_session["gitlab"]
        and "user_id" in user_session["gitlab"]
    )
    logger.debug(f"Gitlab_session_valid={result}")
    return result


def valid_client_profile_session(user_session: SessionMixin) -> bool:
    SESSION_VERSION = 1.0
    result = (
        "profile" in user_session
        and "version" in user_session["profile"]
        and user_session["profile"]["version"] >= SESSION_VERSION
        and "username" in user_session["profile"]
    )
    logger.debug(f"Client_profile_session_valid={result}")
    return result


def set_oauth_session(
    auth_user: AuthenticatedUser, oauth_tokens: dict[str, str] | None = None, version: float = 1.5
) -> dict[str, Any]:
    """Set oauth creds in session for student"""

    logger.debug(f"Setting session for user={auth_user.username}, version={version}")
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


def set_client_profile_session(client_profile: ClientProfile, version: float = 1.0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "username": client_profile.username,
        "version": version,
    }
    return result


def handle_course_membership(app: CustomFlask, course: Course, username: str) -> bool | str | Response:
    """Checking user on course"""

    try:
        if app.storage_api.check_user_on_course(course.course_name, username):
            logger.info(f"User {username} is on course {course.course_name}")
            return True
        else:
            logger.info(f"No user {username} on course {course.course_name}")
            return False
    except NoResultFound:
        logger.info(f"User: {username} not in the database")
        return False
    except Exception:
        logger.error("Failed login while working with db", exc_info=True)
        return False


def __redirect_to_signup_finish() -> Response:
    return redirect(url_for("root.signup_finish"))


def handle_oauth_callback(oauth: OAuth, app: CustomFlask) -> Response:
    """Process oauth2 callback with code for auth, if success set auth session and sync user's data to database"""

    try:
        # This is where the oath_api should be used
        gitlab_oauth_token = oauth.gitlab.authorize_access_token()
        token = gitlab_oauth_token["access_token"]
        logger.info("OAuth token received")

        auth_user = app.auth_api.get_authenticated_user(token)
    except Exception:
        logger.error("Gitlab authorization failed", exc_info=True)
        return redirect(url_for("root.index"))

    session.pop("username", None)
    session.setdefault("gitlab", {}).update(set_oauth_session(auth_user, gitlab_oauth_token))
    session.permanent = True
    logger.info(f"Session set for user={auth_user.username}")

    return __redirect_to_signup_finish()


def get_authenticated_user(oauth: OAuth, app: CustomFlask) -> AuthenticatedUser:
    """Getting student and update session"""

    # This is where the auth_api should be user instead of gitlab/rms
    auth_user = app.auth_api.get_authenticated_user(session["gitlab"]["access_token"])
    logger.info(f"Authenticated user={auth_user.username}")
    session["gitlab"].update(set_oauth_session(auth_user))
    return auth_user


def redirect_to_login_with_bad_session() -> Response:
    logger.debug("Clearing session and redirecting to signup")
    session.pop("gitlab", None)
    return redirect(url_for("root.signup"))


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    """Check authentication"""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        if not valid_gitlab_session(session):
            logger.error("Failed to verify gitlab session.", exc_info=True)
            return redirect_to_login_with_bad_session()

        if not app.auth_api.check_user_is_authenticated(
            app.oauth,
            session["gitlab"]["access_token"],
            session["gitlab"]["refresh_token"],
        ):
            logger.warning("Session not authenticated, redirecting to login")
            return redirect_to_login_with_bad_session()

        if not valid_client_profile_session(session):
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
        app: CustomFlask = current_app  # type: ignore

        if app.debug:
            return f(*args, **kwargs)

        oauth = app.oauth

        course: Course = app.storage_api.get_course(kwargs["course_name"])  # type: ignore
        auth_user: AuthenticatedUser = get_authenticated_user(oauth, app)
        logger.info(f"User {auth_user.username} accessing course={course.course_name}")

        hidden_for_user = [CourseStatus.CREATED, CourseStatus.HIDDEN]
        if course.status in hidden_for_user and not app.storage_api.check_if_course_admin(
            course.course_name, auth_user.username
        ):
            flash("course is hidden!", "course_hidden")
            abort(redirect(url_for("root.index")))

        if not handle_course_membership(app, course, auth_user.username) or not app.rms_api.check_project_exists(
            project_name=auth_user.username, project_group=course.gitlab_course_students_group
        ):
            logger.info(f"User {auth_user.username} missing membership or project")
            abort(redirect(url_for("course.create_project", course_name=course.course_name)))

        # sync user's data from gitlab to database  TODO: optimize it
        app.storage_api.sync_user_on_course(
            course.course_name,
            auth_user.username,
            app.storage_api.check_if_instance_admin(auth_user.username),
        )
        logger.info(f"Synced user {auth_user.username} on course {course.course_name}")

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

import logging
import secrets
from functools import wraps
from typing import Any, Callable

from flask import current_app, redirect, render_template, request, session, url_for
from flask.sessions import SessionMixin
from werkzeug.exceptions import Unauthorized

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


def requires_auth(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        if current_app.debug:
            return f(*args, **kwargs)

        if not valid_session(session):
            return redirect(url_for("web.signup"))
        return f(*args, **kwargs)

    return decorated


def requires_ready(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        course = current_app.course  # type: ignore
        if not course.config:
            return redirect(url_for("web.not_ready"))
        return f(*args, **kwargs)

    return decorated


def requires_secret(template: str = "create_project.html") -> Callable[..., Any]:
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            course = current_app.course  # type: ignore
            secret: str = ""

            try:
                student = course.gitlab_api.get_authenticated_student(session["gitlab"]["oauth_access_token"])
                # if user already in db we let him in with out secret
                if course.storage_api.check_user_on_course(course.storage_api.course_name, student):
                    secret = course.registration_secret

                # secret was entered in form
                elif "secret" in request.form:
                    if not secrets.compare_digest(request.form["secret"], course.registration_secret):
                        raise Exception("Invalid registration secret")
                    secret = request.form["secret"]

                # gently asking for a secret
                else:
                    return render_template(
                        template,
                        course_name=course.name,
                        course_favicon=course.favicon,
                        base_url=course.gitlab_api.base_url,
                    )

                # user have secret but dont have gitlab fork
                if not course.gitlab_api.check_project_exists(student) and secret:
                    return redirect(url_for("web.create_project", secret=secret))

            except Unauthorized:
                return redirect(url_for("web.signup"))
            except Exception as e:
                logger.error(f"Error in requires_secret: {e}", exc_info=True)
                return render_template(
                    template,
                    error_message=str(e),
                    course_name=course.name,
                    course_favicon=course.favicon,
                    base_url=course.gitlab_api.base_url,
                )
            return f(*args, **kwargs)

        return decorated

    return decorator

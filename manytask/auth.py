from functools import wraps

from flask import session, redirect, url_for, current_app


def valid_session(user_session) -> bool:
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


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_app.debug:
            return f(*args, **kwargs)
            
        if not valid_session(session):
            return redirect(url_for("web.signup"))
        return f(*args, **kwargs)
    return decorated


def requires_ready(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        course = current_app.course
        if not course.config:
            return redirect(url_for("web.not_ready"))
        return f(*args, **kwargs)
    return decorated 
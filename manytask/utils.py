from flask import abort, current_app, redirect, url_for

from .course import Course


def get_current_course(cookies: dict[str, str]) -> Course:
    course_name = cookies.get("course_name", None)

    if course_name is None:
        abort(redirect(url_for("web.not_ready")))  # TODO: make different pages

    course = current_app.storage_api.get_course(course_name)

    if course is None:
        abort(redirect(url_for("web.not_ready")))  # TODO: make different pages

    return course

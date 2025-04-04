from http import HTTPStatus

from flask import abort, current_app, redirect, url_for
from werkzeug.datastructures import Headers

from .course import Course
from .main import CustomFlask


def get_current_course_from_cookies(cookies: dict[str, str]) -> Course:
    app: CustomFlask = current_app  # type: ignore

    course_name = cookies.get("course_name", None)

    if course_name is None:
        abort(redirect(url_for("web.not_ready")))  # TODO: make different pages

    course = app.storage_api.get_course(course_name)

    if course is None:
        abort(redirect(url_for("web.not_ready")))  # TODO: make different pages

    if not course.is_ready:
        abort(redirect(url_for("web.not_ready")))  # TODO: make different pages

    return course


def get_current_course_from_headers(headers: Headers) -> Course:
    app: CustomFlask = current_app  # type: ignore

    course_name = headers.get("Course", None)

    if course_name is None:
        abort(HTTPStatus.BAD_REQUEST, "You didn't provide required header `Course`")

    course = app.storage_api.get_course(course_name)
    if course is None:
        abort(HTTPStatus.BAD_REQUEST, "Course not found")

    return course

from typing import TYPE_CHECKING
from flask import current_app as flask_current_app

from .course import Course

if TYPE_CHECKING:
    from flask import Flask

    class FlaskWithCourse(Flask):
        course: Course

    current_app: FlaskWithCourse
else:
    current_app = flask_current_app


def get_course() -> Course:
    """Get the course from the current Flask app."""
    if not hasattr(current_app, "course"):
        raise RuntimeError("Course not initialized in Flask app")
    return current_app.course 
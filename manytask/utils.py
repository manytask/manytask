import secrets

from flask import session, url_for

from manytask.abstract import RmsUser
from manytask.main import CustomFlask


def sanitize_log_data(data: str | None) -> str | None:
    """Sanitize form data."""
    if data is None:
        return None
    sanitized_data = data.replace("\r", "").replace("\n", "")
    return sanitized_data


def generate_token_hex(bytes_count: int = 24) -> str:
    return secrets.token_hex(nbytes=bytes_count)


def get_courses(app: CustomFlask) -> list[dict[str, str]]:
    if app.debug:
        courses_names = app.storage_api.get_all_courses_names_with_statuses()

    else:
        rms_user_id = session["gitlab"]["user_id"]
        rms_user = app.rms_api.get_rms_user_by_id(rms_user_id)
        if app.storage_api.check_if_instance_admin(rms_user.username):
            courses_names = app.storage_api.get_all_courses_names_with_statuses()
        else:
            courses_names = app.storage_api.get_user_courses_names_with_statuses(rms_user.username)

    return [
        {
            "name": course_name,
            "status": status.value,
            "url": url_for("course.course_page", course_name=course_name),
        }
        for course_name, status in courses_names
    ]


def check_admin(app: CustomFlask) -> bool:
    if app.debug:
        return True
    else:
        student_username = session["gitlab"]["username"]
        return app.storage_api.check_if_instance_admin(student_username)


def guess_first_last_name(user: RmsUser) -> tuple[str, str]:
    PARTS_IN_NAME = 2

    # TODO: implement better method for separating names
    name = user.name
    parts = name.split()
    if len(parts) == PARTS_IN_NAME:
        return tuple(parts)  # type: ignore
    return name, ""

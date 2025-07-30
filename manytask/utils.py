import secrets

from flask import session, url_for

from manytask.main import CustomFlask


def generate_token_hex(bytes_count: int = 24) -> str:
    return secrets.token_hex(nbytes=bytes_count)


def get_courses(app: CustomFlask) -> list[dict[str, str]]:
    if app.debug:
        courses_names = app.storage_api.get_all_courses_names()

    else:
        student_id = session["gitlab"]["user_id"]
        student = app.gitlab_api.get_student(student_id)
        if app.storage_api.check_if_instance_admin(student.username):
            courses_names = app.storage_api.get_all_courses_names()
        else:
            courses_names = app.storage_api.get_user_courses_names(student.username)

    return [
        {
            "name": course_name,
            "url": url_for("course.course_page", course_name=course_name),
        }
        for course_name in courses_names
    ]

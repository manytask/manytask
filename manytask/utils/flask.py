from flask import session, url_for

from manytask.main import CustomFlask


def get_courses(app: CustomFlask) -> list[dict[str, str]]:
    if app.debug:
        courses_names = app.storage_api.get_all_courses_names_with_statuses()

    if app.storage_api.check_if_instance_admin(session["profile"]["username"]):
        courses_names = app.storage_api.get_all_courses_names_with_statuses()
    else:
        courses_names = app.storage_api.get_user_courses_names_with_statuses(session["profile"]["username"])

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

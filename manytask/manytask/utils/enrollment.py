from __future__ import annotations

from manytask.abstract import RmsApi, RmsUser, StorageApi
from manytask.course import Course


def enroll_user_on_course(
    storage_api: StorageApi,
    rms_api: RmsApi,
    rms_user: RmsUser,
    course: Course,
    username: str,
    course_admin: bool,
) -> None:
    """Enroll a user on a course: record them in users_on_courses and create/update their RMS project.

    Shared by the web `create_project` view and the `POST /api/<course_name>/enroll` API endpoint.
    Idempotent: safe to call again for an already enrolled user.
    """
    storage_api.sync_user_on_course(course.course_name, username, course_admin)
    rms_api.create_project(rms_user, course.gitlab_course_students_group, course.gitlab_course_public_repo)

from collections.abc import Iterator

import pytest
from sqlalchemy import select

from manytask.course import CourseConfig, CourseStatus
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.models import UserOnCourse

STUDENT = "enrollment_student"


@pytest.fixture
def enrollment_database(postgres_container, tables) -> Iterator[tuple[DataBaseApi, CourseConfig]]:
    storage = DataBaseApi(DatabaseConfig(postgres_container.get_connection_url(), "instance_admin"))
    course = CourseConfig(
        course_name="enrollment_course",
        namespace_id=None,
        gitlab_course_group="course",
        gitlab_course_public_repo="course/public",
        gitlab_course_students_group="course/students",
        gitlab_default_branch="main",
        registration_secret="test-secret",
        token="test-token",
        show_allscores=True,
        status=CourseStatus.IN_PROGRESS,
    )
    storage.create_course(course)
    storage.update_or_create_user(STUDENT, "Student", "Test", "1001", 1001)
    try:
        yield storage, course
    finally:
        storage.engine.dispose()


@pytest.mark.parametrize("read_only", [False, True])
@pytest.mark.parametrize("method_name, expected", [("get_effective_grade", 0), ("is_grade_overridden", False)])
def test_grade_read_does_not_create_enrollment(enrollment_database, read_only, method_name, expected):
    storage, course = enrollment_database
    storage.engine.update_execution_options(postgresql_readonly=read_only)
    read = getattr(storage, method_name)
    assert read(course.course_name, STUDENT) == expected
    assert read(course.course_name, "unknown_student") == expected
    assert storage.check_user_on_course(course.course_name, STUDENT) is False


@pytest.mark.parametrize("saved_grade, override, expected", [(None, None, 0), (3, None, 3), (3, 5, 5)])
def test_grade_reads_keep_saved_values(enrollment_database, saved_grade, override, expected):
    storage, course = enrollment_database
    storage.sync_user_on_course(course.course_name, STUDENT, False)
    with storage._session_create() as session:
        enrollment = session.scalars(select(UserOnCourse)).one()
        enrollment.final_grade = saved_grade
        enrollment.final_grade_override = override
        session.commit()

    storage.engine.update_execution_options(postgresql_readonly=True)
    assert storage.get_effective_grade(course.course_name, STUDENT) == expected
    assert storage.is_grade_overridden(course.course_name, STUDENT) is (override is not None)

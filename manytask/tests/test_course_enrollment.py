from collections.abc import Iterator
from dataclasses import replace
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import NoResultFound, OperationalError

from manytask.abstract import AuthenticatedUser, RmsUser
from manytask.api import bp as api_bp
from manytask.course import CourseConfig, CourseStatus
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.mock_auth import MockAuthApi
from manytask.models import Course, Deadline, Grade, Task, TaskGroup, UserOnCourse
from manytask.web import course_bp, root_bp
from tests.helpers import build_mock_session, make_flask_app, set_session

STUDENT = "enrollment_student"
MUTATIONS = [
    ("update_student_comment", {"comment": "Teacher comment"}),
    ("override_grade", {"new_grade": 5}),
    ("clear_grade_override", {}),
    ("calculate_and_save_grade", {"student_scores_data": {"percent": 80, "large_count": 1}}),
    ("store_score", {"task_name": "task", "update_fn": lambda *args: 80}),
]


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


def _prepare_missing_enrollment(storage, course, state) -> str:
    if state == "unknown":
        return "unknown_student"
    if state == "other_course":
        other = replace(course, course_name="other_course", token="other-test-token")
        storage.create_course(other)
        storage.sync_user_on_course(other.course_name, STUDENT, False)
    return STUDENT


@pytest.mark.parametrize("state", ["not_enrolled", "unknown", "other_course"])
@pytest.mark.parametrize("method_name, kwargs", MUTATIONS)
def test_grade_mutations_never_enroll_students(enrollment_database, state, method_name, kwargs):
    storage, course = enrollment_database
    username = _prepare_missing_enrollment(storage, course, state)
    users_before = storage.get_all_users()
    with pytest.raises(NoResultFound):
        getattr(storage, method_name)(course.course_name, username, **kwargs)
    assert storage.check_user_on_course(course.course_name, STUDENT) is False
    assert {user.username for user in storage.get_all_users()} == {user.username for user in users_before}
    if state == "other_course":
        assert storage.check_user_on_course("other_course", STUDENT) is True


@pytest.mark.parametrize("method_name, kwargs", MUTATIONS)
def test_grade_mutations_update_existing_enrollment_under_lock(course_with_task, method_name, kwargs):
    storage, course = course_with_task
    initial_override = 4
    storage.sync_user_on_course(course.course_name, STUDENT, False)
    with storage._session_create() as session:
        enrollment = session.scalars(select(UserOnCourse)).one()
        enrollment.final_grade = 3
        enrollment.final_grade_override = initial_override
        session.commit()

    observed_locks = []

    def verify_lock(connection, cursor, statement, parameters, context, executemany) -> None:
        if UserOnCourse.__tablename__ not in statement or "FOR UPDATE" not in statement or "NOWAIT" in statement:
            return
        with pytest.raises(OperationalError) as failure:
            with storage.engine.begin() as competitor:
                competitor.execute(select(UserOnCourse.id).with_for_update(nowait=True))
        assert failure.value.orig.pgcode == "55P03"
        observed_locks.append(True)

    event.listen(storage.engine, "after_cursor_execute", verify_lock)
    try:
        getattr(storage, method_name)(course.course_name, STUDENT, **kwargs)
    finally:
        event.remove(storage.engine, "after_cursor_execute", verify_lock)
    assert observed_locks
    with storage._session_create() as session:
        enrollment = session.scalars(select(UserOnCourse)).one()
        if method_name == "update_student_comment":
            assert enrollment.comment == kwargs["comment"]
        elif method_name == "override_grade":
            assert enrollment.final_grade_override == kwargs["new_grade"]
        elif method_name == "clear_grade_override":
            assert enrollment.final_grade_override is None
        elif method_name == "calculate_and_save_grade":
            assert enrollment.final_grade == 0
            assert enrollment.final_grade_override == initial_override
        else:
            assert storage.get_scores(course.course_name, STUDENT) == {"task": 80}


@pytest.fixture
def course_with_task(enrollment_database):
    storage, config = enrollment_database
    with storage._session_create() as session:
        course = session.scalars(select(Course).where(Course.name == config.course_name)).one()
        group = TaskGroup(name="hw", course=course, deadline=Deadline())
        session.add(Task(name="task", group=group, score=100, min_score=50))
        session.commit()
    return storage, config


@pytest.fixture
def enrollment_client(course_with_task):
    storage, _ = course_with_task
    app = make_flask_app(root_bp, course_bp, api_bp)
    app.storage_api = storage
    app.auth_api = MockAuthApi()
    app.auth_api.user = AuthenticatedUser(id=-1, username="instance_admin")
    app.oauth = MagicMock()
    app.rms_api = MagicMock()
    app.rms_api.get_url_for_repo.return_value = "https://example.test/course/student"
    admin = storage.get_stored_user_by_username("instance_admin")
    with app.test_client() as client:
        set_session(client, build_mock_session("instance_admin", user_auth_id=-1, rms_id="-1", user_id=admin.user_id))
        yield client


def _table_payload(username, new_scores) -> dict:
    return {
        "new_scores": new_scores,
        "row_data": {"username": username, "scores": {}, "total_score": 0, "percent": 0, "large_count": 0, "grade": 0},
    }


@pytest.mark.parametrize("state", ["not_enrolled", "unknown", "other_course"])
@pytest.mark.parametrize(
    "endpoint, payload",
    [
        ("comment/update", {"comment": "Teacher comment"}),
        ("grade/override", {"grade": 5}),
        ("grade/clear_override", {}),
        ("database/update", _table_payload(STUDENT, {"task": 80})),
        ("database/update", _table_payload(STUDENT, {})),
    ],
)
def test_table_api_rejects_missing_enrollment(enrollment_client, enrollment_database, state, endpoint, payload):
    storage, course = enrollment_database
    username = _prepare_missing_enrollment(storage, course, state)
    data = {**payload, "username": username}
    if "row_data" in data:
        data["row_data"] = {**data["row_data"], "username": username}
    response = enrollment_client.post(f"/api/{course.course_name}/{endpoint}", json=data)
    assert response.status_code == HTTPStatus.NOT_FOUND, response.data
    assert "error" in response.json
    if state != "unknown":
        assert response.json["success"] is False
        assert response.json["message"] == "Student is not enrolled in this course"
    assert storage.check_user_on_course(course.course_name, STUDENT) is False


@pytest.mark.parametrize(
    "endpoint, payload",
    [
        ("comment/update", {"username": STUDENT, "comment": "Teacher comment"}),
        ("grade/override", {"username": STUDENT, "grade": 5}),
        ("grade/clear_override", {"username": STUDENT}),
        ("database/update", _table_payload(STUDENT, {"task": 80})),
    ],
)
def test_table_api_can_update_existing_enrollment(enrollment_client, enrollment_database, endpoint, payload):
    storage, course = enrollment_database
    storage.sync_user_on_course(course.course_name, STUDENT, False)
    response = enrollment_client.post(f"/api/{course.course_name}/{endpoint}", json=payload)
    assert response.status_code == HTTPStatus.OK, response.data
    assert response.json["success"] is True
    if endpoint == "database/update":
        assert storage.get_scores(course.course_name, STUDENT) == {"task": 80}


def _send_score_report(client, course: CourseConfig, username: str = STUDENT):
    rms_id = "1001" if username == STUDENT else "9999"
    rms_user = RmsUser(id=rms_id, username=username, name="Test User")
    client.application.rms_api.get_rms_user_by_id.return_value = rms_user
    return client.post(
        f"/api/{course.course_name}/report",
        headers={"Authorization": f"Bearer {course.token}"},
        data={"user_id": rms_id, "task": "task", "score": "80", "check_deadline": "False"},
    )


@pytest.mark.parametrize("state", ["not_enrolled", "unknown", "other_course"])
def test_checker_report_rejects_missing_enrollment(enrollment_client, enrollment_database, state):
    storage, course = enrollment_database
    username = _prepare_missing_enrollment(storage, course, state)
    users_before = {user.username for user in storage.get_all_users()}
    response = _send_score_report(enrollment_client, course, username)
    assert response.status_code == HTTPStatus.NOT_FOUND, response.data
    if state != "unknown":
        assert response.json["message"] == "Student is not enrolled in this course"
    else:
        assert b"no registered user" in response.data
    assert storage.check_user_on_course(course.course_name, STUDENT) is False
    assert {user.username for user in storage.get_all_users()} == users_before
    with storage._session_create() as session:
        assert session.query(Grade).count() == 0


def test_checker_report_updates_already_enrolled_student(enrollment_client, enrollment_database):
    storage, course = enrollment_database
    storage.sync_user_on_course(course.course_name, STUDENT, False)
    response = _send_score_report(enrollment_client, course)
    assert response.status_code == HTTPStatus.OK, response.data
    assert response.json["score"] == storage.get_scores(course.course_name, STUDENT)["task"]

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import yaml
from alembic import command
from alembic.script import ScriptDirectory
from psycopg2.errors import DuplicateColumn, DuplicateTable, UndefinedTable, UniqueViolation
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, NoResultFound, ProgrammingError
from sqlalchemy.orm import Session

from manytask.config import (
    ManytaskConfig,
    ManytaskDeadlinesConfig,
    ManytaskFinalGradeConfig,
    ManytaskGroupConfig,
    ManytaskUiConfig,
)
from manytask.course import Course as ManytaskCourse
from manytask.course import CourseConfig, CourseStatus, ManytaskDeadlinesType
from manytask.database import DataBaseApi, DatabaseConfig, TaskDisabledError
from manytask.models import (
    Course,
    Deadline,
    Grade,
    Namespace,
    Task,
    TaskGroup,
    User,
    UserOnCourse,
    UserOnNamespace,
    UserOnNamespaceRole,
)
from tests.constants import (
    BONUS_GROUP,
    BONUS_SCORE,
    DEADLINES_CONFIG_FILES,
    FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED,
    FIRST_COURSE_EXPECTED_STATS_KEYS,
    FIRST_COURSE_NAME,
    FIXED_CURRENT_TIME,
    GRADE_AFTER_DOWNGRADE_IN_PROGRESS,
    GRADE_BEFORE_DOWNGRADE,
    GRADE_CONFIG_FILES,
    GRADE_FROZEN_VALUE,
    SECOND_COURSE_EXPECTED_MAX_SCORE_STARTED,
    SECOND_COURSE_EXPECTED_STATS_KEYS,
    SECOND_COURSE_NAME,
    TEST_AUTH_ID,
    TEST_AUTH_ID_1,
    TEST_AUTH_ID_2,
    TEST_FIRST_NAME,
    TEST_FIRST_NAME_1,
    TEST_FIRST_NAME_2,
    TEST_LAST_NAME,
    TEST_LAST_NAME_1,
    TEST_LAST_NAME_2,
    TEST_RMS_ID,
    TEST_RMS_ID_1,
    TEST_RMS_ID_2,
    TEST_USERNAME,
    TEST_USERNAME_1,
    TEST_USERNAME_2,
    USER_EXPECTED,
)


class TestException(Exception):
    pass


def _make_full_name(first_name: str, last_name: str) -> str:
    return f"{first_name} {last_name}"


def _load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


@pytest.fixture(autouse=True)
def mock_current_time():
    with patch("manytask.database.DataBaseApi.get_now_with_timezone") as mock:
        mock.return_value = FIXED_CURRENT_TIME
        yield mock


def db_config(db_url):
    return DatabaseConfig(
        database_url=db_url,
        instance_admin_username="instance_admin",
        apply_migrations=True,
    )


@pytest.fixture
def db_api(tables, postgres_container, session):
    config = db_config(postgres_container.get_connection_url())
    config.session_factory = lambda: session
    return DataBaseApi(config)


@pytest.fixture
def first_course_grade_config():
    grade_config_data = _load_yaml(GRADE_CONFIG_FILES[0])

    return ManytaskFinalGradeConfig(**grade_config_data["grades"])


@pytest.fixture
def first_course_grade_config_with_changed_numbers():
    grade_config_data = _load_yaml(GRADE_CONFIG_FILES[0])

    grade_config_data_changed_numbers = dict()
    grade_config_data_changed_numbers["grades"] = dict()
    for key, value in grade_config_data["grades"]["grades"].items():
        grade_config_data_changed_numbers["grades"][key + 2] = value.copy()

    return ManytaskFinalGradeConfig(**grade_config_data_changed_numbers)


@pytest.fixture
def second_course_grade_config():
    grade_config_data = _load_yaml(GRADE_CONFIG_FILES[1])

    return ManytaskFinalGradeConfig(**grade_config_data["grades"])


@pytest.fixture
def second_course_grade_config_with_additional_grade():
    grade_config_data = _load_yaml(GRADE_CONFIG_FILES[1])

    grade_config_data["grades"]["grades"][3] = [
        {
            "percent": 50,
            "large_count": 1,
        },
    ]

    return ManytaskFinalGradeConfig(**grade_config_data["grades"])


@pytest.fixture
def first_course_config():
    return CourseConfig(
        course_name=FIRST_COURSE_NAME,
        namespace_id=None,
        gitlab_course_group="test_course_group",
        gitlab_course_public_repo="test_course_public_repo",
        gitlab_course_students_group="test_course_students_group",
        gitlab_default_branch="test_default_branch",
        registration_secret="secret",
        token="test_token",
        show_allscores=True,
        status=CourseStatus.CREATED,
        task_url_template="https://gitlab.test.com/test/$GROUP_NAME/$TASK_NAME",
        links={"TG Channel": "https://t.me/joinchat/", "TG Chat": "https://t.me/joinchat/"},
        deadlines_type=ManytaskDeadlinesType.HARD,
    )


@pytest.fixture
def edited_first_course_config(first_course_config):
    edited_config = first_course_config
    edited_config.gitlab_course_group = "test_course_group2"
    edited_config.gitlab_course_public_repo = "test_course_public_repo2"
    edited_config.gitlab_course_students_group = "test_course_students_group2"
    edited_config.gitlab_default_branch = "test_default_branch2"
    edited_config.registration_secret = "secret2"
    edited_config.token = "test_token"
    edited_config.show_allscores = False
    edited_config.status = CourseStatus.IN_PROGRESS

    return edited_config


@pytest.fixture
def first_course_updated_ui_config():
    return ManytaskUiConfig(
        task_url_template=UPDATED_TASK_URL_TEMPLATE,
        links=UPDATED_LINKS,
    )


@pytest.fixture
def second_course_config():
    return CourseConfig(
        course_name=SECOND_COURSE_NAME,
        namespace_id=None,
        gitlab_course_group="test_course_group",
        gitlab_course_public_repo="test_course_public_repo",
        gitlab_course_students_group="test_course_students_group",
        gitlab_default_branch="test_default_branch",
        registration_secret="secret",
        token="another_test_token",
        show_allscores=True,
        status=CourseStatus.CREATED,
        task_url_template="https://gitlab.test.com/another_test/$GROUP_NAME/$TASK_NAME",
        links={"TG Chat": "https://t.me/joinchat2/"},
        deadlines_type=ManytaskDeadlinesType.HARD,
    )


@pytest.fixture
def edited_second_course_config(second_course_config):
    edited_config = second_course_config
    edited_config.status = CourseStatus.IN_PROGRESS

    return edited_config


@pytest.fixture
def first_course_deadlines_config():
    deadlines_config_data = _load_yaml(DEADLINES_CONFIG_FILES[0])
    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def second_course_deadlines_config():
    deadlines_config_data = _load_yaml(DEADLINES_CONFIG_FILES[1])
    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def first_course_deadlines_config_with_changed_task_name():
    deadlines_config_data = _load_yaml(DEADLINES_CONFIG_FILES[0])

    # change task name: task_0_0 -> task_0_0_changed
    deadlines_config_data["deadlines"]["schedule"][0]["tasks"][0]["task"] += "_changed"

    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def first_course_deadlines_config_with_changed_order_of_groups():
    deadlines_config_data = _load_yaml(DEADLINES_CONFIG_FILES[0])

    # reverse order of the groups
    deadlines_config_data["deadlines"]["schedule"] = list(reversed(deadlines_config_data["deadlines"]["schedule"]))

    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def first_course_deadlines_config_with_changed_order_of_tasks():
    deadlines_config_data = _load_yaml(DEADLINES_CONFIG_FILES[0])

    # reverse order of the tasks of the first group
    deadlines_config_data["deadlines"]["schedule"][0]["tasks"] = list(
        reversed(deadlines_config_data["deadlines"]["schedule"][0]["tasks"])
    )

    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


def update_course(
    db_api: DataBaseApi,
    course_name: str,
    ui_config: ManytaskUiConfig,
    deadlines_config: ManytaskDeadlinesConfig,
    final_grade_config: ManytaskFinalGradeConfig | None = None,
) -> None:
    """Update created course"""
    config = ManytaskConfig(version=1, ui=ui_config, deadlines=deadlines_config, grades=final_grade_config)

    db_api.update_course(course_name=course_name, config=config)


def create_course(
    db_api: DataBaseApi,
    course_config: CourseConfig,
    deadlines_config: ManytaskDeadlinesConfig,
    final_grade_config: ManytaskFinalGradeConfig | None = None,
) -> None:
    """Create and update course"""
    db_api.create_course(settings_config=course_config)

    update_course(
        db_api,
        course_config.course_name,
        ManytaskUiConfig(
            task_url_template=course_config.task_url_template,
            links=course_config.links,
        ),
        deadlines_config,
        final_grade_config,
    )


def edit_course(db_api: DataBaseApi, course_config: CourseConfig) -> None:
    db_api.edit_course(settings_config=course_config)


@pytest.fixture
def db_api_with_initialized_first_course(
    db_api, first_course_config, first_course_deadlines_config, first_course_grade_config
):
    create_course(db_api, first_course_config, first_course_deadlines_config, first_course_grade_config)
    return db_api


@pytest.fixture
def db_api_with_two_initialized_courses(
    db_api,
    first_course_config,
    first_course_deadlines_config,
    first_course_grade_config,
    second_course_config,
    second_course_deadlines_config,
    second_course_grade_config,
):
    create_course(db_api, first_course_config, first_course_deadlines_config, first_course_grade_config)
    create_course(db_api, second_course_config, second_course_deadlines_config, second_course_grade_config)
    return db_api


def update_func(add: int):
    def _update_func(_, score):
        return score + add

    return _update_func


@dataclass
class QueryCount:
    value: int = 0


@contextmanager
def query_counter(engine):
    counter = QueryCount()

    def _increment(conn, cursor, statement, parameters, context, executemany):
        counter.value += 1

    event.listen(engine, "before_cursor_execute", _increment)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _increment)


@dataclass
class TestStudent:
    username: str
    first_name: str
    last_name: str
    rms_id: str | int
    auth_id: int


STUDENT = TestStudent(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID, TEST_AUTH_ID)
STUDENT_1 = TestStudent(TEST_USERNAME_1, TEST_FIRST_NAME_1, TEST_LAST_NAME_1, TEST_RMS_ID_1, TEST_AUTH_ID_1)
STUDENT_2 = TestStudent(TEST_USERNAME_2, TEST_FIRST_NAME_2, TEST_LAST_NAME_2, TEST_RMS_ID_2, TEST_AUTH_ID_2)

DEFAULT_LINKS = {"TG Channel": "https://t.me/joinchat/", "TG Chat": "https://t.me/joinchat/"}
UPDATED_LINKS = {"TG Channel": "https://t.me/joinchat_updated/", "TG Chat": "https://t.me/joinchat_updated/"}
UPDATED_TASK_URL_TEMPLATE = "https://gitlab.test.com/test_updated/$GROUP_NAME/$TASK_NAME"


def create_user(db_api: DataBaseApi, student: TestStudent = STUDENT):
    return db_api.update_or_create_user(
        student.username, student.first_name, student.last_name, student.rms_id, student.auth_id
    )


def make_user(student: TestStudent = STUDENT, **kwargs) -> User:
    return User(
        username=student.username,
        first_name=student.first_name,
        last_name=student.last_name,
        rms_id=student.rms_id,
        auth_id=student.auth_id,
        **kwargs,
    )


def add_user_on_course(
    session: Session,
    *,
    student: TestStudent = STUDENT,
    user_id: int = 2,
    course_id: int = 1,
    is_course_admin: bool,
) -> tuple[User, UserOnCourse]:
    user = make_user(student, id=user_id)
    user_on_course = UserOnCourse(user_id=user.id, course_id=course_id, is_course_admin=is_course_admin)
    session.add(user)
    session.add(user_on_course)
    session.commit()
    return user, user_on_course


def get_user_results(db_api: DataBaseApi, course_name: str, username: str):
    return (
        db_api.get_stats(course_name),
        db_api.get_all_scores_with_names(course_name),
        db_api.get_bonus_score(course_name, username),
        db_api.get_scores(course_name, username),
    )


def assert_empty_stats(
    db_api: DataBaseApi,
    course_name: str,
    expected_keys: set[str],
    expected_max_score: int,
) -> None:
    stats = db_api.get_stats(course_name)
    assert set(stats.keys()) == expected_keys
    assert all(v == 0 for v in stats.values())
    assert db_api.max_score_started(course_name) == expected_max_score


def assert_stats(stats: dict, expected_keys: set[str], nonzero: dict[str, float]) -> None:
    assert set(stats.keys()) == expected_keys
    for name, ratio in nonzero.items():
        assert stats[name] == ratio
    assert all(v == 0.0 for k, v in stats.items() if k not in nonzero)


def named_scores(scores: dict, student: TestStudent = STUDENT) -> tuple:
    return (scores, (student.first_name, student.last_name), None, None, None)


def assert_course(  # noqa: PLR0913
    course: Course,
    *,
    name: str = FIRST_COURSE_NAME,
    registration_secret: str = "secret",
    token: str = "test_token",
    show_allscores: bool = True,
    gitlab_course_group: str = "test_course_group",
    gitlab_course_public_repo: str = "test_course_public_repo",
    gitlab_course_students_group: str = "test_course_students_group",
    gitlab_default_branch: str = "test_default_branch",
    task_url_template: str = "https://gitlab.test.com/test/$GROUP_NAME/$TASK_NAME",
    links: dict | None = None,
    timezone: str,
    max_submissions: int | None,
    submission_penalty: float,
    status: CourseStatus | None = None,
) -> None:
    """
    Assert that a Course row matches the expected attributes.
    """
    expected = {
        "name": name,
        "registration_secret": registration_secret,
        "token": token,
        "show_allscores": show_allscores,
        "gitlab_course_group": gitlab_course_group,
        "gitlab_course_public_repo": gitlab_course_public_repo,
        "gitlab_course_students_group": gitlab_course_students_group,
        "gitlab_default_branch": gitlab_default_branch,
        "task_url_template": task_url_template,
        "links": DEFAULT_LINKS if links is None else links,
        "timezone": timezone,
        "max_submissions": max_submissions,
        "submission_penalty": submission_penalty,
    }
    assert {field: getattr(course, field) for field in expected} == expected
    # ``status=None`` only checks the value is set; otherwise require an exact match.
    assert course.status if status is None else course.status == status


def assert_tasks(
    session: Session,
    *,
    bonus_tasks: tuple[str, ...],
    large_tasks,
    special_tasks: tuple[str, ...],
    disabled_groups: tuple[str, ...],
    disabled_tasks: tuple[str, ...],
) -> None:
    tasks = session.query(Task).all()
    for task in tasks:
        if task.group.name == BONUS_GROUP:
            assert task.name == BONUS_SCORE
            continue

        # for convenience task score relates to its name (exception is group_0, it has multiplier "1")
        # for example for task_1_3 score is 10, task_3_0 score is 30
        score_multiplier = int(task.name.split("_")[1]) or 1

        actual = {
            "name": task.name,
            "group_name": task.group.name,
            "is_bonus": task.is_bonus,
            "is_large": task.is_large,
            "is_special": task.is_special,
            "group_enabled": task.group.enabled,
            "enabled": task.enabled,
            "score": task.score,
        }
        expected = {
            "name": task.name,
            "group_name": "group_" + task.name[len("task_")],
            "is_bonus": task.name in bonus_tasks,
            "is_large": task.name in large_tasks,
            "is_special": task.name in special_tasks,
            "group_enabled": task.group.name not in disabled_groups,
            "enabled": task.name not in disabled_tasks,
            "score": score_multiplier * 10,
        }
        assert actual == expected


def test_not_initialized_course(session, db_api, first_course_config):
    db_api.create_course(settings_config=first_course_config)
    course_name = first_course_config.course_name

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert_course(
        course,
        status=CourseStatus.CREATED,
        timezone="UTC",
        max_submissions=None,
        submission_penalty=0,
    )

    stats, all_scores, bonus_score, scores = get_user_results(db_api, course_name, "unknown_user")
    max_score_started = db_api.max_score_started(course_name)

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}
    assert max_score_started == 0


def test_initialized_course(db_api_with_initialized_first_course, session):  # noqa: PLR0915
    expected_task_groups = 7
    expected_tasks = 20
    bonus_tasks = ("task_0_2", "task_1_3")
    large_tasks = "task_5_0"
    special_tasks = ("task_1_1",)
    disabled_groups = ("group_4",)
    disabled_tasks = ("task_2_1",)
    grades_order = [5, 4, 3, 2]
    lowest_grade = 2
    grade_config_list_length = 2
    grade_config_lowest_percent = 50

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert_course(
        course,
        timezone="Europe/Berlin",
        max_submissions=10,
        submission_penalty=0.1,
    )

    assert_empty_stats(
        db_api_with_initialized_first_course,
        FIRST_COURSE_NAME,
        FIRST_COURSE_EXPECTED_STATS_KEYS,
        FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED,
    )

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    assert_tasks(
        session,
        bonus_tasks=bonus_tasks,
        large_tasks=large_tasks,
        special_tasks=special_tasks,
        disabled_groups=disabled_groups,
        disabled_tasks=disabled_tasks,
    )

    final_grade_config = db_api_with_initialized_first_course.get_grades(FIRST_COURSE_NAME)
    assert final_grade_config.grades_order == grades_order

    for grade in final_grade_config.grades_order:
        if grade != lowest_grade:
            assert isinstance(final_grade_config.grades[grade], list)
            assert len(final_grade_config.grades[grade]) == grade_config_list_length
            assert isinstance(final_grade_config.grades[grade][0], dict)
            assert final_grade_config.grades[grade][0][Path("percent")] >= grade_config_lowest_percent
            assert final_grade_config.grades[grade][0][Path("large_count")] >= 1
        else:
            assert isinstance(final_grade_config.grades[grade], list)
            assert len(final_grade_config.grades[grade]) == 1
            assert isinstance(final_grade_config.grades[grade][0], dict)
            assert final_grade_config.grades[grade][0][Path("")] == 0


def test_updating_course(
    db_api,
    first_course_config,
    first_course_deadlines_config,
    second_course_deadlines_config,
    first_course_updated_ui_config,
    first_course_grade_config_with_changed_numbers,
    session,
):
    expected_task_groups = 9
    expected_tasks = 29
    bonus_tasks = ("task_0_2", "task_1_3", "task_6_0")
    large_tasks = ("task_5_0", "task_5_1")
    special_tasks = ("task_1_1", "task_6_0")
    disabled_groups = ("group_6",)
    disabled_tasks = ("task_2_2",)

    create_course(
        db_api, first_course_config, first_course_deadlines_config, first_course_grade_config_with_changed_numbers
    )
    update_course(
        db_api,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        second_course_deadlines_config,
        first_course_grade_config_with_changed_numbers,
    )

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert_course(
        course,
        task_url_template=UPDATED_TASK_URL_TEMPLATE,
        links=UPDATED_LINKS,
        timezone="Europe/Moscow",
        max_submissions=20,
        submission_penalty=0.2,
    )

    assert_empty_stats(
        db_api,
        FIRST_COURSE_NAME,
        SECOND_COURSE_EXPECTED_STATS_KEYS,
        SECOND_COURSE_EXPECTED_MAX_SCORE_STARTED,
    )

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    assert_tasks(
        session,
        bonus_tasks=bonus_tasks,
        large_tasks=large_tasks,
        special_tasks=special_tasks,
        disabled_groups=disabled_groups,
        disabled_tasks=disabled_tasks,
    )


def test_resync_with_changed_task_name(
    db_api,
    first_course_config,
    first_course_deadlines_config,
    first_course_deadlines_config_with_changed_task_name,
    first_course_updated_ui_config,
    first_course_grade_config,
    session,
):
    expected_task_groups = 7
    expected_tasks = 21
    disabled_tasks = ("task_0_0", "task_2_1")

    create_course(db_api, first_course_config, first_course_deadlines_config, first_course_grade_config)
    update_course(
        db_api,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        first_course_deadlines_config_with_changed_task_name,
        first_course_grade_config,
    )

    assert_empty_stats(
        db_api,
        FIRST_COURSE_NAME,
        FIRST_COURSE_EXPECTED_STATS_KEYS - {"task_0_0"} | {"task_0_0_changed"},
        FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED,
    )

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    tasks = session.query(Task).all()
    for task in tasks:
        if task.group.name == BONUS_GROUP:
            assert task.name == BONUS_SCORE
        else:
            assert task.group.name == "group_" + task.name[len("task_")]

            assert task.enabled != (task.name in disabled_tasks)


def test_store_score(db_api_with_initialized_first_course, session):
    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0

    create_user(db_api_with_initialized_first_course)

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 0

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME, TEST_USERNAME, "not_exist_task", update_func(1)
        )
        == 0
    )

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1

    user = session.query(User).all()[-1]
    assert user.username == TEST_USERNAME

    user_on_course = session.query(UserOnCourse).one()
    assert user_on_course.user_id == user.id
    assert user_on_course.course.name == FIRST_COURSE_NAME

    assert session.query(Grade).count() == 0

    assert (
        db_api_with_initialized_first_course.store_score(FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(1))
        == 1
    )

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).one()
    assert grade.user_on_course_id == user_on_course.id
    assert grade.task.name == "task_0_0"
    assert grade.score == 1

    stats, all_scores, bonus_score, scores = get_user_results(
        db_api_with_initialized_first_course, FIRST_COURSE_NAME, TEST_USERNAME
    )

    assert_stats(stats, FIRST_COURSE_EXPECTED_STATS_KEYS, {"task_0_0": 1.0})

    assert all_scores == {TEST_USERNAME: named_scores({"task_0_0": (1, False)})}
    assert bonus_score == 0
    assert scores == {"task_0_0": 1}


def test_store_bonus_score(db_api_with_initialized_first_course, session):
    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0

    create_user(db_api_with_initialized_first_course)

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 0

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME, TEST_USERNAME, "bonus_score", update_func(1)
        )
        == 1
    )

    assert (
        db_api_with_initialized_first_course.store_score(FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(1))
        == 1
    )

    all_scores = db_api_with_initialized_first_course.get_all_scores_with_names(FIRST_COURSE_NAME)
    scores = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, TEST_USERNAME)

    assert all_scores == {TEST_USERNAME: named_scores({"bonus_score": (1, False), "task_0_0": (1, False)})}
    assert scores == {"bonus_score": 1, "task_0_0": 1}


def test_store_score_bonus_task(db_api_with_initialized_first_course, session):
    expected_score = 22

    create_user(db_api_with_initialized_first_course)

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME, TEST_USERNAME, "task_1_3", update_func(expected_score)
        )
        == expected_score
    )

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).join(Task).filter(Task.name == "task_1_3").one()
    assert grade.task.name == "task_1_3"
    assert grade.score == expected_score

    stats, all_scores, bonus_score, scores = get_user_results(
        db_api_with_initialized_first_course, FIRST_COURSE_NAME, TEST_USERNAME
    )

    assert_stats(stats, FIRST_COURSE_EXPECTED_STATS_KEYS, {"task_1_3": 1.0})

    assert all_scores == {TEST_USERNAME: named_scores({"task_1_3": (expected_score, False)})}
    assert bonus_score == expected_score
    assert scores == {"task_1_3": expected_score}


def test_store_score_with_changed_task_name(
    db_api,
    first_course_config,
    first_course_deadlines_config,
    first_course_deadlines_config_with_changed_task_name,
    first_course_updated_ui_config,
):
    create_course(db_api, first_course_config, first_course_deadlines_config)

    create_user(db_api)

    db_api.store_score(FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(10))

    update_course(
        db_api,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        first_course_deadlines_config_with_changed_task_name,
    )

    stats, all_scores, bonus_score, scores = get_user_results(db_api, FIRST_COURSE_NAME, TEST_USERNAME)

    assert_stats(stats, FIRST_COURSE_EXPECTED_STATS_KEYS - {"task_0_0"} | {"task_0_0_changed"}, {})

    assert all_scores == {TEST_USERNAME: named_scores({"task_0_0": (10, False)})}
    assert bonus_score == 0
    assert scores == {}


def test_sync_user_on_course(db_api_with_initialized_first_course, session):
    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0

    create_user(db_api_with_initialized_first_course)

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 0

    is_user_on_course = db_api_with_initialized_first_course.check_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME)
    assert not is_user_on_course

    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, False)

    is_course_admin = db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)
    assert not is_course_admin

    is_user_on_course = db_api_with_initialized_first_course.check_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME)
    assert is_user_on_course

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1

    # admin in gitlab
    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, True)

    is_course_admin = db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)
    assert is_course_admin

    # lost admin rules in gitlab, but in database stored that user is admin
    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, False)

    is_course_admin = db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)
    assert is_course_admin

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1


def _create_namespace_with_course(
    session: Session,
    *,
    created_by_id: int,
    course_id: int = 1,
    namespace_id: int = 1,
) -> Namespace:
    """Create a namespace and attach the given course to it."""
    namespace = Namespace(
        id=namespace_id,
        name="Test Namespace",
        slug="test-namespace",
        description=None,
        gitlab_group_id=namespace_id,
        created_by_id=created_by_id,
    )
    session.add(namespace)
    course = session.query(Course).filter_by(id=course_id).one()
    course.namespace_id = namespace_id
    session.commit()
    return namespace


def test_check_if_course_admin_namespace_owner(db_api_with_initialized_first_course, session):
    """Namespace owner (creator) must be treated as a course admin."""
    instance_admin_id = session.query(User).filter_by(username="instance_admin").one().id
    create_user(db_api_with_initialized_first_course)
    user = session.query(User).filter_by(username=TEST_USERNAME).one()

    _create_namespace_with_course(session, created_by_id=user.id)

    # user is the namespace owner, so it is a course admin even without UserOnCourse
    assert db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)
    # unrelated user (instance admin excluded from this check via a non-owner) is not
    assert instance_admin_id != user.id


def test_check_if_course_admin_namespace_admin_role(db_api_with_initialized_first_course, session):
    """User with namespace_admin role must be treated as a course admin."""
    owner_id = session.query(User).filter_by(username="instance_admin").one().id
    create_user(db_api_with_initialized_first_course)
    user = session.query(User).filter_by(username=TEST_USERNAME).one()

    _create_namespace_with_course(session, created_by_id=owner_id)

    session.add(
        UserOnNamespace(
            user_id=user.id,
            namespace_id=1,
            role=UserOnNamespaceRole.NAMESPACE_ADMIN,
            assigned_by_id=owner_id,
        )
    )
    session.commit()

    assert db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)


def test_check_if_course_admin_namespace_program_manager_is_not_admin(db_api_with_initialized_first_course, session):
    """User with only program_manager role in the namespace is not a course admin."""
    owner_id = session.query(User).filter_by(username="instance_admin").one().id
    create_user(db_api_with_initialized_first_course)
    user = session.query(User).filter_by(username=TEST_USERNAME).one()

    _create_namespace_with_course(session, created_by_id=owner_id)

    session.add(
        UserOnNamespace(
            user_id=user.id,
            namespace_id=1,
            role=UserOnNamespaceRole.PROGRAM_MANAGER,
            assigned_by_id=owner_id,
        )
    )
    session.commit()

    assert not db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)


def test_check_if_course_admin_no_namespace_uses_course_flag(db_api_with_initialized_first_course, session):
    """When the course has no namespace, only the per-course admin flag matters."""
    create_user(db_api_with_initialized_first_course)

    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, False)
    assert not db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)

    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, True)
    assert db_api_with_initialized_first_course.check_if_course_admin(FIRST_COURSE_NAME, TEST_USERNAME)


def test_many_users(db_api_with_initialized_first_course, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 3
    expected_user_on_course = 2
    expected_grades = 3
    expected_stats_ratio = 0.5

    create_user(db_api_with_initialized_first_course, STUDENT_1)

    db_api_with_initialized_first_course.store_score(FIRST_COURSE_NAME, TEST_USERNAME_1, "task_0_0", update_func(1))
    db_api_with_initialized_first_course.store_score(
        FIRST_COURSE_NAME, TEST_USERNAME_1, "task_1_3", update_func(expected_score_1)
    )

    create_user(db_api_with_initialized_first_course, STUDENT_2)

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME, TEST_USERNAME_2, "task_0_0", update_func(expected_score_2)
        )
        == expected_score_2
    )

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api_with_initialized_first_course.get_all_scores_with_names(FIRST_COURSE_NAME)
    bonus_score_user1 = db_api_with_initialized_first_course.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME_1)
    scores_user1 = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, TEST_USERNAME_1)
    bonus_score_user2 = db_api_with_initialized_first_course.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME_2)
    scores_user2 = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, TEST_USERNAME_2)

    assert_stats(stats, FIRST_COURSE_EXPECTED_STATS_KEYS, {"task_0_0": 1.0, "task_1_3": expected_stats_ratio})

    assert all_scores == {
        TEST_USERNAME_1: named_scores({"task_0_0": (1, False), "task_1_3": (expected_score_1, False)}, STUDENT_1),
        TEST_USERNAME_2: named_scores({"task_0_0": (expected_score_2, False)}, STUDENT_2),
    }
    assert bonus_score_user1 == expected_score_1
    assert scores_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score_user2 == 0
    assert scores_user2 == {"task_0_0": expected_score_2}


def test_many_courses(db_api_with_two_initialized_courses, session):
    create_user(db_api_with_two_initialized_courses)

    db_api_with_two_initialized_courses.store_score(FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(30))
    db_api_with_two_initialized_courses.store_score(SECOND_COURSE_NAME, TEST_USERNAME, "task_1_3", update_func(40))
    expected_users = 2
    expected_user_on_course = 2
    expected_grades = 2

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats1 = db_api_with_two_initialized_courses.get_stats(FIRST_COURSE_NAME)
    all_scores1 = db_api_with_two_initialized_courses.get_all_scores_with_names(FIRST_COURSE_NAME)
    bonus_score_user1 = db_api_with_two_initialized_courses.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME)
    scores_user1 = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, TEST_USERNAME)

    assert_stats(stats1, FIRST_COURSE_EXPECTED_STATS_KEYS, {"task_0_0": 1.0})

    assert all_scores1 == {TEST_USERNAME: named_scores({"task_0_0": (30, False)})}
    assert bonus_score_user1 == 0
    assert scores_user1 == {"task_0_0": 30}

    stats2 = db_api_with_two_initialized_courses.get_stats(SECOND_COURSE_NAME)
    all_scores2 = db_api_with_two_initialized_courses.get_all_scores_with_names(SECOND_COURSE_NAME)
    bonus_score_user2 = db_api_with_two_initialized_courses.get_bonus_score(SECOND_COURSE_NAME, TEST_USERNAME)
    scores_user2 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, TEST_USERNAME)

    assert_stats(stats2, SECOND_COURSE_EXPECTED_STATS_KEYS, {"task_1_3": 1.0})

    user2_score = 40
    assert all_scores2 == {TEST_USERNAME: named_scores({"task_1_3": (user2_score, False)})}
    assert bonus_score_user2 == user2_score
    assert scores_user2 == {"task_1_3": user2_score}


def test_many_users_and_courses(db_api_with_two_initialized_courses, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 3
    expected_user_on_course = 4
    expected_grades = 5
    expected_stats_ratio = 0.5

    create_user(db_api_with_two_initialized_courses, STUDENT_1)
    create_user(db_api_with_two_initialized_courses, STUDENT_2)

    db_api_with_two_initialized_courses.store_score(FIRST_COURSE_NAME, TEST_USERNAME_1, "task_0_0", update_func(1))
    db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME, TEST_USERNAME_1, "task_1_3", update_func(expected_score_1)
    )
    db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME, TEST_USERNAME_2, "task_0_0", update_func(expected_score_2)
    )

    db_api_with_two_initialized_courses.store_score(SECOND_COURSE_NAME, TEST_USERNAME_1, "task_1_0", update_func(99))
    db_api_with_two_initialized_courses.store_score(SECOND_COURSE_NAME, TEST_USERNAME_2, "task_1_1", update_func(7))

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats1 = db_api_with_two_initialized_courses.get_stats(FIRST_COURSE_NAME)
    all_scores1 = db_api_with_two_initialized_courses.get_all_scores_with_names(FIRST_COURSE_NAME)
    bonus_score1_user1 = db_api_with_two_initialized_courses.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME_1)
    scores1_user1 = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, TEST_USERNAME_1)
    bonus_score1_user2 = db_api_with_two_initialized_courses.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME_2)
    scores1_user2 = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, TEST_USERNAME_2)

    assert_stats(stats1, FIRST_COURSE_EXPECTED_STATS_KEYS, {"task_0_0": 1.0, "task_1_3": expected_stats_ratio})

    assert all_scores1 == {
        TEST_USERNAME_1: named_scores({"task_0_0": (1, False), "task_1_3": (expected_score_1, False)}, STUDENT_1),
        TEST_USERNAME_2: named_scores({"task_0_0": (expected_score_2, False)}, STUDENT_2),
    }
    assert bonus_score1_user1 == expected_score_1
    assert scores1_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score1_user2 == 0
    assert scores1_user2 == {"task_0_0": expected_score_2}

    stats2 = db_api_with_two_initialized_courses.get_stats(SECOND_COURSE_NAME)
    all_scores2 = db_api_with_two_initialized_courses.get_all_scores_with_names(SECOND_COURSE_NAME)
    bonus_score2_user1 = db_api_with_two_initialized_courses.get_bonus_score(SECOND_COURSE_NAME, TEST_USERNAME_1)
    scores2_user1 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, TEST_USERNAME_1)
    bonus_score2_user2 = db_api_with_two_initialized_courses.get_bonus_score(SECOND_COURSE_NAME, TEST_USERNAME_2)
    scores2_user2 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, TEST_USERNAME_2)

    assert_stats(
        stats2, SECOND_COURSE_EXPECTED_STATS_KEYS, {"task_1_0": expected_stats_ratio, "task_1_1": expected_stats_ratio}
    )

    assert all_scores2 == {
        TEST_USERNAME_1: named_scores({"task_1_0": (99, False)}, STUDENT_1),
        TEST_USERNAME_2: named_scores({"task_1_1": (7, False)}, STUDENT_2),
    }
    assert bonus_score2_user1 == 0
    assert scores2_user1 == {"task_1_0": 99}
    assert bonus_score2_user2 == 0
    assert scores2_user2 == {"task_1_1": 7}


def test_deadlines(db_api_with_two_initialized_courses, session):
    deadline1 = (
        session.query(Deadline)
        .join(TaskGroup)
        .filter(TaskGroup.name == "group_1")
        .join(Course)
        .filter(Course.name == FIRST_COURSE_NAME)
        .one()
    )

    assert deadline1.start == datetime(2000, 1, 2, 18, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    assert deadline1.steps == {0.5: datetime(2000, 2, 2, 23, 59, tzinfo=ZoneInfo("Europe/Berlin"))}
    assert deadline1.end == datetime(2000, 2, 2, 23, 59, tzinfo=ZoneInfo("Europe/Berlin"))

    deadline2 = (
        session.query(Deadline)
        .join(TaskGroup)
        .filter(TaskGroup.name == "group_1")
        .join(Course)
        .filter(Course.name == SECOND_COURSE_NAME)
        .one()
    )

    assert deadline2.start == datetime(2000, 1, 1, 18, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    assert deadline2.steps == {0.5: datetime(2000, 2, 1, 23, 59, tzinfo=ZoneInfo("Europe/Moscow"))}
    assert deadline2.end == datetime(2000, 2, 1, 23, 59, tzinfo=ZoneInfo("Europe/Moscow"))


def test_bad_requests(db_api_with_two_initialized_courses, session):
    bonus_score = db_api_with_two_initialized_courses.get_bonus_score(FIRST_COURSE_NAME, "unknown_user")
    scores = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, "unknown_user")

    assert bonus_score == 0
    assert scores == {}

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0
    assert session.query(Grade).count() == 0


def test_auto_tables_creation(engine, alembic_cfg, postgres_container, first_course_config):
    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.downgrade(alembic_cfg, "base")  # Base.metadata.drop_all(engine)

    with pytest.raises(ProgrammingError) as exc_info:
        db_api = DataBaseApi(
            DatabaseConfig(
                database_url=postgres_container.get_connection_url(),
                instance_admin_username="admin",
                apply_migrations=False,
            )
        )

        with Session(engine) as session:
            test_not_initialized_course(session, db_api, first_course_config)

    assert isinstance(exc_info.value.orig, UndefinedTable)

    db_api = DataBaseApi(db_config(postgres_container.get_connection_url()))  # apply_migrations=True

    with Session(engine) as session:
        test_not_initialized_course(session, db_api, first_course_config)


def test_auto_database_migration(engine, alembic_cfg, postgres_container, first_course_config):
    script = ScriptDirectory.from_config(alembic_cfg)
    revisions = list(script.walk_revisions("base", "head"))
    revisions.reverse()

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection

        for revision in revisions:
            command.downgrade(alembic_cfg, "base")
            command.upgrade(alembic_cfg, revision.revision)

            db_api = DataBaseApi(db_config(postgres_container.get_connection_url()))

            with Session(engine) as session:
                test_not_initialized_course(session, db_api, first_course_config)


def test_store_score_integrity_error(db_api_with_two_initialized_courses, session):
    user = make_user()

    session.add(user)
    session.commit()

    create_user(db_api_with_two_initialized_courses)

    score = db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(1)
    )
    assert score == 1

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1


def test_store_score_update_error(db_api_with_two_initialized_courses, session):
    create_user(db_api_with_two_initialized_courses)

    def failing_update(_, score):
        raise ValueError("Update failed")

    with pytest.raises(ValueError) as exc_info:
        db_api_with_two_initialized_courses.store_score(FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", failing_update)
    assert "Update failed" in str(exc_info.value)

    assert session.query(Grade).count() == 0


def test_get_course_success(db_api_with_two_initialized_courses, first_course_config, second_course_config):
    first_course_config.status = CourseStatus.HIDDEN
    course = db_api_with_two_initialized_courses.get_course(FIRST_COURSE_NAME)
    assert course.__dict__ == ManytaskCourse(first_course_config).__dict__

    second_course_config.status = CourseStatus.HIDDEN
    course = db_api_with_two_initialized_courses.get_course(SECOND_COURSE_NAME)
    assert course.__dict__ == ManytaskCourse(second_course_config).__dict__


def test_get_course_unknown(db_api_with_two_initialized_courses):
    course = db_api_with_two_initialized_courses.get_course("Unknown course")
    assert course is None


def test_store_score_raises_exception_if_user_does_not_exist(db_api_with_initialized_first_course):
    with pytest.raises(NoResultFound):
        db_api_with_initialized_first_course.store_score(FIRST_COURSE_NAME, TEST_USERNAME_2, "task_0_0", update_func(1))


def test_store_get_stored_user_raises_exception_if_user_does_not_exist(db_api_with_initialized_first_course):
    with pytest.raises(NoResultFound):
        db_api_with_initialized_first_course.get_stored_user_by_username(TEST_USERNAME)


def test_store_sync_user_on_course_raises_exception_if_user_does_not_exist(db_api_with_initialized_first_course):
    with pytest.raises(NoResultFound):
        db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, False)


def test_apply_migrations_exceptions(db_api_with_two_initialized_courses, postgres_container):
    with patch.object(command, "upgrade", side_effect=TestException()):
        with pytest.raises(TestException):
            db_api_with_two_initialized_courses._apply_migrations(postgres_container.get_connection_url())

    with patch.object(command, "upgrade", side_effect=IntegrityError(None, None, TestException())):
        with pytest.raises(IntegrityError) as exc_info:
            db_api_with_two_initialized_courses._apply_migrations(postgres_container.get_connection_url())

        assert isinstance(exc_info.value.orig, TestException)

    with patch.object(command, "upgrade", side_effect=IntegrityError(None, None, UniqueViolation())):
        db_api_with_two_initialized_courses._apply_migrations(postgres_container.get_connection_url())

    with patch.object(command, "upgrade", side_effect=ProgrammingError(None, None, TestException())):
        with pytest.raises(ProgrammingError) as exc_info:
            db_api_with_two_initialized_courses._apply_migrations(postgres_container.get_connection_url())

        assert isinstance(exc_info.value.orig, TestException)

    with patch.object(command, "upgrade", side_effect=ProgrammingError(None, None, DuplicateColumn())):
        db_api_with_two_initialized_courses._apply_migrations(postgres_container.get_connection_url())

    with patch.object(command, "upgrade", side_effect=DuplicateTable()):
        db_api_with_two_initialized_courses._apply_migrations(postgres_container.get_connection_url())


def test_sync_and_get_admin_status_admin_update(db_api_with_two_initialized_courses, session):
    user, _ = add_user_on_course(session, is_course_admin=False)

    db_api_with_two_initialized_courses.sync_and_get_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, True)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_sync_and_get_admin_status_admin_no_update(db_api_with_two_initialized_courses, session):
    user, _ = add_user_on_course(session, is_course_admin=True)

    db_api_with_two_initialized_courses.sync_and_get_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, False)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_set_course_admin_status_grant(db_api_with_two_initialized_courses, session):
    user, _ = add_user_on_course(session, is_course_admin=False)

    db_api_with_two_initialized_courses.set_course_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, True)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_set_course_admin_status_revoke(db_api_with_two_initialized_courses, session):
    user, _ = add_user_on_course(session, is_course_admin=True)

    db_api_with_two_initialized_courses.set_course_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, False)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert not updated_user_on_course.is_course_admin


def test_set_course_admin_status_can_revoke_last_admin(db_api_with_two_initialized_courses, session):
    # a course may have zero course admins, unlike an instance
    user, _ = add_user_on_course(session, is_course_admin=True)

    db_api_with_two_initialized_courses.set_course_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, False)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert not updated_user_on_course.is_course_admin


def test_set_course_admin_status_unknown_user(db_api_with_two_initialized_courses, session):
    # should not raise, just log an error
    db_api_with_two_initialized_courses.set_course_admin_status(FIRST_COURSE_NAME, "nonexistent_user", True)


def test_get_course_users_with_admin_status(db_api_with_two_initialized_courses, session):
    add_user_on_course(session, is_course_admin=True)
    add_user_on_course(session, student=STUDENT_1, user_id=3, is_course_admin=False)

    result = db_api_with_two_initialized_courses.get_course_users_with_admin_status(FIRST_COURSE_NAME)

    result_map = {stored_user.username: is_admin for stored_user, is_admin in result}
    assert result_map == {TEST_USERNAME: True, TEST_USERNAME_1: False}


def test_get_course_users_with_admin_status_unknown_course(db_api_with_two_initialized_courses):
    assert db_api_with_two_initialized_courses.get_course_users_with_admin_status("nonexistent_course") == []


def test_check_user_on_course(db_api_with_two_initialized_courses, session):
    add_user_on_course(session, is_course_admin=True)

    assert db_api_with_two_initialized_courses.check_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME)


def test_update_or_create_user_existing(db_api_with_two_initialized_courses, session):
    user = make_user(id=2)
    session.add(user)
    session.commit()

    assert session.query(User).filter_by(username=TEST_USERNAME).one().id == user.id
    create_user(db_api_with_two_initialized_courses)
    assert session.query(User).filter_by(username=TEST_USERNAME).one().id == user.id


def test_update_or_create_user_nonexisting(db_api_with_two_initialized_courses, session):
    assert session.query(User).filter_by(username=TEST_USERNAME).one_or_none() is None
    create_user(db_api_with_two_initialized_courses)
    assert session.query(User).filter_by(username=TEST_USERNAME).one()


def test_convert_timedelta_to_datetime():
    start = datetime(2025, 5, 5, 5, 5, tzinfo=ZoneInfo("Europe/Berlin"))
    value_datetime = datetime(2026, 6, 6, 6, 6, tzinfo=ZoneInfo("Europe/Berlin"))
    value_timedelta = timedelta(days=397, hours=1, minutes=1)  # value_datetime - start

    assert DataBaseApi._convert_timedelta_to_datetime(start, value_datetime) == value_datetime
    assert DataBaseApi._convert_timedelta_to_datetime(start, value_timedelta) == value_datetime


def change_timedelta_to_datetime(group: ManytaskGroupConfig) -> ManytaskGroupConfig:
    group.steps = {k: DataBaseApi._convert_timedelta_to_datetime(group.start, v) for k, v in group.steps.items()}
    group.end = DataBaseApi._convert_timedelta_to_datetime(group.start, group.end)

    return group


def check_find_task(
    db_api,
    course_name,
    course_deadlines_config,
):
    for group in course_deadlines_config.groups:
        group = change_timedelta_to_datetime(group)

        for task in group.tasks:
            if not task.enabled:
                with pytest.raises(TaskDisabledError) as e:
                    db_api.find_task(course_name, task.name)
                assert str(e.value) == f"Task {task.name} is disabled"
                continue
            if not group.enabled:
                with pytest.raises(TaskDisabledError) as e:
                    db_api.find_task(course_name, task.name)
                assert str(e.value) == f"Task {task.name} group {group.name} is disabled"
                continue

            found_course, found_group, found_task = db_api.find_task(course_name, task.name)

            assert found_group == group
            assert found_task == task
            assert found_course.course_name == course_name


@pytest.mark.parametrize("course_number", [1, 2])
def test_find_task(
    db_api_with_two_initialized_courses,
    first_course_deadlines_config,
    second_course_deadlines_config,
    course_number,
):
    course_name = (FIRST_COURSE_NAME, SECOND_COURSE_NAME)[course_number - 1]
    course_deadlines_config = (first_course_deadlines_config, second_course_deadlines_config)[course_number - 1]

    check_find_task(db_api_with_two_initialized_courses, course_name, course_deadlines_config)


@pytest.mark.parametrize("config_number", [1, 2, 3])
def test_find_task_with_resync(
    db_api_with_two_initialized_courses,
    second_course_deadlines_config,
    first_course_deadlines_config_with_changed_order_of_groups,
    first_course_deadlines_config_with_changed_order_of_tasks,
    first_course_updated_ui_config,
    config_number,
):
    course_deadlines_config = (
        second_course_deadlines_config,
        first_course_deadlines_config_with_changed_order_of_groups,
        first_course_deadlines_config_with_changed_order_of_tasks,
    )[config_number - 1]

    update_course(
        db_api_with_two_initialized_courses,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        course_deadlines_config,
    )

    check_find_task(db_api_with_two_initialized_courses, FIRST_COURSE_NAME, course_deadlines_config)


def test_find_task_not_found(db_api_with_two_initialized_courses):
    task_name = "non-existent_task"

    with pytest.raises(KeyError) as e:
        db_api_with_two_initialized_courses.find_task(FIRST_COURSE_NAME, task_name)
    assert e.value.args[0] == f"Task {task_name} not found"

    with pytest.raises(KeyError) as e:
        db_api_with_two_initialized_courses.find_task(SECOND_COURSE_NAME, task_name)
    assert e.value.args[0] == f"Task {task_name} not found"


def check_get_groups(
    db_api,
    course_name,
    course_deadlines_config,
    enabled,
    started,
    now,
):
    result_groups = db_api.get_groups(course_name, enabled=enabled, started=started, now=now)

    assert len([group.name for group in result_groups]) == len(set([group.name for group in result_groups]))

    groups = [change_timedelta_to_datetime(group) for group in course_deadlines_config.groups]

    if enabled is not None:
        groups = [group for group in groups if group.enabled == enabled]
        for i in range(len(groups)):
            groups[i].tasks = [task for task in groups[i].tasks if task.enabled == enabled]

    if started is not None:
        if started:
            groups = [group for group in groups if group.start <= FIXED_CURRENT_TIME]
        else:
            groups = [group for group in groups if group.start > FIXED_CURRENT_TIME]

    assert result_groups == groups


@pytest.mark.parametrize("course_number", [1, 2])
@pytest.mark.parametrize("enabled", [None, True, False])
@pytest.mark.parametrize("started", [None, True, False])
@pytest.mark.parametrize("now", [FIXED_CURRENT_TIME, None])
def test_get_groups(  # noqa: PLR0913
    db_api_with_two_initialized_courses,
    first_course_deadlines_config,
    second_course_deadlines_config,
    course_number,
    enabled,
    started,
    now,
):
    course_name = (FIRST_COURSE_NAME, SECOND_COURSE_NAME)[course_number - 1]
    course_deadlines_config = (first_course_deadlines_config, second_course_deadlines_config)[course_number - 1]

    check_get_groups(db_api_with_two_initialized_courses, course_name, course_deadlines_config, enabled, started, now)


@pytest.mark.parametrize("config_number", [1, 2, 3])
@pytest.mark.parametrize("enabled", [None, True, False])
@pytest.mark.parametrize("started", [None, True, False])
@pytest.mark.parametrize("now", [FIXED_CURRENT_TIME, None])
def test_get_groups_with_resync(  # noqa: PLR0913
    db_api_with_two_initialized_courses,
    second_course_deadlines_config,
    first_course_deadlines_config_with_changed_order_of_groups,
    first_course_deadlines_config_with_changed_order_of_tasks,
    first_course_updated_ui_config,
    config_number,
    enabled,
    started,
    now,
):
    course_deadlines_config = (
        second_course_deadlines_config,
        first_course_deadlines_config_with_changed_order_of_groups,
        first_course_deadlines_config_with_changed_order_of_tasks,
    )[config_number - 1]

    update_course(
        db_api_with_two_initialized_courses,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        course_deadlines_config,
    )

    check_get_groups(
        db_api_with_two_initialized_courses, FIRST_COURSE_NAME, course_deadlines_config, enabled, started, now
    )


def test_edit_course(db_api_with_initialized_first_course, edited_first_course_config, session):
    db_api_with_initialized_first_course.edit_course(edited_first_course_config)

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert_course(
        course,
        registration_secret=edited_first_course_config.registration_secret,
        show_allscores=False,
        status=CourseStatus.IN_PROGRESS,
        gitlab_course_group=edited_first_course_config.gitlab_course_group,
        gitlab_course_public_repo=edited_first_course_config.gitlab_course_public_repo,
        gitlab_course_students_group=edited_first_course_config.gitlab_course_students_group,
        gitlab_default_branch=edited_first_course_config.gitlab_default_branch,
        timezone="Europe/Berlin",
        max_submissions=10,
        submission_penalty=0.1,
    )

    assert_empty_stats(
        db_api_with_initialized_first_course,
        FIRST_COURSE_NAME,
        FIRST_COURSE_EXPECTED_STATS_KEYS,
        FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED,
    )


def test_zero_instance_admin_is_in_db_and_set_admin_status(db_api, session):
    assert session.query(User).count() == 1
    assert session.query(User).one().is_instance_admin

    db_api.set_instance_admin_status(session.query(User).one().username, False)
    assert session.query(User).one().is_instance_admin  # should not be possible to remove last admin

    create_user(db_api)

    assert not session.query(User).filter_by(username=TEST_USERNAME).one().is_instance_admin
    db_api.set_instance_admin_status(TEST_USERNAME, True)
    assert session.query(User).filter_by(username=TEST_USERNAME).one().is_instance_admin
    db_api.set_instance_admin_status(TEST_USERNAME, False)
    assert not session.query(User).filter_by(username=TEST_USERNAME).one().is_instance_admin


def test_update_user_profile(db_api, session):
    create_user(db_api)

    db_api.update_user_profile(TEST_USERNAME, "NewFirstName", "NewLastName")
    updated_user = session.query(User).filter_by(username=TEST_USERNAME).populate_existing().one()

    assert updated_user.first_name == "NewFirstName"
    assert updated_user.last_name == "NewLastName"

    db_api.update_user_profile(TEST_USERNAME, None, "LastName")
    updated_user = session.query(User).filter_by(username=TEST_USERNAME).populate_existing().one()

    assert updated_user.first_name == "NewFirstName"
    assert updated_user.last_name == "LastName"

    db_api.update_user_profile(TEST_USERNAME, "FirstName", None)
    updated_user = session.query(User).filter_by(username=TEST_USERNAME).populate_existing().one()

    assert updated_user.first_name == "FirstName"
    assert updated_user.last_name == "LastName"


def test_grade_config_estimation_with_adding_grade(
    db_api_with_two_initialized_courses,
    first_course_updated_ui_config,
    second_course_deadlines_config,
    second_course_grade_config_with_additional_grade,
    session,
):
    mock_scores = [
        {"percent": 75.0, "large_count": 2, "scores": {}},
        {"percent": 83.2, "large_count": 3, "scores": {}},
        {"percent": 92.7, "large_count": 1, "scores": {}},
        {"percent": 60.4, "large_count": 2, "scores": {}},
        {"percent": 52.8, "large_count": 0, "scores": {}},
    ]
    mock_grades = [4, 5, 2, 4, 2]
    mock_grades_updated = [4, 5, 3, 4, 2]
    grade_config_data = db_api_with_two_initialized_courses.get_grades(SECOND_COURSE_NAME)

    for i, score in enumerate(mock_scores):
        assert grade_config_data.evaluate(score) == mock_grades[i]

    update_course(
        db_api_with_two_initialized_courses,
        SECOND_COURSE_NAME,
        first_course_updated_ui_config,
        second_course_deadlines_config,
        second_course_grade_config_with_additional_grade,
    )

    grade_config_data = db_api_with_two_initialized_courses.get_grades(SECOND_COURSE_NAME)

    for i, score in enumerate(mock_scores):
        assert grade_config_data.evaluate(score) == mock_grades_updated[i]


def test_calculate_and_save_grade_allows_downgrade_in_progress(
    db_api_with_initialized_first_course,
    session,
):
    course = session.query(Course).filter_by(name=FIRST_COURSE_NAME).one()
    course.status = CourseStatus.IN_PROGRESS
    session.commit()

    create_user(db_api_with_initialized_first_course)
    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, False)

    user_on_course = (
        session.query(UserOnCourse)
        .join(User)
        .filter(User.username == TEST_USERNAME, UserOnCourse.course_id == course.id)
        .one()
    )
    user_on_course.final_grade = GRADE_BEFORE_DOWNGRADE
    session.commit()

    row = {"percent": 0, "large_count": 0}
    new_grade = db_api_with_initialized_first_course.calculate_and_save_grade(FIRST_COURSE_NAME, TEST_USERNAME, row)

    assert new_grade == GRADE_AFTER_DOWNGRADE_IN_PROGRESS
    session.expire_all()
    assert (
        session.query(UserOnCourse).filter_by(id=user_on_course.id).one().final_grade
        == GRADE_AFTER_DOWNGRADE_IN_PROGRESS
    )


def test_calculate_and_save_grade_no_downgrade_in_doreshka_and_all_tasks_issued(
    db_api_with_initialized_first_course,
    session,
):
    create_user(db_api_with_initialized_first_course)
    db_api_with_initialized_first_course.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME, False)

    course = session.query(Course).filter_by(name=FIRST_COURSE_NAME).one()
    user_on_course = (
        session.query(UserOnCourse)
        .join(User)
        .filter(User.username == TEST_USERNAME, UserOnCourse.course_id == course.id)
        .one()
    )

    row = {"percent": 0, "large_count": 0}

    course.status = CourseStatus.DORESHKA
    user_on_course.final_grade = GRADE_FROZEN_VALUE
    session.commit()
    new_grade = db_api_with_initialized_first_course.calculate_and_save_grade(FIRST_COURSE_NAME, TEST_USERNAME, row)
    assert new_grade == GRADE_FROZEN_VALUE

    course.status = CourseStatus.ALL_TASKS_ISSUED
    user_on_course.final_grade = GRADE_FROZEN_VALUE
    session.commit()
    new_grade = db_api_with_initialized_first_course.calculate_and_save_grade(FIRST_COURSE_NAME, TEST_USERNAME, row)
    assert new_grade == GRADE_FROZEN_VALUE


def test_grade_config_estimation_with_removing_grade(
    db_api_with_two_initialized_courses,
    first_course_updated_ui_config,
    second_course_deadlines_config,
    second_course_grade_config,
    second_course_grade_config_with_additional_grade,
    session,
):
    update_course(
        db_api_with_two_initialized_courses,
        SECOND_COURSE_NAME,
        first_course_updated_ui_config,
        second_course_deadlines_config,
        second_course_grade_config_with_additional_grade,
    )

    mock_scores = [
        {"percent": 75.0, "large_count": 2, "scores": {}},
        {"percent": 83.2, "large_count": 3, "scores": {}},
        {"percent": 92.7, "large_count": 1, "scores": {}},
        {"percent": 60.4, "large_count": 2, "scores": {}},
        {"percent": 52.8, "large_count": 0, "scores": {}},
    ]
    mock_grades = [4, 5, 3, 4, 2]
    mock_grades_updated = [4, 5, 2, 4, 2]
    grade_config_data = db_api_with_two_initialized_courses.get_grades(SECOND_COURSE_NAME)

    for i, score in enumerate(mock_scores):
        assert grade_config_data.evaluate(score) == mock_grades[i]

    update_course(
        db_api_with_two_initialized_courses,
        SECOND_COURSE_NAME,
        first_course_updated_ui_config,
        second_course_deadlines_config,
        second_course_grade_config,
    )

    grade_config_data = db_api_with_two_initialized_courses.get_grades(SECOND_COURSE_NAME)

    for i, score in enumerate(mock_scores):
        assert grade_config_data.evaluate(score) == mock_grades_updated[i]


@pytest.mark.parametrize(
    "method_name, method_kwargs",
    [
        ("get_all_scores_with_names", {"course_name": FIRST_COURSE_NAME}),
        ("recalculate_all_grades", {"course_name": FIRST_COURSE_NAME}),
        ("get_stats", {"course_name": FIRST_COURSE_NAME}),
        ("get_groups", {"course_name": FIRST_COURSE_NAME, "enabled": True, "started": True}),
        ("get_user_courses_names_with_statuses", {"username": TEST_USERNAME_1}),
        ("get_courses_where_course_admin", {"username": TEST_USERNAME_1}),
    ],
)
def test_constant_queries(  # noqa: PLR0913
    db_api_with_initialized_first_course,
    second_course_config,
    second_course_deadlines_config,
    second_course_grade_config,
    session,
    engine,
    method_name,
    method_kwargs,
):
    """Query count must not grow with entity count (students or courses)."""
    db_api = db_api_with_initialized_first_course
    method = getattr(db_api, method_name)

    # Setup 1st course and 1st student
    course1 = session.query(Course).filter_by(name=FIRST_COURSE_NAME).one()
    course1.status = CourseStatus.IN_PROGRESS
    session.commit()

    create_user(db_api, STUDENT_1)
    db_api.store_score(FIRST_COURSE_NAME, STUDENT_1.username, "task_0_0", update_func(1))
    db_api.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME_1, True)

    with query_counter(engine) as counter:
        method(**method_kwargs)
    queries_initial = counter.value

    # Setup 2nd course
    create_course(db_api, second_course_config, second_course_deadlines_config, second_course_grade_config)
    course2 = session.query(Course).filter_by(name=SECOND_COURSE_NAME).one()
    course2.status = CourseStatus.IN_PROGRESS
    session.commit()

    # Register 1st student on 2nd course
    db_api.store_score(SECOND_COURSE_NAME, STUDENT_1.username, "task_0_0", update_func(1))
    db_api.sync_user_on_course(SECOND_COURSE_NAME, TEST_USERNAME_1, True)

    # Setup 2nd student and register on both courses
    create_user(db_api, STUDENT_2)
    db_api.store_score(FIRST_COURSE_NAME, STUDENT_2.username, "task_0_0", update_func(1))
    db_api.sync_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME_2, True)
    db_api.store_score(SECOND_COURSE_NAME, STUDENT_2.username, "task_0_0", update_func(1))
    db_api.sync_user_on_course(SECOND_COURSE_NAME, TEST_USERNAME_2, True)

    with query_counter(engine) as counter:
        method(**method_kwargs)
    queries_scaled = counter.value

    assert queries_initial == queries_scaled

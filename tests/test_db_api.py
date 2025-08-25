import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import yaml
from alembic import command
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from psycopg2.errors import DuplicateColumn, DuplicateTable, UndefinedTable, UniqueViolation
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
from manytask.course import CourseConfig, CourseStatus
from manytask.database import DataBaseApi, DatabaseConfig, TaskDisabledError
from manytask.models import Course, Deadline, Grade, Task, TaskGroup, User, UserOnCourse
from tests.constants import (
    DEADLINES_CONFIG_FILES,
    FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED,
    FIRST_COURSE_EXPECTED_STATS_KEYS,
    FIRST_COURSE_NAME,
    FIXED_CURRENT_TIME,
    GRADE_CONFIG_FILES,
    SECOND_COURSE_EXPECTED_MAX_SCORE_STARTED,
    SECOND_COURSE_EXPECTED_STATS_KEYS,
    SECOND_COURSE_NAME,
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
    with open(GRADE_CONFIG_FILES[0], "r") as f:
        grade_config_data = yaml.load(f, Loader=yaml.SafeLoader)

    return ManytaskFinalGradeConfig(**grade_config_data["grades"])


@pytest.fixture
def first_course_grade_config_with_changed_numbers():
    with open(GRADE_CONFIG_FILES[0], "r") as f:
        grade_config_data = yaml.load(f, Loader=yaml.SafeLoader)

    grade_config_data_changed_numbers = dict()
    grade_config_data_changed_numbers["grades"] = dict()
    for key, value in grade_config_data["grades"]["grades"].items():
        grade_config_data_changed_numbers["grades"][key + 2] = value.copy()

    return ManytaskFinalGradeConfig(**grade_config_data_changed_numbers)


@pytest.fixture
def second_course_grade_config():
    with open(GRADE_CONFIG_FILES[1], "r") as f:
        grade_config_data = yaml.load(f, Loader=yaml.SafeLoader)

    return ManytaskFinalGradeConfig(**grade_config_data["grades"])


@pytest.fixture
def second_course_grade_config_with_additional_grade():
    with open(GRADE_CONFIG_FILES[1], "r") as f:
        grade_config_data = yaml.load(f, Loader=yaml.SafeLoader)

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
        task_url_template="https://gitlab.test.com/test_updated/$GROUP_NAME/$TASK_NAME",
        links={"TG Channel": "https://t.me/joinchat_updated/", "TG Chat": "https://t.me/joinchat_updated/"},
    )


@pytest.fixture
def second_course_config():
    return CourseConfig(
        course_name=SECOND_COURSE_NAME,
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
    )


@pytest.fixture
def edited_second_course_config(second_course_config):
    edited_config = second_course_config
    edited_config.status = CourseStatus.IN_PROGRESS

    return edited_config


@pytest.fixture
def first_course_deadlines_config():
    with open(DEADLINES_CONFIG_FILES[0], "r") as f:
        deadlines_config_data = yaml.load(f, Loader=yaml.SafeLoader)
    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def second_course_deadlines_config():
    with open(DEADLINES_CONFIG_FILES[1], "r") as f:
        deadlines_config_data = yaml.load(f, Loader=yaml.SafeLoader)
    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def first_course_deadlines_config_with_changed_task_name():
    with open(DEADLINES_CONFIG_FILES[0], "r") as f:
        deadlines_config_data = yaml.load(f, Loader=yaml.SafeLoader)

    # change task name: task_0_0 -> task_0_0_changed
    deadlines_config_data["deadlines"]["schedule"][0]["tasks"][0]["task"] += "_changed"

    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def first_course_deadlines_config_with_changed_order_of_groups():
    with open(DEADLINES_CONFIG_FILES[0], "r") as f:
        deadlines_config_data = yaml.load(f, Loader=yaml.SafeLoader)

    # reverse order of the groups
    deadlines_config_data["deadlines"]["schedule"] = list(reversed(deadlines_config_data["deadlines"]["schedule"]))

    return ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])


@pytest.fixture
def first_course_deadlines_config_with_changed_order_of_tasks():
    with open(DEADLINES_CONFIG_FILES[0], "r") as f:
        deadlines_config_data = yaml.load(f, Loader=yaml.SafeLoader)

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


@pytest.fixture(autouse=True)
def setup_environment(monkeypatch):
    load_dotenv()
    if not os.getenv("MANYTASK_COURSE_TOKEN"):
        monkeypatch.setenv("MANYTASK_COURSE_TOKEN", "test_token")
    monkeypatch.setenv("FLASK_SECRET_KEY", "test_key")
    monkeypatch.setenv("TESTING", "true")
    yield


def update_func(add: int):
    def _update_func(_, score):
        return score + add

    return _update_func


def test_not_initialized_course(session, db_api, first_course_config):
    db_api.create_course(settings_config=first_course_config)
    course_name = first_course_config.course_name

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == FIRST_COURSE_NAME
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.status == CourseStatus.CREATED

    assert course.gitlab_course_group == "test_course_group"
    assert course.gitlab_course_public_repo == "test_course_public_repo"
    assert course.gitlab_course_students_group == "test_course_students_group"
    assert course.gitlab_default_branch == "test_default_branch"

    assert course.task_url_template == "https://gitlab.test.com/test/$GROUP_NAME/$TASK_NAME"
    assert course.links == {"TG Channel": "https://t.me/joinchat/", "TG Chat": "https://t.me/joinchat/"}

    assert course.timezone == "UTC"
    assert course.max_submissions is None
    assert course.submission_penalty == 0

    stats = db_api.get_stats(course_name)
    all_scores = db_api.get_all_scores_with_names(course_name)
    bonus_score = db_api.get_bonus_score(course_name, "some_user")
    scores = db_api.get_scores(course_name, "some_user")
    max_score_started = db_api.max_score_started(course_name)

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}
    assert max_score_started == 0


def test_initialized_course(db_api_with_initialized_first_course, session):  # noqa: PLR0915
    expected_task_groups = 6
    expected_tasks = 19
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

    assert course.name == FIRST_COURSE_NAME
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.status

    assert course.gitlab_course_group == "test_course_group"
    assert course.gitlab_course_public_repo == "test_course_public_repo"
    assert course.gitlab_course_students_group == "test_course_students_group"
    assert course.gitlab_default_branch == "test_default_branch"

    assert course.task_url_template == "https://gitlab.test.com/test/$GROUP_NAME/$TASK_NAME"
    assert course.links == {"TG Channel": "https://t.me/joinchat/", "TG Chat": "https://t.me/joinchat/"}

    assert course.timezone == "Europe/Berlin"
    assert course.max_submissions == 10  # noqa: PLR2004
    assert course.submission_penalty == 0.1  # noqa: PLR2004

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert all(v == 0 for v in stats.values())
    assert (
        db_api_with_initialized_first_course.max_score_started(FIRST_COURSE_NAME)
        == FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED
    )

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == "group_" + task.name[len("task_")]

        assert task.is_bonus == (task.name in bonus_tasks)
        assert task.is_large == (task.name in large_tasks)
        assert task.is_special == (task.name in special_tasks)
        assert task.group.enabled != (task.group.name in disabled_groups)
        assert task.enabled != (task.name in disabled_tasks)

        # for convenience task score related to its name(exception is group_0, it has multiplier "1")
        # for example for task_1_3 score is 10, task_3_0 score is 30
        score_multiplier = int(task.name.split("_")[1])
        score_multiplier = 1 if score_multiplier == 0 else score_multiplier
        expected_task_score = score_multiplier * 10

        assert task.score == expected_task_score

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
    expected_task_groups = 8
    expected_tasks = 28
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

    assert course.name == FIRST_COURSE_NAME
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.status

    assert course.gitlab_course_group == "test_course_group"
    assert course.gitlab_course_public_repo == "test_course_public_repo"
    assert course.gitlab_course_students_group == "test_course_students_group"
    assert course.gitlab_default_branch == "test_default_branch"

    assert course.task_url_template == "https://gitlab.test.com/test_updated/$GROUP_NAME/$TASK_NAME"
    assert course.links == {"TG Channel": "https://t.me/joinchat_updated/", "TG Chat": "https://t.me/joinchat_updated/"}

    assert course.timezone == "Europe/Moscow"
    assert course.max_submissions == 20  # noqa: PLR2004
    assert course.submission_penalty == 0.2  # noqa: PLR2004

    stats = db_api.get_stats(FIRST_COURSE_NAME)
    assert set(stats.keys()) == SECOND_COURSE_EXPECTED_STATS_KEYS
    assert all(v == 0 for v in stats.values())
    assert db_api.max_score_started(FIRST_COURSE_NAME) == SECOND_COURSE_EXPECTED_MAX_SCORE_STARTED

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == "group_" + task.name[len("task_")]

        assert task.is_bonus == (task.name in bonus_tasks)
        assert task.is_large == (task.name in large_tasks)
        assert task.is_special == (task.name in special_tasks)
        assert task.group.enabled != (task.group.name in disabled_groups)
        assert task.enabled != (task.name in disabled_tasks)

        # for convenience task score related to its name(exception is group_0, it has multiplier "1")
        # for example for task_1_3 score is 10, task_3_0 score is 30
        score_multiplier = int(task.name.split("_")[1])
        score_multiplier = 1 if score_multiplier == 0 else score_multiplier
        expected_task_score = score_multiplier * 10

        assert task.score == expected_task_score


def test_resync_with_changed_task_name(
    db_api,
    first_course_config,
    first_course_deadlines_config,
    first_course_deadlines_config_with_changed_task_name,
    first_course_updated_ui_config,
    first_course_grade_config,
    session,
):
    expected_task_groups = 6
    expected_tasks = 20
    disabled_tasks = ("task_0_0", "task_2_1")

    create_course(db_api, first_course_config, first_course_deadlines_config, first_course_grade_config)
    update_course(
        db_api,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        first_course_deadlines_config_with_changed_task_name,
        first_course_grade_config,
    )

    stats = db_api.get_stats(FIRST_COURSE_NAME)
    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS - {"task_0_0"} | {"task_0_0_changed"}
    assert all(v == 0 for v in stats.values())
    assert db_api.max_score_started(FIRST_COURSE_NAME) == FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == "group_" + task.name[len("task_")]

        assert task.enabled != (task.name in disabled_tasks)


def test_store_score(db_api_with_initialized_first_course, session):
    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0

    db_api_with_initialized_first_course.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )

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

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api_with_initialized_first_course.get_all_scores_with_names(FIRST_COURSE_NAME)
    bonus_score = db_api_with_initialized_first_course.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME)
    scores = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, TEST_USERNAME)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats["task_0_0"] == 1.0
    assert all(v == 0.0 for k, v in stats.items() if k != "task_0_0")

    assert all_scores == {TEST_USERNAME: ({"task_0_0": 1}, (TEST_FIRST_NAME, TEST_LAST_NAME))}
    assert bonus_score == 0
    assert scores == {"task_0_0": 1}


def test_store_score_bonus_task(db_api_with_initialized_first_course, session):
    expected_score = 22

    db_api_with_initialized_first_course.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )

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

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api_with_initialized_first_course.get_all_scores_with_names(FIRST_COURSE_NAME)
    bonus_score = db_api_with_initialized_first_course.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME)
    scores = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, TEST_USERNAME)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats["task_1_3"] == 1.0
    assert all(v == 0.0 for k, v in stats.items() if k != "task_1_3")

    assert all_scores == {TEST_USERNAME: ({"task_1_3": expected_score}, (TEST_FIRST_NAME, TEST_LAST_NAME))}
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

    db_api.create_user_if_not_exist(TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID)

    db_api.store_score(FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(10))

    update_course(
        db_api,
        FIRST_COURSE_NAME,
        first_course_updated_ui_config,
        first_course_deadlines_config_with_changed_task_name,
    )

    stats = db_api.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api.get_all_scores_with_names(FIRST_COURSE_NAME)
    bonus_score = db_api.get_bonus_score(FIRST_COURSE_NAME, TEST_USERNAME)
    scores = db_api.get_scores(FIRST_COURSE_NAME, TEST_USERNAME)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS - {"task_0_0"} | {"task_0_0_changed"}
    assert all(v == 0.0 for k, v in stats.items())

    assert all_scores == {TEST_USERNAME: ({}, (TEST_FIRST_NAME, TEST_LAST_NAME))}
    assert bonus_score == 0
    assert scores == {}


def test_sync_user_on_course(db_api_with_initialized_first_course, session):
    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0

    db_api_with_initialized_first_course.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )

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


def test_many_users(db_api_with_initialized_first_course, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 3
    expected_user_on_course = 2
    expected_grades = 3
    expected_stats_ratio = 0.5

    db_api_with_initialized_first_course.create_user_if_not_exist(
        TEST_USERNAME_1, TEST_FIRST_NAME_1, TEST_LAST_NAME_1, TEST_RMS_ID_1
    )

    db_api_with_initialized_first_course.store_score(FIRST_COURSE_NAME, TEST_USERNAME_1, "task_0_0", update_func(1))
    db_api_with_initialized_first_course.store_score(
        FIRST_COURSE_NAME, TEST_USERNAME_1, "task_1_3", update_func(expected_score_1)
    )

    db_api_with_initialized_first_course.create_user_if_not_exist(
        TEST_USERNAME_2, TEST_FIRST_NAME_2, TEST_LAST_NAME_2, TEST_RMS_ID_2
    )

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

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats["task_0_0"] == 1.0
    assert stats["task_1_3"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats.items() if k not in ["task_0_0", "task_1_3"])

    assert all_scores == {
        TEST_USERNAME_1: (
            {"task_0_0": 1, "task_1_3": expected_score_1},
            (TEST_FIRST_NAME_1, TEST_LAST_NAME_1),
        ),
        TEST_USERNAME_2: (
            {"task_0_0": expected_score_2},
            (TEST_FIRST_NAME_2, TEST_LAST_NAME_2),
        ),
    }
    assert bonus_score_user1 == expected_score_1
    assert scores_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score_user2 == 0
    assert scores_user2 == {"task_0_0": expected_score_2}


def test_many_courses(db_api_with_two_initialized_courses, session):
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )

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

    assert set(stats1.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats1["task_0_0"] == 1.0
    assert all(v == 0.0 for k, v in stats1.items() if k != "task_0_0")

    assert all_scores1 == {TEST_USERNAME: ({"task_0_0": 30}, (TEST_FIRST_NAME, TEST_LAST_NAME))}
    assert bonus_score_user1 == 0
    assert scores_user1 == {"task_0_0": 30}

    stats2 = db_api_with_two_initialized_courses.get_stats(SECOND_COURSE_NAME)
    all_scores2 = db_api_with_two_initialized_courses.get_all_scores_with_names(SECOND_COURSE_NAME)
    bonus_score_user2 = db_api_with_two_initialized_courses.get_bonus_score(SECOND_COURSE_NAME, TEST_USERNAME)
    scores_user2 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, TEST_USERNAME)

    assert set(stats2.keys()) == SECOND_COURSE_EXPECTED_STATS_KEYS
    assert stats2["task_1_3"] == 1.0
    assert all(v == 0.0 for k, v in stats2.items() if k != "task_1_3")

    user2_score = 40
    assert all_scores2 == {TEST_USERNAME: ({"task_1_3": user2_score}, (TEST_FIRST_NAME, TEST_LAST_NAME))}
    assert bonus_score_user2 == user2_score
    assert scores_user2 == {"task_1_3": user2_score}


def test_many_users_and_courses(db_api_with_two_initialized_courses, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 3
    expected_user_on_course = 4
    expected_grades = 5
    expected_stats_ratio = 0.5

    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME_1, TEST_FIRST_NAME_1, TEST_LAST_NAME_1, TEST_RMS_ID_1
    )
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME_2, TEST_FIRST_NAME_2, TEST_LAST_NAME_2, TEST_RMS_ID_2
    )

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

    assert set(stats1.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats1["task_0_0"] == 1.0
    assert stats1["task_1_3"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats1.items() if k not in ["task_0_0", "task_1_3"])

    assert all_scores1 == {
        TEST_USERNAME_1: (
            {"task_0_0": 1, "task_1_3": expected_score_1},
            (TEST_FIRST_NAME_1, TEST_LAST_NAME_1),
        ),
        TEST_USERNAME_2: (
            {"task_0_0": expected_score_2},
            (TEST_FIRST_NAME_2, TEST_LAST_NAME_2),
        ),
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

    assert set(stats2.keys()) == SECOND_COURSE_EXPECTED_STATS_KEYS
    assert stats2["task_1_0"] == expected_stats_ratio
    assert stats2["task_1_1"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats2.items() if k not in ["task_1_0", "task_1_1"])

    assert all_scores2 == {
        TEST_USERNAME_1: ({"task_1_0": 99}, (TEST_FIRST_NAME_1, TEST_LAST_NAME_1)),
        TEST_USERNAME_2: ({"task_1_1": 7}, (TEST_FIRST_NAME_2, TEST_LAST_NAME_2)),
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
    bonus_score = db_api_with_two_initialized_courses.get_bonus_score(FIRST_COURSE_NAME, "random_user")
    scores = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, "random_user")

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
    user = User(
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )

    session.add(user)
    session.commit()

    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )

    score = db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME, TEST_USERNAME, "task_0_0", update_func(1)
    )
    assert score == 1

    assert session.query(User).count() == USER_EXPECTED
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1


def test_store_score_update_error(db_api_with_two_initialized_courses, session):
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )

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
        db_api_with_initialized_first_course.get_stored_user(TEST_USERNAME)


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
    user = User(
        id=2,
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )
    user_on_course = UserOnCourse(user_id=user.id, course_id=1, is_course_admin=False)

    session.add(user)
    session.add(user_on_course)
    session.commit()

    db_api_with_two_initialized_courses.sync_and_get_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, True)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_sync_and_get_admin_status_admin_no_update(db_api_with_two_initialized_courses, session):
    user = User(
        id=2,
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )
    user_on_course = UserOnCourse(user_id=user.id, course_id=1, is_course_admin=True)

    session.add(user)
    session.add(user_on_course)
    session.commit()

    db_api_with_two_initialized_courses.sync_and_get_admin_status(FIRST_COURSE_NAME, TEST_USERNAME, False)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_check_user_on_course(db_api_with_two_initialized_courses, session):
    user = User(
        id=2,
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )
    user_on_course = UserOnCourse(user_id=user.id, course_id=1, is_course_admin=True)

    session.add(user)
    session.add(user_on_course)
    session.commit()

    assert db_api_with_two_initialized_courses.check_user_on_course(FIRST_COURSE_NAME, TEST_USERNAME)


def test_create_user_if_not_exist_existing(db_api_with_two_initialized_courses, session):
    user = User(
        id=2,
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )
    session.add(user)
    session.commit()

    assert session.query(User).filter_by(username=TEST_USERNAME).one().id == user.id
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )
    assert session.query(User).filter_by(username=TEST_USERNAME).one().id == user.id


def test_create_user_if_not_exist_nonexisting(db_api_with_two_initialized_courses, session):
    assert session.query(User).filter_by(username=TEST_USERNAME).one_or_none() is None
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        TEST_USERNAME, TEST_FIRST_NAME, TEST_LAST_NAME, TEST_RMS_ID
    )
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

            found_group, found_task = db_api.find_task(course_name, task.name)

            assert found_group == group
            assert found_task == task


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

    assert course.name == FIRST_COURSE_NAME
    assert course.registration_secret == edited_first_course_config.registration_secret
    assert course.token == "test_token"
    assert not course.show_allscores
    assert course.status == CourseStatus.IN_PROGRESS

    assert course.gitlab_course_group == edited_first_course_config.gitlab_course_group
    assert course.gitlab_course_public_repo == edited_first_course_config.gitlab_course_public_repo
    assert course.gitlab_course_students_group == edited_first_course_config.gitlab_course_students_group
    assert course.gitlab_default_branch == edited_first_course_config.gitlab_default_branch

    assert course.task_url_template == "https://gitlab.test.com/test/$GROUP_NAME/$TASK_NAME"
    assert course.links == {"TG Channel": "https://t.me/joinchat/", "TG Chat": "https://t.me/joinchat/"}

    assert course.timezone == "Europe/Berlin"
    assert course.max_submissions == 10  # noqa: PLR2004
    assert course.submission_penalty == 0.1  # noqa: PLR2004

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert all(v == 0 for v in stats.values())
    assert (
        db_api_with_initialized_first_course.max_score_started(FIRST_COURSE_NAME)
        == FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED
    )


def test_zero_instance_admin_is_in_db_and_set_admin_status(db_api, session):
    assert session.query(User).count() == 1
    assert session.query(User).one().is_instance_admin

    db_api.set_instance_admin_status(session.query(User).one().username, False)
    assert session.query(User).one().is_instance_admin  # should not be possible to remove last admin

    db_api.create_user_if_not_exist(
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )

    assert not session.query(User).filter_by(username=TEST_USERNAME).one().is_instance_admin
    db_api.set_instance_admin_status(TEST_USERNAME, True)
    assert session.query(User).filter_by(username=TEST_USERNAME).one().is_instance_admin
    db_api.set_instance_admin_status(session.query(User).filter_by(id=1).one().username, False)
    assert not session.query(User).filter_by(id=1).one().is_instance_admin


def test_update_user_profile(db_api, session):
    db_api.create_user_if_not_exist(
        username=TEST_USERNAME,
        first_name=TEST_FIRST_NAME,
        last_name=TEST_LAST_NAME,
        rms_id=TEST_RMS_ID,
    )

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

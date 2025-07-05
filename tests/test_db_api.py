import os
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
import yaml
from alembic import command
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from psycopg2.errors import DuplicateColumn, DuplicateTable, UndefinedTable, UniqueViolation
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from manytask.config import ManytaskConfig, ManytaskDeadlinesConfig, ManytaskGroupConfig, ManytaskUiConfig
from manytask.course import Course as ManytaskCourse
from manytask.course import CourseConfig
from manytask.database import DataBaseApi, DatabaseConfig, StoredUser, TaskDisabledError
from manytask.models import Course, Deadline, Grade, Task, TaskGroup, User, UserOnCourse
from tests import constants

DEADLINES_CONFIG_FILES = [  # part of manytask config file
    "tests/.deadlines.test.yml",
    "tests/.deadlines.test2.yml",
]

FIXED_CURRENT_TIME = datetime(2025, 4, 1, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
FIRST_COURSE_NAME = "Test Course"
SECOND_COURSE_NAME = "Another Test Course"

FIRST_COURSE_EXPECTED_STATS_KEYS = {
    "task_0_0",
    "task_0_1",
    "task_0_2",
    "task_0_3",
    "task_1_0",
    "task_1_1",
    "task_1_2",
    "task_1_3",
    "task_1_4",
    "task_2_2",
    "task_2_3",
    "task_3_0",
    "task_3_1",
    "task_3_2",
    "task_5_0",
}
SECOND_COURSE_EXPECTED_STATS_KEYS = {
    "task_0_0",
    "task_0_1",
    "task_0_2",
    "task_0_3",
    "task_0_4",
    "task_0_5",
    "task_1_0",
    "task_1_1",
    "task_1_2",
    "task_1_3",
    "task_1_4",
    "task_2_0",
    "task_2_1",
    "task_2_3",
    "task_3_0",
    "task_3_1",
    "task_3_2",
    "task_3_3",
    "task_4_0",
    "task_4_1",
    "task_4_2",
    "task_5_0",
    "task_5_1",
    "task_5_2",
}

FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED = 250
SECOND_COURSE_EXPECTED_MAX_SCORE_STARTED = 540


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
        gitlab_instance_host="gitlab.test.com",
        apply_migrations=True,
    )


@pytest.fixture
def db_api(tables, postgres_container):
    return DataBaseApi(db_config(postgres_container.get_connection_url()))


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
        is_ready=False,
        task_url_template="https://gitlab.test.com/test/$GROUP_NAME/$TASK_NAME",
        links={"TG Channel": "https://t.me/joinchat/", "TG Chat": "https://t.me/joinchat/"},
    )


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
        is_ready=False,
        task_url_template="https://gitlab.test.com/another_test/$GROUP_NAME/$TASK_NAME",
        links={"TG Chat": "https://t.me/joinchat2/"},
    )


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
    db_api: DataBaseApi, course_name: str, ui_config: ManytaskUiConfig, deadlines_config: ManytaskDeadlinesConfig
) -> None:
    """Update created course"""
    config = ManytaskConfig(version=1, ui=ui_config, deadlines=deadlines_config)

    db_api.update_course(course_name=course_name, config=config)


def create_course(db_api: DataBaseApi, course_config: CourseConfig, deadlines_config: ManytaskDeadlinesConfig) -> None:
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
    )


@pytest.fixture
def db_api_with_initialized_first_course(db_api, first_course_config, first_course_deadlines_config):
    create_course(db_api, first_course_config, first_course_deadlines_config)
    return db_api


@pytest.fixture
def db_api_with_two_initialized_courses(
    db_api, first_course_config, first_course_deadlines_config, second_course_config, second_course_deadlines_config
):
    create_course(db_api, first_course_config, first_course_deadlines_config)
    create_course(db_api, second_course_config, second_course_deadlines_config)
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
    assert course.gitlab_instance_host == "gitlab.test.com"
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert not course.is_ready

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
    all_scores = db_api.get_all_scores(course_name)
    bonus_score = db_api.get_bonus_score(course_name, "some_user")
    scores = db_api.get_scores(course_name, "some_user")
    max_score_started = db_api.max_score_started(course_name)

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}
    assert max_score_started == 0


def test_initialized_course(db_api_with_initialized_first_course, session):
    expected_task_groups = 6
    expected_tasks = 19
    bonus_tasks = ("task_0_2", "task_1_3")
    large_tasks = "task_5_0"
    special_tasks = ("task_1_1",)
    disabled_groups = ("group_4",)
    disabled_tasks = ("task_2_1",)

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == FIRST_COURSE_NAME
    assert course.gitlab_instance_host == "gitlab.test.com"
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.is_ready

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


def test_updating_course(
    db_api,
    first_course_config,
    first_course_deadlines_config,
    second_course_deadlines_config,
    first_course_updated_ui_config,
    session,
):
    expected_task_groups = 8
    expected_tasks = 28
    bonus_tasks = ("task_0_2", "task_1_3", "task_6_0")
    large_tasks = ("task_5_0", "task_5_1")
    special_tasks = ("task_1_1", "task_6_0")
    disabled_groups = ("group_6",)
    disabled_tasks = ("task_2_2",)

    create_course(db_api, first_course_config, first_course_deadlines_config)
    update_course(db_api, FIRST_COURSE_NAME, first_course_updated_ui_config, second_course_deadlines_config)

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == FIRST_COURSE_NAME
    assert course.gitlab_instance_host == "gitlab.test.com"
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.is_ready

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
    session,
):
    expected_task_groups = 6
    expected_tasks = 20
    disabled_tasks = ("task_0_0", "task_2_1")

    create_course(db_api, first_course_config, first_course_deadlines_config)
    update_course(
        db_api, FIRST_COURSE_NAME, first_course_updated_ui_config, first_course_deadlines_config_with_changed_task_name
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
    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    db_api_with_initialized_first_course.create_user_if_not_exist(
        constants.TEST_USERNAME, constants.TEST_FIRST_NAME, constants.TEST_LAST_NAME, FIRST_COURSE_NAME
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 0

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME,
            constants.TEST_USERNAME,
            constants.TEST_REPO_NAME,
            "not_exist_task",
            update_func(1),
        )
        == 0
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1

    user = session.query(User).one()
    assert user.username == constants.TEST_USERNAME
    assert user.gitlab_instance_host == "gitlab.test.com"

    user_on_course = session.query(UserOnCourse).one()
    assert user_on_course.user_id == user.id
    assert user_on_course.course.name == FIRST_COURSE_NAME

    assert session.query(Grade).count() == 0

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME,
            constants.TEST_USERNAME,
            constants.TEST_REPO_NAME,
            "task_0_0",
            update_func(1),
        )
        == 1
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).one()
    assert grade.user_on_course_id == user_on_course.id
    assert grade.task.name == "task_0_0"
    assert grade.score == 1

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api_with_initialized_first_course.get_all_scores(FIRST_COURSE_NAME)
    bonus_score = db_api_with_initialized_first_course.get_bonus_score(FIRST_COURSE_NAME, constants.TEST_USERNAME)
    scores = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats["task_0_0"] == 1.0
    assert all(v == 0.0 for k, v in stats.items() if k != "task_0_0")

    assert all_scores == {constants.TEST_USERNAME: {"task_0_0": 1}}
    assert bonus_score == 0
    assert scores == {"task_0_0": 1}


def test_store_score_bonus_task(db_api_with_initialized_first_course, session):
    expected_score = 22

    db_api_with_initialized_first_course.create_user_if_not_exist(
        constants.TEST_USERNAME, constants.TEST_FIRST_NAME, constants.TEST_LAST_NAME, FIRST_COURSE_NAME
    )

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME,
            constants.TEST_USERNAME,
            constants.TEST_REPO_NAME,
            "task_1_3",
            update_func(expected_score),
        )
        == expected_score
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).join(Task).filter(Task.name == "task_1_3").one()
    assert grade.task.name == "task_1_3"
    assert grade.score == expected_score

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api_with_initialized_first_course.get_all_scores(FIRST_COURSE_NAME)
    bonus_score = db_api_with_initialized_first_course.get_bonus_score(FIRST_COURSE_NAME, constants.TEST_USERNAME)
    scores = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats["task_1_3"] == 1.0
    assert all(v == 0.0 for k, v in stats.items() if k != "task_1_3")

    assert all_scores == {constants.TEST_USERNAME: {"task_1_3": expected_score}}
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

    db_api.create_user_if_not_exist(
        constants.TEST_USERNAME, constants.TEST_FIRST_NAME, constants.TEST_LAST_NAME, FIRST_COURSE_NAME
    )

    db_api.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME,
        constants.TEST_REPO_NAME,
        "task_0_0",
        update_func(10),
    )

    update_course(
        db_api, FIRST_COURSE_NAME, first_course_updated_ui_config, first_course_deadlines_config_with_changed_task_name
    )

    stats = db_api.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api.get_all_scores(FIRST_COURSE_NAME)
    bonus_score = db_api.get_bonus_score(FIRST_COURSE_NAME, constants.TEST_USERNAME)
    scores = db_api.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS - {"task_0_0"} | {"task_0_0_changed"}
    assert all(v == 0.0 for k, v in stats.items())

    assert all_scores == {constants.TEST_USERNAME: {}}
    assert bonus_score == 0
    assert scores == {}


def test_get_and_sync_stored_user(db_api_with_initialized_first_course, session):
    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    stored_user = db_api_with_initialized_first_course.get_stored_user(FIRST_COURSE_NAME, constants.TEST_USERNAME)

    assert stored_user == StoredUser(
        username=constants.TEST_USERNAME,
        course_admin=False,
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1

    # admin in gitlab
    stored_user = db_api_with_initialized_first_course.sync_stored_user(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME,
        constants.TEST_REPO_NAME,
        True,
    )

    assert stored_user == StoredUser(
        username=constants.TEST_USERNAME,
        course_admin=True,
    )

    # lost admin rules in gitlab, but in database stored that user is admin
    stored_user = db_api_with_initialized_first_course.sync_stored_user(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME,
        constants.TEST_REPO_NAME,
        False,
    )

    assert stored_user == StoredUser(
        username=constants.TEST_USERNAME,
        course_admin=True,
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1


def test_many_users(db_api_with_initialized_first_course, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 2
    expected_user_on_course = 2
    expected_grades = 3
    expected_stats_ratio = 0.5

    db_api_with_initialized_first_course.create_user_if_not_exist(
        constants.TEST_USERNAME_1, constants.TEST_FIRST_NAME_1, constants.TEST_LAST_NAME_1, FIRST_COURSE_NAME
    )

    db_api_with_initialized_first_course.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME_1,
        constants.TEST_REPO_NAME_1,
        "task_0_0",
        update_func(1),
    )
    db_api_with_initialized_first_course.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME_1,
        constants.TEST_REPO_NAME_1,
        "task_1_3",
        update_func(expected_score_1),
    )

    assert (
        db_api_with_initialized_first_course.store_score(
            FIRST_COURSE_NAME,
            constants.TEST_USERNAME_2,
            constants.TEST_REPO_NAME_2,
            "task_0_0",
            update_func(expected_score_2),
        )
        == expected_score_2
    )

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats = db_api_with_initialized_first_course.get_stats(FIRST_COURSE_NAME)
    all_scores = db_api_with_initialized_first_course.get_all_scores(FIRST_COURSE_NAME)
    bonus_score_user1 = db_api_with_initialized_first_course.get_bonus_score(
        FIRST_COURSE_NAME, constants.TEST_USERNAME_1
    )
    scores_user1 = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME_1)
    bonus_score_user2 = db_api_with_initialized_first_course.get_bonus_score(
        FIRST_COURSE_NAME, constants.TEST_USERNAME_2
    )
    scores_user2 = db_api_with_initialized_first_course.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME_2)

    assert set(stats.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats["task_0_0"] == 1.0
    assert stats["task_1_3"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats.items() if k not in ["task_0_0", "task_1_3"])

    assert all_scores == {
        constants.TEST_USERNAME_1: {"task_0_0": 1, "task_1_3": expected_score_1},
        constants.TEST_USERNAME_2: {"task_0_0": expected_score_2},
    }
    assert bonus_score_user1 == expected_score_1
    assert scores_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score_user2 == 0
    assert scores_user2 == {"task_0_0": expected_score_2}


def test_many_courses(db_api_with_two_initialized_courses, session):
    db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME,
        constants.TEST_REPO_NAME,
        "task_0_0",
        update_func(30),
    )
    db_api_with_two_initialized_courses.store_score(
        SECOND_COURSE_NAME,
        constants.TEST_USERNAME,
        constants.TEST_REPO_NAME,
        "task_1_3",
        update_func(40),
    )
    expected_users = 1
    expected_user_on_course = 2
    expected_grades = 2

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats1 = db_api_with_two_initialized_courses.get_stats(FIRST_COURSE_NAME)
    all_scores1 = db_api_with_two_initialized_courses.get_all_scores(FIRST_COURSE_NAME)
    bonus_score_user1 = db_api_with_two_initialized_courses.get_bonus_score(FIRST_COURSE_NAME, constants.TEST_USERNAME)
    scores_user1 = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME)

    assert set(stats1.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats1["task_0_0"] == 1.0
    assert all(v == 0.0 for k, v in stats1.items() if k != "task_0_0")

    assert all_scores1 == {constants.TEST_USERNAME: {"task_0_0": 30}}
    assert bonus_score_user1 == 0
    assert scores_user1 == {"task_0_0": 30}

    stats2 = db_api_with_two_initialized_courses.get_stats(SECOND_COURSE_NAME)
    all_scores2 = db_api_with_two_initialized_courses.get_all_scores(SECOND_COURSE_NAME)
    bonus_score_user2 = db_api_with_two_initialized_courses.get_bonus_score(SECOND_COURSE_NAME, constants.TEST_USERNAME)
    scores_user2 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, constants.TEST_USERNAME)

    assert set(stats2.keys()) == SECOND_COURSE_EXPECTED_STATS_KEYS
    assert stats2["task_1_3"] == 1.0
    assert all(v == 0.0 for k, v in stats2.items() if k != "task_1_3")

    user2_score = 40
    assert all_scores2 == {constants.TEST_USERNAME: {"task_1_3": user2_score}}
    assert bonus_score_user2 == user2_score
    assert scores_user2 == {"task_1_3": user2_score}


def test_many_users_and_courses(db_api_with_two_initialized_courses, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 2
    expected_user_on_course = 4
    expected_grades = 5
    expected_stats_ratio = 0.5

    db_api_with_two_initialized_courses.create_user_if_not_exist(
        constants.TEST_USERNAME_1, constants.TEST_FIRST_NAME_1, constants.TEST_LAST_NAME_1, FIRST_COURSE_NAME
    )
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        constants.TEST_USERNAME_2, constants.TEST_FIRST_NAME_2, constants.TEST_LAST_NAME_2, FIRST_COURSE_NAME
    )

    db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME_1,
        constants.TEST_REPO_NAME_1,
        "task_0_0",
        update_func(1),
    )
    db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME_1,
        constants.TEST_REPO_NAME_1,
        "task_1_3",
        update_func(expected_score_1),
    )
    db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME_2,
        constants.TEST_REPO_NAME_2,
        "task_0_0",
        update_func(expected_score_2),
    )

    db_api_with_two_initialized_courses.store_score(
        SECOND_COURSE_NAME,
        constants.TEST_USERNAME_1,
        constants.TEST_REPO_NAME_1,
        "task_1_0",
        update_func(99),
    )
    db_api_with_two_initialized_courses.store_score(
        SECOND_COURSE_NAME,
        constants.TEST_USERNAME_2,
        constants.TEST_REPO_NAME_2,
        "task_1_1",
        update_func(7),
    )

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats1 = db_api_with_two_initialized_courses.get_stats(FIRST_COURSE_NAME)
    all_scores1 = db_api_with_two_initialized_courses.get_all_scores(FIRST_COURSE_NAME)
    bonus_score1_user1 = db_api_with_two_initialized_courses.get_bonus_score(
        FIRST_COURSE_NAME, constants.TEST_USERNAME_1
    )
    scores1_user1 = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME_1)
    bonus_score1_user2 = db_api_with_two_initialized_courses.get_bonus_score(
        FIRST_COURSE_NAME, constants.TEST_USERNAME_2
    )
    scores1_user2 = db_api_with_two_initialized_courses.get_scores(FIRST_COURSE_NAME, constants.TEST_USERNAME_2)

    assert set(stats1.keys()) == FIRST_COURSE_EXPECTED_STATS_KEYS
    assert stats1["task_0_0"] == 1.0
    assert stats1["task_1_3"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats1.items() if k not in ["task_0_0", "task_1_3"])

    assert all_scores1 == {
        constants.TEST_USERNAME_1: {"task_0_0": 1, "task_1_3": expected_score_1},
        constants.TEST_USERNAME_2: {"task_0_0": expected_score_2},
    }
    assert bonus_score1_user1 == expected_score_1
    assert scores1_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score1_user2 == 0
    assert scores1_user2 == {"task_0_0": expected_score_2}

    stats2 = db_api_with_two_initialized_courses.get_stats(SECOND_COURSE_NAME)
    all_scores2 = db_api_with_two_initialized_courses.get_all_scores(SECOND_COURSE_NAME)
    bonus_score2_user1 = db_api_with_two_initialized_courses.get_bonus_score(
        SECOND_COURSE_NAME, constants.TEST_USERNAME_1
    )
    scores2_user1 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, constants.TEST_USERNAME_1)
    bonus_score2_user2 = db_api_with_two_initialized_courses.get_bonus_score(
        SECOND_COURSE_NAME, constants.TEST_USERNAME_2
    )
    scores2_user2 = db_api_with_two_initialized_courses.get_scores(SECOND_COURSE_NAME, constants.TEST_USERNAME_2)

    assert set(stats2.keys()) == SECOND_COURSE_EXPECTED_STATS_KEYS
    assert stats2["task_1_0"] == expected_stats_ratio
    assert stats2["task_1_1"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats2.items() if k not in ["task_1_0", "task_1_1"])

    assert all_scores2 == {constants.TEST_USERNAME_1: {"task_1_0": 99}, "user2": {"task_1_1": 7}}
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

    assert session.query(User).count() == 0
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
                gitlab_instance_host="gitlab.test.com",
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
        username=constants.TEST_USERNAME,
        gitlab_instance_host="gitlab.test.com",
    )
    session.add(user)
    session.commit()

    score = db_api_with_two_initialized_courses.store_score(
        FIRST_COURSE_NAME,
        constants.TEST_USERNAME,
        constants.TEST_REPO_NAME,
        "task_0_0",
        update_func(1),
    )
    assert score == 1

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1


def test_store_score_update_error(db_api_with_two_initialized_courses, session):
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        constants.TEST_USERNAME, constants.TEST_FIRST_NAME, constants.TEST_LAST_NAME, FIRST_COURSE_NAME
    )

    def failing_update(_, score):
        raise ValueError("Update failed")

    with pytest.raises(ValueError) as exc_info:
        db_api_with_two_initialized_courses.store_score(
            FIRST_COURSE_NAME,
            constants.TEST_USERNAME,
            constants.TEST_REPO_NAME,
            "task_0_0",
            failing_update,
        )
    assert "Update failed" in str(exc_info.value)

    assert session.query(Grade).count() == 0


def test_get_course_success(db_api_with_two_initialized_courses, first_course_config, second_course_config):
    first_course_config.is_ready = True
    course = db_api_with_two_initialized_courses.get_course(FIRST_COURSE_NAME)
    assert course.__dict__ == ManytaskCourse(first_course_config).__dict__

    second_course_config.is_ready = True
    course = db_api_with_two_initialized_courses.get_course(SECOND_COURSE_NAME)
    assert course.__dict__ == ManytaskCourse(second_course_config).__dict__


def test_get_course_unknown(db_api_with_two_initialized_courses):
    course = db_api_with_two_initialized_courses.get_course("Unknown course")
    assert course is None


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
        id=1,
        username=constants.TEST_USERNAME,
        first_name=constants.TEST_FIRST_NAME,
        last_name=constants.TEST_LAST_NAME,
        gitlab_instance_host="gitlab.test.com",
    )
    user_on_course = UserOnCourse(
        user_id=user.id, course_id=1, repo_name=constants.TEST_REPO_NAME, is_course_admin=False
    )

    session.add(user)
    session.add(user_on_course)
    session.commit()

    db_api_with_two_initialized_courses.sync_and_get_admin_status(FIRST_COURSE_NAME, constants.TEST_USERNAME, True)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_sync_and_get_admin_status_admin_no_update(db_api_with_two_initialized_courses, session):
    user = User(
        id=1,
        username=constants.TEST_USERNAME,
        first_name=constants.TEST_FIRST_NAME,
        last_name=constants.TEST_LAST_NAME,
        gitlab_instance_host="gitlab.test.com",
    )
    user_on_course = UserOnCourse(
        user_id=user.id, course_id=1, repo_name=constants.TEST_REPO_NAME, is_course_admin=True
    )

    session.add(user)
    session.add(user_on_course)
    session.commit()

    db_api_with_two_initialized_courses.sync_and_get_admin_status(FIRST_COURSE_NAME, constants.TEST_USERNAME, False)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_check_user_on_course(db_api_with_two_initialized_courses, session):
    user = User(
        id=1,
        username=constants.TEST_USERNAME,
        first_name=constants.TEST_FIRST_NAME,
        last_name=constants.TEST_LAST_NAME,
        gitlab_instance_host="gitlab.test.com",
    )
    user_on_course = UserOnCourse(
        user_id=user.id, course_id=1, repo_name=constants.TEST_REPO_NAME, is_course_admin=True
    )

    session.add(user)
    session.add(user_on_course)
    session.commit()

    assert db_api_with_two_initialized_courses.check_user_on_course(FIRST_COURSE_NAME, constants.TEST_USERNAME)


def test_create_user_if_not_exist_existing(db_api_with_two_initialized_courses, session):
    user = User(
        id=1,
        username=constants.TEST_USERNAME,
        first_name=constants.TEST_FIRST_NAME,
        last_name=constants.TEST_LAST_NAME,
        gitlab_instance_host="gitlab.test.com",
    )
    session.add(user)
    session.commit()

    assert session.query(User).filter_by(username=constants.TEST_USERNAME).one().id == user.id
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        constants.TEST_USERNAME, constants.TEST_FIRST_NAME, constants.TEST_LAST_NAME, FIRST_COURSE_NAME
    )
    assert session.query(User).filter_by(username=constants.TEST_USERNAME).one().id == user.id


def test_create_user_if_not_exist_nonexisting(db_api_with_two_initialized_courses, session):
    assert session.query(User).filter_by(username=constants.TEST_USERNAME).one_or_none() is None
    db_api_with_two_initialized_courses.create_user_if_not_exist(
        constants.TEST_USERNAME, constants.TEST_FIRST_NAME, constants.TEST_LAST_NAME, FIRST_COURSE_NAME
    )
    assert session.query(User).filter_by(username=constants.TEST_USERNAME).one()


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
        db_api_with_two_initialized_courses, FIRST_COURSE_NAME, first_course_updated_ui_config, course_deadlines_config
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
        db_api_with_two_initialized_courses, FIRST_COURSE_NAME, first_course_updated_ui_config, course_deadlines_config
    )

    check_get_groups(
        db_api_with_two_initialized_courses, FIRST_COURSE_NAME, course_deadlines_config, enabled, started, now
    )

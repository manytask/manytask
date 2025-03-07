import os
from datetime import datetime, timedelta
from typing import Any
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

from manytask.config import ManytaskDeadlinesConfig
from manytask.database import DataBaseApi, DatabaseConfig, StoredUser
from manytask.glab import Student
from manytask.models import Course, Deadline, Grade, Task, TaskGroup, User, UserOnCourse

DEADLINES_CONFIG_FILES = [  # part of manytask config file
    "tests/.deadlines.test.yml",
    "tests/.deadlines.test2.yml",
]

FIXED_CURRENT_TIME = datetime(2025, 4, 1, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))


class TestException(Exception):
    pass


@pytest.fixture(autouse=True)
def mock_current_time():
    with patch("manytask.config.ManytaskDeadlinesConfig.get_now_with_timezone") as mock:
        mock.return_value = FIXED_CURRENT_TIME
        yield mock


@pytest.fixture
def first_course_db_api(tables, postgres_container):
    return DataBaseApi(
        DatabaseConfig(
            database_url=postgres_container.get_connection_url(),
            course_name="Test Course",
            gitlab_instance_host="gitlab.test.com",
            registration_secret="secret",
            token="test_token",
            show_allscores=True,
            apply_migrations=True,
        )
    )


@pytest.fixture
def second_course_db_api(tables, postgres_container):
    return DataBaseApi(
        DatabaseConfig(
            database_url=postgres_container.get_connection_url(),
            course_name="Another Test Course",
            gitlab_instance_host="gitlab.test.com",
            token="another_test_token",
            registration_secret="secret",
            show_allscores=True,
            apply_migrations=True,
        )
    )


def load_deadlines_config_and_sync_columns(db_api: DataBaseApi, yaml_file_file_path: str):
    with open(yaml_file_file_path, "r") as f:
        deadlines_config_data: dict[str, Any] = yaml.load(f, Loader=yaml.SafeLoader)
    deadlines_config = ManytaskDeadlinesConfig(**deadlines_config_data["deadlines"])

    with Session(db_api.engine) as session:
        try:
            db_api._get(session, Course, name=db_api.course_name)
        except NoResultFound:
            db_api._create(
                session,
                Course,
                name=db_api.course_name,
                gitlab_instance_host="gitlab.test.com",
                registration_secret="secret",
                token="token",
                show_allscores=True,
            )
            session.commit()

    # Invariant: course exists
    db_api.sync_columns(deadlines_config)


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
def first_course_with_deadlines(first_course_db_api, first_course_deadlines_config, session):
    first_course_db_api.sync_columns(first_course_deadlines_config)
    return first_course_db_api


@pytest.fixture
def second_course_with_deadlines(second_course_db_api, second_course_deadlines_config, session):
    second_course_db_api.sync_columns(second_course_deadlines_config)
    return second_course_db_api


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


def test_empty_course(first_course_db_api, session):
    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == "Test Course"
    assert course.gitlab_instance_host == "gitlab.test.com"
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.timezone == "UTC"
    assert course.max_submissions is None
    assert course.submission_penalty == 0

    stats = first_course_db_api.get_stats()
    all_scores = first_course_db_api.get_all_scores()
    bonus_score = first_course_db_api.get_bonus_score("some_user")
    scores = first_course_db_api.get_scores("some_user")

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}


def test_sync_columns(first_course_with_deadlines, session):
    expected_task_groups = 5
    expected_tasks = 18

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == "Test Course"
    assert course.gitlab_instance_host == "gitlab.test.com"
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.timezone == "Europe/Berlin"
    assert course.max_submissions == 10  # noqa: PLR2004
    assert course.submission_penalty == 0.1  # noqa: PLR2004

    stats = first_course_with_deadlines.get_stats()
    assert set(stats.keys()) == {
        "task_0_0",
        "task_0_1",
        "task_0_2",
        "task_0_3",
        "task_1_0",
        "task_1_1",
        "task_1_2",
        "task_1_3",
        "task_1_4",
        "task_2_1",
        "task_2_2",
        "task_2_3",
        "task_3_0",
        "task_3_1",
        "task_3_2",
        "task_4_0",
        "task_4_1",
        "task_4_2",
    }
    assert all(v == 0 for v in stats.values())

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == "group_" + task.name[len("task_")]
        assert task.group.enabled

        if task.name in ("task_0_2", "task_1_3"):
            assert task.is_bonus
        else:
            assert not task.is_bonus

        if task.name in ("task_1_1"):
            assert task.is_special
        else:
            assert not task.is_special

        # for convenience task score related to its name(exception is group_0, it has multiplier "1")
        # for example for task_1_3 score is 10, task_3_0 score is 30
        score_multiplier = int(task.name.split("_")[1])
        score_multiplier = 1 if score_multiplier == 0 else score_multiplier
        expected_task_score = score_multiplier * 10

        assert task.score == expected_task_score


def test_resync_columns(first_course_db_api, first_course_deadlines_config, second_course_deadlines_config, session):
    expected_task_groups = 6
    expected_tasks = 25

    first_course_db_api.sync_columns(first_course_deadlines_config)
    first_course_db_api.sync_columns(second_course_deadlines_config)

    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == "Test Course"
    assert course.gitlab_instance_host == "gitlab.test.com"
    assert course.registration_secret == "secret"
    assert course.token == "test_token"
    assert course.show_allscores
    assert course.timezone == "Europe/Moscow"
    assert course.max_submissions == 20  # noqa: PLR2004
    assert course.submission_penalty == 0.2  # noqa: PLR2004

    stats = first_course_db_api.get_stats()
    assert set(stats.keys()) == {
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
        "task_2_2",
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
    assert all(v == 0 for v in stats.values())

    assert session.query(TaskGroup).count() == expected_task_groups
    assert session.query(Task).count() == expected_tasks

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == "group_" + task.name[len("task_")]
        assert task.group.enabled  # TODO in #258 issue, must store disabled tasks also

        if task.name in ("task_0_2", "task_1_3", "task_6_0"):
            assert task.is_bonus
        else:
            assert not task.is_bonus

        if task.name in ("task_1_1", "task_6_0"):
            assert task.is_special
        else:
            assert not task.is_special

        # for convenience task score related to its name(exception is group_0, it has multiplier "1")
        # for example for task_1_3 score is 10, task_3_0 score is 30
        score_multiplier = int(task.name.split("_")[1])
        score_multiplier = 1 if score_multiplier == 0 else score_multiplier
        expected_task_score = score_multiplier * 10

        assert task.score == expected_task_score


def test_store_score(first_course_with_deadlines, session):
    student = Student(0, "user1", "username1", False, "repo1")

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    assert first_course_with_deadlines.store_score(student, "not_exist_task", update_func(1)) == 0

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1

    user = session.query(User).one()
    assert user.username == student.username
    assert user.gitlab_instance_host == "gitlab.test.com"

    user_on_course = session.query(UserOnCourse).one()
    assert user_on_course.user_id == user.id
    assert user_on_course.course.name == "Test Course"
    assert user_on_course.repo_name == student.repo

    assert session.query(Grade).count() == 0

    assert first_course_with_deadlines.store_score(student, "task_0_0", update_func(1)) == 1

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).one()
    assert grade.user_on_course_id == user_on_course.id
    assert grade.task.name == "task_0_0"
    assert grade.score == 1

    stats = first_course_with_deadlines.get_stats()
    all_scores = first_course_with_deadlines.get_all_scores()
    bonus_score = first_course_with_deadlines.get_bonus_score("user1")
    scores = first_course_with_deadlines.get_scores("user1")

    assert set(stats.keys()) == {
        "task_0_0",
        "task_0_1",
        "task_0_2",
        "task_0_3",
        "task_1_0",
        "task_1_1",
        "task_1_2",
        "task_1_3",
        "task_1_4",
        "task_2_1",
        "task_2_2",
        "task_2_3",
        "task_3_0",
        "task_3_1",
        "task_3_2",
        "task_4_0",
        "task_4_1",
        "task_4_2",
    }
    assert stats["task_0_0"] == 1.0
    assert all(v == 0.0 for k, v in stats.items() if k != "task_0_0")

    assert all_scores == {"user1": {"task_0_0": 1}}
    assert bonus_score == 0
    assert scores == {"task_0_0": 1}


def test_store_score_bonus_task(first_course_with_deadlines, session):
    expected_score = 22
    student = Student(0, "user1", "username1", False, "repo1")

    assert first_course_with_deadlines.store_score(student, "task_1_3", update_func(expected_score)) == expected_score

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).join(Task).filter(Task.name == "task_1_3").one()
    assert grade.task.name == "task_1_3"
    assert grade.score == expected_score

    stats = first_course_with_deadlines.get_stats()
    all_scores = first_course_with_deadlines.get_all_scores()
    bonus_score = first_course_with_deadlines.get_bonus_score("user1")
    scores = first_course_with_deadlines.get_scores("user1")

    assert set(stats.keys()) == {
        "task_0_0",
        "task_0_1",
        "task_0_2",
        "task_0_3",
        "task_1_0",
        "task_1_1",
        "task_1_2",
        "task_1_3",
        "task_1_4",
        "task_2_1",
        "task_2_2",
        "task_2_3",
        "task_3_0",
        "task_3_1",
        "task_3_2",
        "task_4_0",
        "task_4_1",
        "task_4_2",
    }
    assert stats["task_1_3"] == 1.0
    assert all(v == 0.0 for k, v in stats.items() if k != "task_1_3")

    assert all_scores == {"user1": {"task_1_3": expected_score}}
    assert bonus_score == expected_score
    assert scores == {"task_1_3": expected_score}


def test_get_and_sync_stored_user(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    student = Student(0, "user1", "username1", False, "repo1")  # default student(not admin in gitlab)

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    stored_user = first_course_db_api.get_stored_user(student)

    assert stored_user == StoredUser(username="user1", course_admin=False)

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1

    student.course_admin = True  # admin in gitlab

    stored_user = first_course_db_api.sync_stored_user(student)

    assert stored_user == StoredUser(username="user1", course_admin=True)

    student.course_admin = False  # lost admin rules in gitlab, but in database stored that user is admin

    stored_user = first_course_db_api.sync_stored_user(student)

    assert stored_user == StoredUser(username="user1", course_admin=True)

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1


def test_many_users(first_course_with_deadlines, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 2
    expected_user_on_course = 2
    expected_grades = 3
    expected_stats_ratio = 0.5

    student1 = Student(0, "user1", "username1", False, "repo1")
    first_course_with_deadlines.store_score(student1, "task_0_0", update_func(1))
    first_course_with_deadlines.store_score(student1, "task_1_3", update_func(expected_score_1))

    student2 = Student(1, "user2", "username2", False, "repo2")

    assert (
        first_course_with_deadlines.store_score(student2, "task_0_0", update_func(expected_score_2)) == expected_score_2
    )

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats = first_course_with_deadlines.get_stats()
    all_scores = first_course_with_deadlines.get_all_scores()
    bonus_score_user1 = first_course_with_deadlines.get_bonus_score("user1")
    scores_user1 = first_course_with_deadlines.get_scores("user1")
    bonus_score_user2 = first_course_with_deadlines.get_bonus_score("user2")
    scores_user2 = first_course_with_deadlines.get_scores("user2")

    assert set(stats.keys()) == {
        "task_0_0",
        "task_0_1",
        "task_0_2",
        "task_0_3",
        "task_1_0",
        "task_1_1",
        "task_1_2",
        "task_1_3",
        "task_1_4",
        "task_2_1",
        "task_2_2",
        "task_2_3",
        "task_3_0",
        "task_3_1",
        "task_3_2",
        "task_4_0",
        "task_4_1",
        "task_4_2",
    }
    assert stats["task_0_0"] == 1.0
    assert stats["task_1_3"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats.items() if k not in ["task_0_0", "task_1_3"])

    assert all_scores == {
        "user1": {"task_0_0": 1, "task_1_3": expected_score_1},
        "user2": {"task_0_0": expected_score_2},
    }
    assert bonus_score_user1 == expected_score_1
    assert scores_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score_user2 == 0
    assert scores_user2 == {"task_0_0": expected_score_2}


def test_many_courses(first_course_with_deadlines, second_course_with_deadlines, session):
    student = Student(0, "user1", "username1", False, "repo1")
    first_course_with_deadlines.store_score(student, "task_0_0", update_func(30))
    second_course_with_deadlines.store_score(student, "task_1_3", update_func(40))
    expected_users = 1
    expected_user_on_course = 2
    expected_grades = 2

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats1 = first_course_with_deadlines.get_stats()
    all_scores1 = first_course_with_deadlines.get_all_scores()
    bonus_score_user1 = first_course_with_deadlines.get_bonus_score("user1")
    scores_user1 = first_course_with_deadlines.get_scores("user1")

    assert set(stats1.keys()) == {
        "task_0_0",
        "task_0_1",
        "task_0_2",
        "task_0_3",
        "task_1_0",
        "task_1_1",
        "task_1_2",
        "task_1_3",
        "task_1_4",
        "task_2_1",
        "task_2_2",
        "task_2_3",
        "task_3_0",
        "task_3_1",
        "task_3_2",
        "task_4_0",
        "task_4_1",
        "task_4_2",
    }
    assert stats1["task_0_0"] == 1.0
    assert all(v == 0.0 for k, v in stats1.items() if k != "task_0_0")

    assert all_scores1 == {"user1": {"task_0_0": 30}}
    assert bonus_score_user1 == 0
    assert scores_user1 == {"task_0_0": 30}

    stats2 = second_course_with_deadlines.get_stats()
    all_scores2 = second_course_with_deadlines.get_all_scores()
    bonus_score_user2 = second_course_with_deadlines.get_bonus_score("user1")
    scores_user2 = second_course_with_deadlines.get_scores("user1")

    assert set(stats2.keys()) == {
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
        "task_2_2",
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
    assert stats2["task_1_3"] == 1.0
    assert all(v == 0.0 for k, v in stats2.items() if k != "task_1_3")

    user2_score = 40
    assert all_scores2 == {"user1": {"task_1_3": user2_score}}
    assert bonus_score_user2 == user2_score
    assert scores_user2 == {"task_1_3": user2_score}


def test_many_users_and_courses(first_course_with_deadlines, second_course_with_deadlines, session):
    expected_score_1 = 22
    expected_score_2 = 15
    expected_users = 2
    expected_user_on_course = 4
    expected_grades = 5
    expected_stats_ratio = 0.5

    student1 = Student(0, "user1", "username1", False, "repo1")
    student2 = Student(1, "user2", "username2", False, "repo2")

    first_course_with_deadlines.store_score(student1, "task_0_0", update_func(1))
    first_course_with_deadlines.store_score(student1, "task_1_3", update_func(expected_score_1))
    first_course_with_deadlines.store_score(student2, "task_0_0", update_func(expected_score_2))

    second_course_with_deadlines.store_score(student1, "task_1_0", update_func(99))
    second_course_with_deadlines.store_score(student2, "task_1_1", update_func(7))

    assert session.query(User).count() == expected_users
    assert session.query(UserOnCourse).count() == expected_user_on_course
    assert session.query(Grade).count() == expected_grades

    stats1 = first_course_with_deadlines.get_stats()
    all_scores1 = first_course_with_deadlines.get_all_scores()
    bonus_score1_user1 = first_course_with_deadlines.get_bonus_score("user1")
    scores1_user1 = first_course_with_deadlines.get_scores("user1")
    bonus_score1_user2 = first_course_with_deadlines.get_bonus_score("user2")
    scores1_user2 = first_course_with_deadlines.get_scores("user2")

    assert set(stats1.keys()) == {
        "task_0_0",
        "task_0_1",
        "task_0_2",
        "task_0_3",
        "task_1_0",
        "task_1_1",
        "task_1_2",
        "task_1_3",
        "task_1_4",
        "task_2_1",
        "task_2_2",
        "task_2_3",
        "task_3_0",
        "task_3_1",
        "task_3_2",
        "task_4_0",
        "task_4_1",
        "task_4_2",
    }
    assert stats1["task_0_0"] == 1.0
    assert stats1["task_1_3"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats1.items() if k not in ["task_0_0", "task_1_3"])

    assert all_scores1 == {
        "user1": {"task_0_0": 1, "task_1_3": expected_score_1},
        "user2": {"task_0_0": expected_score_2},
    }
    assert bonus_score1_user1 == expected_score_1
    assert scores1_user1 == {"task_0_0": 1, "task_1_3": expected_score_1}
    assert bonus_score1_user2 == 0
    assert scores1_user2 == {"task_0_0": expected_score_2}

    stats2 = second_course_with_deadlines.get_stats()
    all_scores2 = second_course_with_deadlines.get_all_scores()
    bonus_score2_user1 = second_course_with_deadlines.get_bonus_score("user1")
    scores2_user1 = second_course_with_deadlines.get_scores("user1")
    bonus_score2_user2 = second_course_with_deadlines.get_bonus_score("user2")
    scores2_user2 = second_course_with_deadlines.get_scores("user2")

    assert set(stats2.keys()) == {
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
        "task_2_2",
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
    assert stats2["task_1_0"] == expected_stats_ratio
    assert stats2["task_1_1"] == expected_stats_ratio
    assert all(v == 0.0 for k, v in stats2.items() if k not in ["task_1_0", "task_1_1"])

    assert all_scores2 == {"user1": {"task_1_0": 99}, "user2": {"task_1_1": 7}}
    assert bonus_score2_user1 == 0
    assert scores2_user1 == {"task_1_0": 99}
    assert bonus_score2_user2 == 0
    assert scores2_user2 == {"task_1_1": 7}


def test_deadlines(first_course_with_deadlines, second_course_with_deadlines, session):
    deadline1 = (
        session.query(Deadline)
        .join(TaskGroup)
        .filter(TaskGroup.name == "group_1")
        .join(Course)
        .filter(Course.name == "Test Course")
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
        .filter(Course.name == "Another Test Course")
        .one()
    )

    assert deadline2.start == datetime(2000, 1, 1, 18, 0, tzinfo=ZoneInfo("Europe/Moscow"))
    assert deadline2.steps == {0.5: datetime(2000, 2, 1, 23, 59, tzinfo=ZoneInfo("Europe/Moscow"))}
    assert deadline2.end == datetime(2000, 2, 1, 23, 59, tzinfo=ZoneInfo("Europe/Moscow"))


def test_course_change_params(first_course_db_api, postgres_container):
    with pytest.raises(AttributeError):
        DataBaseApi(
            DatabaseConfig(
                database_url=postgres_container.get_connection_url(),
                course_name="Test Course",
                gitlab_instance_host="gitlab.another_test.com",
                registration_secret="secret",
                token="test_token",
                show_allscores=True,
            )
        )

    DataBaseApi(
        DatabaseConfig(
            database_url=postgres_container.get_connection_url(),
            course_name="Test Course",
            gitlab_instance_host="gitlab.test.com",
            registration_secret="another_secret",
            token="test_token",
            show_allscores=False,
        )
    )


def test_bad_requests(first_course_with_deadlines, session):
    bonus_score = first_course_with_deadlines.get_bonus_score("random_user")
    scores = first_course_with_deadlines.get_scores("random_user")

    assert bonus_score == 0
    assert scores == {}

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0
    assert session.query(Grade).count() == 0


def test_auto_tables_creation(engine, alembic_cfg, postgres_container):
    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.downgrade(alembic_cfg, "base")  # Base.metadata.drop_all(engine)

    with pytest.raises(ProgrammingError) as exc_info:
        DataBaseApi(
            DatabaseConfig(
                database_url=postgres_container.get_connection_url(),
                course_name="Test Course",
                gitlab_instance_host="gitlab.test.com",
                registration_secret="secret",
                token="test_token",
                show_allscores=True,
            )
        )

    assert isinstance(exc_info.value.orig, UndefinedTable)

    db_api = DataBaseApi(
        DatabaseConfig(
            database_url=postgres_container.get_connection_url(),
            course_name="Test Course",
            gitlab_instance_host="gitlab.test.com",
            registration_secret="secret",
            token="test_token",
            show_allscores=True,
            apply_migrations=True,
        )
    )

    with Session(engine) as session:
        test_empty_course(db_api, session)


def test_auto_database_migration(engine, alembic_cfg, postgres_container):
    script = ScriptDirectory.from_config(alembic_cfg)
    revisions = list(script.walk_revisions("base", "head"))
    revisions.reverse()

    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection

        for revision in revisions:
            command.downgrade(alembic_cfg, "base")
            command.upgrade(alembic_cfg, revision.revision)

            db_api = DataBaseApi(
                DatabaseConfig(
                    database_url=postgres_container.get_connection_url(),
                    course_name="Test Course",
                    gitlab_instance_host="gitlab.test.com",
                    registration_secret="secret",
                    show_allscores=True,
                    apply_migrations=True,
                    token="test_token",
                )
            )

            with Session(engine) as session:
                test_empty_course(db_api, session)


def test_viewer_api(postgres_container):
    db_api = DataBaseApi(
        DatabaseConfig(
            database_url=postgres_container.get_connection_url(),
            course_name="Test Course",
            gitlab_instance_host="gitlab.test.com",
            registration_secret="secret",
            token="test_token",
            show_allscores=True,
            apply_migrations=True,
        )
    )
    assert db_api.get_scoreboard_url() == ""


def test_store_score_integrity_error(first_course_with_deadlines, session):
    student = Student(0, "user1", "username1", False, "repo1")

    user = User(username=student.username, gitlab_instance_host="gitlab.test.com")
    session.add(user)
    session.commit()

    score = first_course_with_deadlines.store_score(student, "task_0_0", update_func(1))
    assert score == 1

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1


def test_store_score_update_error(first_course_with_deadlines, session):
    student = Student(0, "user1", "username1", False, "repo1")

    def failing_update(_, score):
        raise ValueError("Update failed")

    with pytest.raises(ValueError) as exc_info:
        first_course_with_deadlines.store_score(student, "task_0_0", failing_update)
    assert "Update failed" in str(exc_info.value)

    assert session.query(Grade).count() == 0


def test_get_course_success(first_course_db_api):
    course = first_course_db_api.get_course(first_course_db_api.course_name)
    assert course.name == first_course_db_api.course_name


def test_get_course_unknown(first_course_db_api):
    course = first_course_db_api.get_course("Unknown course")
    assert not course


def test_apply_migrations_exceptions(first_course_db_api, postgres_container):
    with patch.object(command, "upgrade", side_effect=TestException()):
        with pytest.raises(TestException):
            first_course_db_api._apply_migrations(postgres_container.get_connection_url())

    with patch.object(command, "upgrade", side_effect=IntegrityError(None, None, TestException())):
        with pytest.raises(IntegrityError) as exc_info:
            first_course_db_api._apply_migrations(postgres_container.get_connection_url())

        assert isinstance(exc_info.value.orig, TestException)

    with patch.object(command, "upgrade", side_effect=IntegrityError(None, None, UniqueViolation())):
        first_course_db_api._apply_migrations(postgres_container.get_connection_url())

    with patch.object(command, "upgrade", side_effect=ProgrammingError(None, None, TestException())):
        with pytest.raises(ProgrammingError) as exc_info:
            first_course_db_api._apply_migrations(postgres_container.get_connection_url())

        assert isinstance(exc_info.value.orig, TestException)

    with patch.object(command, "upgrade", side_effect=ProgrammingError(None, None, DuplicateColumn())):
        first_course_db_api._apply_migrations(postgres_container.get_connection_url())

    with patch.object(command, "upgrade", side_effect=DuplicateTable()):
        first_course_db_api._apply_migrations(postgres_container.get_connection_url())


def test_sync_and_get_admin_status_admin_update(first_course_db_api, session):
    course_name = "Test Course"
    student = Student(id=1, username="user1", name="username1", course_admin=True, repo="repo1")
    user = User(id=1, username="user1", gitlab_instance_host="gitlab.test.com")
    user_on_course = UserOnCourse(user_id=user.id, course_id=1, repo_name="repo1", is_course_admin=False)

    session.add(user)
    session.add(user_on_course)
    session.commit()

    first_course_db_api.sync_and_get_admin_status(course_name, student)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_sync_and_get_admin_status_admin_no_update(first_course_db_api, session):
    course_name = "Test Course"
    student = Student(id=1, username="user1", name="username1", course_admin=False, repo="repo1")

    user = User(id=1, username="user1", gitlab_instance_host="gitlab.test.com")
    user_on_course = UserOnCourse(user_id=user.id, course_id=1, repo_name="repo1", is_course_admin=True)

    session.add(user)
    session.add(user_on_course)
    session.commit()

    first_course_db_api.sync_and_get_admin_status(course_name, student)

    updated_user_on_course = session.query(UserOnCourse).filter_by(user_id=user.id, course_id=1).one()
    assert updated_user_on_course.is_course_admin


def test_check_user_on_course(first_course_db_api, session):
    course_name = "Test Course"
    student = Student(id=1, username="user1", name="username1", course_admin=False, repo="repo1")

    user = User(id=1, username="user1", gitlab_instance_host="gitlab.test.com")
    user_on_course = UserOnCourse(user_id=user.id, course_id=1, repo_name="repo1", is_course_admin=True)

    session.add(user)
    session.add(user_on_course)
    session.commit()

    assert first_course_db_api.check_user_on_course(course_name, student)


def test_get_or_create_user_existing_get(first_course_db_api, session):
    course_name = "Test Course"
    student = Student(id=1, username="user1", name="username1", course_admin=False, repo="repo1")
    user = User(id=1, username="user1", gitlab_instance_host="gitlab.test.com")
    session.add(user)
    session.commit()

    get_user = first_course_db_api.get_or_create_user(student, course_name)
    assert get_user.id == user.id


def test_get_or_create_user_nonexisting_create(first_course_db_api, session):
    course_name = "Test Course"
    student = Student(id=1, username="user1", name="username1", course_admin=False, repo="repo1")

    get_user = first_course_db_api.get_or_create_user(student, course_name)
    assert get_user.username == student.username


def test_convert_timedelta_to_datetime():
    start = datetime(2025, 5, 5, 5, 5, tzinfo=ZoneInfo("Europe/Berlin"))
    value_datetime = datetime(2026, 6, 6, 6, 6, tzinfo=ZoneInfo("Europe/Berlin"))
    value_timedelta = timedelta(days=397, hours=1, minutes=1)  # value_datetime - start

    assert DataBaseApi._convert_timedelta_to_datetime(start, value_datetime) == value_datetime
    assert DataBaseApi._convert_timedelta_to_datetime(start, value_timedelta) == value_datetime

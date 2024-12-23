from typing import Any

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from manytask.config import ManytaskDeadlinesConfig
from manytask.database import DataBaseApi
from manytask.glab import Student
from manytask.models import Base, Course, Deadline, Grade, Task, TaskGroup, User, UserOnCourse


SQLALCHEMY_DATABASE_URL = 'sqlite:///file::memory:?cache=shared'
DEADLINES_CONFIG_FILE_1 = 'tests/.deadlines.test.yml'  # part of manytask config file
DEADLINES_CONFIG_FILE_2 = 'tests/.deadlines.test2.yml'  # part of manytask config file


@pytest.fixture(scope='module')
def engine():
    return create_engine(SQLALCHEMY_DATABASE_URL, echo=False)


@pytest.fixture(scope='module')
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    with Session(engine) as session:
        yield session


@pytest.fixture
def db_api(tables):
    return DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Test Course",
        gitlab_instance_host="gitlab.test.com",
        registration_secret="secret",
        show_allscores=True
    )


@pytest.fixture
def db_api2(tables):
    return DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Another Test Course",
        gitlab_instance_host="gitlab.test.com",
        registration_secret="secret",
        show_allscores=True
    )


def test_empty_course(db_api, session):
    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == 'Test Course'
    assert course.gitlab_instance_host == 'gitlab.test.com'
    assert course.registration_secret == 'secret'
    assert course.show_allscores == True

    stats = db_api.get_stats()
    all_scores = db_api.get_all_scores()
    bonus_score = db_api.get_bonus_score('some_user')
    scores = db_api.get_scores('some_user')

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}


def test_sync_columns(db_api):
    with open(DEADLINES_CONFIG_FILE_1, "r") as f:
        deadlines_config_data: dict[str, Any] = yaml.load(f, Loader=yaml.SafeLoader)
    deadlines_config = ManytaskDeadlinesConfig(**deadlines_config_data['deadlines'])

    db_api.sync_columns(deadlines_config)

    stats = db_api.get_stats()
    assert stats == {'task_0_0': 0, 'task_0_1': 0, 'task_0_2': 0,
                     'task_0_3': 0, 'task_1_0': 0, 'task_1_1': 0,
                     'task_1_2': 0, 'task_1_3': 0, 'task_1_4': 0,
                     'task_2_1': 0, 'task_2_2': 0, 'task_2_3': 0,
                     'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                     'task_4_0': 0, 'task_4_1': 0, 'task_4_2': 0}


def test_groups_and_tasks(session):
    assert session.query(TaskGroup).count() == 5
    assert session.query(Task).count() == 18

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == 'group_' + task.name[len('task_')]


def test_sync_columns_again(db_api):
    with open(DEADLINES_CONFIG_FILE_2, "r") as f:
        deadlines_config_data: dict[str, Any] = yaml.load(f, Loader=yaml.SafeLoader)
    # include not started and disabled tasks
    deadlines_config = ManytaskDeadlinesConfig(**deadlines_config_data['deadlines'])

    db_api.sync_columns(deadlines_config)

    stats = db_api.get_stats()
    assert stats == {'task_0_0': 0, 'task_0_1': 0, 'task_0_2': 0,
                     'task_0_3': 0, 'task_0_4': 0, 'task_0_5': 0,
                     'task_1_0': 0, 'task_1_1': 0, 'task_1_2': 0,
                     'task_1_3': 0, 'task_1_4': 0, 'task_2_1': 0,
                     'task_2_2': 0, 'task_2_3': 0, 'task_2_0': 0,
                     'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                     'task_3_3': 0, 'task_4_0': 0, 'task_4_1': 0,
                     'task_4_2': 0, 'task_5_0': 0, 'task_5_1': 0,
                     'task_5_2': 0}


def test_groups_and_tasks_again(session):
    assert session.query(TaskGroup).count() == 6
    assert session.query(Task).count() == 25

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == 'group_' + task.name[len('task_')]


def test_simple_store_score(db_api, session):
    student = Student(0, 'user1', 'username1', False, 'repo1')

    def update_func(_, score):
        return score + 1

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    assert db_api.store_score(student, 'not_exist_task', update_func) == 0

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1

    user = session.query(User).one()
    assert user.username == student.username
    assert user.gitlab_instance_host == 'gitlab.test.com'

    user_on_course = session.query(UserOnCourse).one()
    assert user_on_course.user_id == user.id
    assert user_on_course.course.name == 'Test Course'
    assert user_on_course.repo_name == student.repo

    assert session.query(Grade).count() == 0

    assert db_api.store_score(student, 'task_0_0', update_func) == 1

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).one()
    assert grade.user_on_course_id == user_on_course.id
    assert grade.task.name == 'task_0_0'
    assert grade.score == 1


def test_api_methods(db_api):
    stats = db_api.get_stats()
    all_scores = db_api.get_all_scores()
    bonus_score = db_api.get_bonus_score('user1')
    scores = db_api.get_scores('user1')

    assert stats == {'task_0_0': 1.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                     'task_0_3': 0.0, 'task_0_4': 0.0, 'task_0_5': 0.0,
                     'task_1_0': 0.0, 'task_1_1': 0.0, 'task_1_2': 0.0,
                     'task_1_3': 0.0, 'task_1_4': 0.0, 'task_2_1': 0.0,
                     'task_2_2': 0.0, 'task_2_3': 0.0, 'task_2_0': 0.0,
                     'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                     'task_3_3': 0.0, 'task_4_0': 0.0, 'task_4_1': 0.0,
                     'task_4_2': 0.0, 'task_5_0': 0.0, 'task_5_1': 0.0,
                     'task_5_2': 0.0}
    assert all_scores == {'user1': {'task_0_0': 1}}
    assert bonus_score == 0
    assert scores == {'task_0_0': 1}


def test_store_score_bonus_task(db_api, session):
    student = Student(0, 'user1', 'username1', False, 'repo1')

    def update_func(_, score):
        return score + 22

    assert db_api.store_score(student, 'task_1_3', update_func) == 22

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 2

    grade = session.query(Grade).join(Task).filter(Task.name == 'task_1_3').one()
    assert grade.task.name == 'task_1_3'
    assert grade.score == 22


def test_api_methods_with_bonus_task(db_api):
    stats = db_api.get_stats()
    all_scores = db_api.get_all_scores()
    bonus_score = db_api.get_bonus_score('user1')
    scores = db_api.get_scores('user1')

    assert stats == {'task_0_0': 1.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                     'task_0_3': 0.0, 'task_0_4': 0.0, 'task_0_5': 0.0,
                     'task_1_0': 0.0, 'task_1_1': 0.0, 'task_1_2': 0.0,
                     'task_1_3': 1.0, 'task_1_4': 0.0, 'task_2_1': 0.0,
                     'task_2_2': 0.0, 'task_2_3': 0.0, 'task_2_0': 0.0,
                     'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                     'task_3_3': 0.0, 'task_4_0': 0.0, 'task_4_1': 0.0,
                     'task_4_2': 0.0, 'task_5_0': 0.0, 'task_5_1': 0.0,
                     'task_5_2': 0.0}
    assert all_scores == {'user1': {'task_0_0': 1, 'task_1_3': 22}}
    assert bonus_score == 22
    assert scores == {'task_0_0': 1, 'task_1_3': 22}


def test_store_score_another_user(db_api, session):
    student = Student(1, 'user2', 'username2', False, 'repo2')

    def update_func(_, score):
        return score + 15

    assert db_api.store_score(student, 'task_0_0', update_func) == 15

    assert session.query(User).count() == 2
    assert session.query(UserOnCourse).count() == 2
    assert session.query(Grade).count() == 3

    grade = session.query(Grade).join(Task).filter(Task.name == 'task_0_0').join(
        UserOnCourse).filter(UserOnCourse.repo_name == student.repo).one()
    assert grade.task.name == 'task_0_0'
    assert grade.score == 15


def test_api_methods_with_another_user(db_api):
    stats = db_api.get_stats()
    all_scores = db_api.get_all_scores()
    bonus_score_user1 = db_api.get_bonus_score('user1')
    scores_user1 = db_api.get_scores('user1')
    bonus_score_user2 = db_api.get_bonus_score('user2')
    scores_user2 = db_api.get_scores('user2')

    assert stats == {'task_0_0': 1.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                     'task_0_3': 0.0, 'task_0_4': 0.0, 'task_0_5': 0.0,
                     'task_1_0': 0.0, 'task_1_1': 0.0, 'task_1_2': 0.0,
                     'task_1_3': 0.5, 'task_1_4': 0.0, 'task_2_1': 0.0,
                     'task_2_2': 0.0, 'task_2_3': 0.0, 'task_2_0': 0.0,
                     'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                     'task_3_3': 0.0, 'task_4_0': 0.0, 'task_4_1': 0.0,
                     'task_4_2': 0.0, 'task_5_0': 0.0, 'task_5_1': 0.0,
                     'task_5_2': 0.0}

    assert all_scores == {'user1': {'task_0_0': 1, 'task_1_3': 22}, 'user2': {'task_0_0': 15}}
    assert bonus_score_user1 == 22
    assert scores_user1 == {'task_0_0': 1, 'task_1_3': 22}
    assert bonus_score_user2 == 0
    assert scores_user2 == {'task_0_0': 15}


def test_another_course(db_api2, session):
    assert session.query(Course).count() == 2
    course = session.query(Course).filter_by(name='Another Test Course').one()

    assert course.name == 'Another Test Course'
    assert course.gitlab_instance_host == 'gitlab.test.com'
    assert course.registration_secret == 'secret'
    assert course.show_allscores == True

    stats = db_api2.get_stats()
    all_scores = db_api2.get_all_scores()
    bonus_score = db_api2.get_bonus_score('some_user')
    scores = db_api2.get_scores('some_user')

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}


def test_sync_columns2(db_api2):
    with open(DEADLINES_CONFIG_FILE_1, "r") as f:
        deadlines_config_data: dict[str, Any] = yaml.load(f, Loader=yaml.SafeLoader)
    deadlines_config = ManytaskDeadlinesConfig(**deadlines_config_data['deadlines'])

    db_api2.sync_columns(deadlines_config)

    stats = db_api2.get_stats()
    assert stats == {'task_0_0': 0, 'task_0_1': 0, 'task_0_2': 0,
                     'task_0_3': 0, 'task_1_0': 0, 'task_1_1': 0,
                     'task_1_2': 0, 'task_1_3': 0, 'task_1_4': 0,
                     'task_2_1': 0, 'task_2_2': 0, 'task_2_3': 0,
                     'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                     'task_4_0': 0, 'task_4_1': 0, 'task_4_2': 0}


def test_groups_and_tasks2(session):
    assert session.query(TaskGroup).count() == 6 + 5
    assert session.query(Task).count() == 25 + 18


def test_simple_store_score2(db_api2, session):
    student = Student(0, 'user1', 'username1', False, 'repo1')

    def update_func(_, score):
        return score + 99

    assert session.query(User).count() == 2
    assert session.query(UserOnCourse).count() == 2

    assert db_api2.store_score(student, 'task_5_2', update_func) == 0

    assert session.query(User).count() == 2
    assert session.query(UserOnCourse).count() == 3

    assert session.query(Grade).count() == 3

    assert db_api2.store_score(student, 'task_1_0', update_func) == 99

    assert session.query(User).count() == 2
    assert session.query(UserOnCourse).count() == 3
    assert session.query(Grade).count() == 4


def test_api_methods2(db_api2):
    stats = db_api2.get_stats()
    all_scores = db_api2.get_all_scores()
    bonus_score = db_api2.get_bonus_score('user1')
    scores = db_api2.get_scores('user1')

    assert stats == {'task_0_0': 0.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                     'task_0_3': 0.0, 'task_1_0': 1.0, 'task_1_1': 0.0,
                     'task_1_2': 0.0, 'task_1_3': 0.0, 'task_1_4': 0.0,
                     'task_2_1': 0.0, 'task_2_2': 0.0, 'task_2_3': 0.0,
                     'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                     'task_4_0': 0.0, 'task_4_1': 0.0, 'task_4_2': 0.0}
    assert all_scores == {'user1': {'task_1_0': 99}}
    assert bonus_score == 0
    assert scores == {'task_1_0': 99}


def test_new_user_on_second_course(db_api2, session):
    student = Student(2, 'user3', 'username3', False, 'repo3')

    def update_func(_, score):
        return score + 7

    assert db_api2.store_score(student, 'task_1_1', update_func) == 7

    assert session.query(User).count() == 3
    assert session.query(UserOnCourse).count() == 4
    assert session.query(Grade).count() == 5

    stats = db_api2.get_stats()
    all_scores = db_api2.get_all_scores()
    bonus_score1 = db_api2.get_bonus_score('user1')
    scores1 = db_api2.get_scores('user1')
    bonus_score3 = db_api2.get_bonus_score('user3')
    scores3 = db_api2.get_scores('user3')

    assert stats == {'task_0_0': 0.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                     'task_0_3': 0.0, 'task_1_0': 0.5, 'task_1_1': 0.5,
                     'task_1_2': 0.0, 'task_1_3': 0.0, 'task_1_4': 0.0,
                     'task_2_1': 0.0, 'task_2_2': 0.0, 'task_2_3': 0.0,
                     'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                     'task_4_0': 0.0, 'task_4_1': 0.0, 'task_4_2': 0.0}
    assert all_scores == {'user1': {'task_1_0': 99}, 'user3': {'task_1_1': 7}}
    assert bonus_score1 == 0
    assert scores1 == {'task_1_0': 99}
    assert bonus_score3 == 0
    assert scores3 == {'task_1_1': 7}


def test_first_course_again(db_api):
    test_api_methods_with_another_user(db_api)


def test_deadlines(session):
    deadline1 = session.query(Deadline).join(TaskGroup).filter(
        TaskGroup.name == 'group_1').join(Course).filter(Course.name == 'Test Course').one()

    assert deadline1.data == {'start': '2000-01-01T18:00:00+01:00',
                              'steps': {'0.5': '2000-02-01T23:59:00+01:00'},
                              'end': '2000-02-01T23:59:00+01:00'}

    deadline2 = session.query(Deadline).join(TaskGroup).filter(
        TaskGroup.name == 'group_1').join(Course).filter(Course.name == 'Another Test Course').one()

    assert deadline2.data == {'start': '2000-01-02T18:00:00+01:00',
                              'steps': {'0.5': '2000-02-02T23:59:00+01:00'},
                              'end': '2000-02-02T23:59:00+01:00'}

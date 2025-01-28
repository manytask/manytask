from typing import Any

import pytest
import yaml
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from manytask.config import ManytaskDeadlinesConfig
from manytask.database import DataBaseApi, StoredUser
from manytask.glab import Student
from manytask.models import Base, Course, Deadline, Grade, Task, TaskGroup, User, UserOnCourse


SQLALCHEMY_DATABASE_URL = 'sqlite:///file::memory:?cache=shared'

DEADLINES_CONFIG_FILES = [  # part of manytask config file
    'tests/.deadlines.test.yml',
    'tests/.deadlines.test2.yml'
]


@pytest.fixture
def engine():
    return create_engine(SQLALCHEMY_DATABASE_URL, echo=False)


@pytest.fixture
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    with Session(engine) as session:
        yield session


@pytest.fixture
def first_course_db_api(tables):
    return DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Test Course",
        gitlab_instance_host="gitlab.test.com",
        registration_secret="secret",
        token="test_token",
        show_allscores=True
    )


@pytest.fixture
def second_course_db_api(tables):
    return DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Another Test Course",
        gitlab_instance_host="gitlab.test.com",
        token="another_test_token",
        registration_secret="secret",
        show_allscores=True
    )


def load_deadlines_config_and_sync_columns(db_api: DataBaseApi, yaml_file_file_path: str):
    with open(yaml_file_file_path, "r") as f:
        deadlines_config_data: dict[str, Any] = yaml.load(f, Loader=yaml.SafeLoader)
    deadlines_config = ManytaskDeadlinesConfig(**deadlines_config_data['deadlines'])

    db_api.sync_columns(deadlines_config)


def update_func(add: int):
    def _update_func(_, score):
        return score + add

    return _update_func


def test_empty_course(first_course_db_api, session):
    assert session.query(Course).count() == 1
    course = session.query(Course).one()

    assert course.name == 'Test Course'
    assert course.gitlab_instance_host == 'gitlab.test.com'
    assert course.registration_secret == 'secret'
    assert course.token == 'test_token'
    assert course.show_allscores

    stats = first_course_db_api.get_stats()
    all_scores = first_course_db_api.get_all_scores()
    bonus_score = first_course_db_api.get_bonus_score('some_user')
    scores = first_course_db_api.get_scores('some_user')

    assert stats == {}
    assert all_scores == {}
    assert bonus_score == 0
    assert scores == {}


def test_sync_columns(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[0])

    stats = first_course_db_api.get_stats()
    assert stats == {'task_0_0': 0, 'task_0_1': 0, 'task_0_2': 0,
                     'task_0_3': 0, 'task_1_0': 0, 'task_1_1': 0,
                     'task_1_2': 0, 'task_1_3': 0, 'task_1_4': 0,
                     'task_2_1': 0, 'task_2_2': 0, 'task_2_3': 0,
                     'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                     'task_4_0': 0, 'task_4_1': 0, 'task_4_2': 0}

    assert session.query(TaskGroup).count() == 5
    assert session.query(Task).count() == 18

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == 'group_' + task.name[len('task_')]


def test_resync_columns(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[0])
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    stats = first_course_db_api.get_stats()
    assert stats == {'task_0_0': 0, 'task_0_1': 0, 'task_0_2': 0,
                     'task_0_3': 0, 'task_0_4': 0, 'task_0_5': 0,
                     'task_1_0': 0, 'task_1_1': 0, 'task_1_2': 0,
                     'task_1_3': 0, 'task_1_4': 0, 'task_2_1': 0,
                     'task_2_2': 0, 'task_2_3': 0, 'task_2_0': 0,
                     'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                     'task_3_3': 0, 'task_4_0': 0, 'task_4_1': 0,
                     'task_4_2': 0, 'task_5_0': 0, 'task_5_1': 0,
                     'task_5_2': 0}

    assert session.query(TaskGroup).count() == 6
    assert session.query(Task).count() == 25

    tasks = session.query(Task).all()
    for task in tasks:
        assert task.group.name == 'group_' + task.name[len('task_')]


def test_store_score(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    student = Student(0, 'user1', 'username1', False, 'repo1')

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    assert first_course_db_api.store_score(student, 'not_exist_task', update_func(1)) == 0

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

    assert first_course_db_api.store_score(student, 'task_0_0', update_func(1)) == 1

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).one()
    assert grade.user_on_course_id == user_on_course.id
    assert grade.task.name == 'task_0_0'
    assert grade.score == 1

    stats = first_course_db_api.get_stats()
    all_scores = first_course_db_api.get_all_scores()
    bonus_score = first_course_db_api.get_bonus_score('user1')
    scores = first_course_db_api.get_scores('user1')

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


def test_store_score_bonus_task(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    student = Student(0, 'user1', 'username1', False, 'repo1')

    assert first_course_db_api.store_score(student, 'task_1_3', update_func(22)) == 22

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1
    assert session.query(Grade).count() == 1

    grade = session.query(Grade).join(Task).filter(Task.name == 'task_1_3').one()
    assert grade.task.name == 'task_1_3'
    assert grade.score == 22

    stats = first_course_db_api.get_stats()
    all_scores = first_course_db_api.get_all_scores()
    bonus_score = first_course_db_api.get_bonus_score('user1')
    scores = first_course_db_api.get_scores('user1')

    assert stats == {'task_0_0': 0.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                     'task_0_3': 0.0, 'task_0_4': 0.0, 'task_0_5': 0.0,
                     'task_1_0': 0.0, 'task_1_1': 0.0, 'task_1_2': 0.0,
                     'task_1_3': 1.0, 'task_1_4': 0.0, 'task_2_1': 0.0,
                     'task_2_2': 0.0, 'task_2_3': 0.0, 'task_2_0': 0.0,
                     'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                     'task_3_3': 0.0, 'task_4_0': 0.0, 'task_4_1': 0.0,
                     'task_4_2': 0.0, 'task_5_0': 0.0, 'task_5_1': 0.0,
                     'task_5_2': 0.0}
    assert all_scores == {'user1': {'task_1_3': 22}}
    assert bonus_score == 22
    assert scores == {'task_1_3': 22}


def test_get_and_sync_stored_user(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    student = Student(0, 'user1', 'username1', False, 'repo1')  # default student(not admin in gitlab)

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0

    stored_user = first_course_db_api.get_stored_user(student)

    assert stored_user == StoredUser(
        username='user1',
        course_admin=False
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1

    student.course_admin = True  # admin in gitlab

    stored_user = first_course_db_api.sync_stored_user(student)

    assert stored_user == StoredUser(
        username='user1',
        course_admin=True
    )

    student.course_admin = False  # lost admin rules in gitlab, but in database stored that user is admin

    stored_user = first_course_db_api.sync_stored_user(student)

    assert stored_user == StoredUser(
        username='user1',
        course_admin=True
    )

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 1


def test_many_users(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    student1 = Student(0, 'user1', 'username1', False, 'repo1')
    first_course_db_api.store_score(student1, 'task_0_0', update_func(1))
    first_course_db_api.store_score(student1, 'task_1_3', update_func(22))

    student2 = Student(1, 'user2', 'username2', False, 'repo2')

    assert first_course_db_api.store_score(student2, 'task_0_0', update_func(15)) == 15

    assert session.query(User).count() == 2
    assert session.query(UserOnCourse).count() == 2
    assert session.query(Grade).count() == 3

    stats = first_course_db_api.get_stats()
    all_scores = first_course_db_api.get_all_scores()
    bonus_score_user1 = first_course_db_api.get_bonus_score('user1')
    scores_user1 = first_course_db_api.get_scores('user1')
    bonus_score_user2 = first_course_db_api.get_bonus_score('user2')
    scores_user2 = first_course_db_api.get_scores('user2')

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


def test_many_courses(first_course_db_api, second_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[0])
    load_deadlines_config_and_sync_columns(second_course_db_api, DEADLINES_CONFIG_FILES[1])

    student = Student(0, 'user1', 'username1', False, 'repo1')
    first_course_db_api.store_score(student, 'task_0_0', update_func(30))
    second_course_db_api.store_score(student, 'task_1_3', update_func(40))

    assert session.query(User).count() == 1
    assert session.query(UserOnCourse).count() == 2
    assert session.query(Grade).count() == 2

    stats1 = first_course_db_api.get_stats()
    all_scores1 = first_course_db_api.get_all_scores()
    bonus_score_user1 = first_course_db_api.get_bonus_score('user1')
    scores_user1 = first_course_db_api.get_scores('user1')

    assert stats1 == {'task_0_0': 1.0, 'task_0_1': 0, 'task_0_2': 0,
                      'task_0_3': 0, 'task_1_0': 0, 'task_1_1': 0,
                      'task_1_2': 0, 'task_1_3': 0, 'task_1_4': 0,
                      'task_2_1': 0, 'task_2_2': 0, 'task_2_3': 0,
                      'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                      'task_4_0': 0, 'task_4_1': 0, 'task_4_2': 0}

    assert all_scores1 == {'user1': {'task_0_0': 30}}
    assert bonus_score_user1 == 0
    assert scores_user1 == {'task_0_0': 30}

    stats2 = second_course_db_api.get_stats()
    all_scores2 = second_course_db_api.get_all_scores()
    bonus_score_user2 = second_course_db_api.get_bonus_score('user1')
    scores_user2 = second_course_db_api.get_scores('user1')

    assert stats2 == {'task_0_0': 0.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                      'task_0_3': 0.0, 'task_0_4': 0.0, 'task_0_5': 0.0,
                      'task_1_0': 0.0, 'task_1_1': 0.0, 'task_1_2': 0.0,
                      'task_1_3': 1.0, 'task_1_4': 0.0, 'task_2_1': 0.0,
                      'task_2_2': 0.0, 'task_2_3': 0.0, 'task_2_0': 0.0,
                      'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                      'task_3_3': 0.0, 'task_4_0': 0.0, 'task_4_1': 0.0,
                      'task_4_2': 0.0, 'task_5_0': 0.0, 'task_5_1': 0.0,
                      'task_5_2': 0.0}

    assert all_scores2 == {'user1': {'task_1_3': 40}}
    assert bonus_score_user2 == 40
    assert scores_user2 == {'task_1_3': 40}


def test_many_users_and_courses(first_course_db_api, second_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[0])
    load_deadlines_config_and_sync_columns(second_course_db_api, DEADLINES_CONFIG_FILES[1])

    student1 = Student(0, 'user1', 'username1', False, 'repo1')
    student2 = Student(1, 'user2', 'username2', False, 'repo2')

    first_course_db_api.store_score(student1, 'task_0_0', update_func(1))
    first_course_db_api.store_score(student1, 'task_1_3', update_func(22))
    first_course_db_api.store_score(student2, 'task_0_0', update_func(15))

    second_course_db_api.store_score(student1, 'task_1_0', update_func(99))
    second_course_db_api.store_score(student2, 'task_1_1', update_func(7))

    assert session.query(User).count() == 2
    assert session.query(UserOnCourse).count() == 4
    assert session.query(Grade).count() == 5

    stats1 = first_course_db_api.get_stats()
    all_scores1 = first_course_db_api.get_all_scores()
    bonus_score1_user1 = first_course_db_api.get_bonus_score('user1')
    scores1_user1 = first_course_db_api.get_scores('user1')
    bonus_score1_user2 = first_course_db_api.get_bonus_score('user2')
    scores1_user2 = first_course_db_api.get_scores('user2')

    assert stats1 == {'task_0_0': 1.0, 'task_0_1': 0, 'task_0_2': 0,
                      'task_0_3': 0, 'task_1_0': 0, 'task_1_1': 0,
                      'task_1_2': 0, 'task_1_3': 0.5, 'task_1_4': 0,
                      'task_2_1': 0, 'task_2_2': 0, 'task_2_3': 0,
                      'task_3_0': 0, 'task_3_1': 0, 'task_3_2': 0,
                      'task_4_0': 0, 'task_4_1': 0, 'task_4_2': 0}

    assert all_scores1 == {'user1': {'task_0_0': 1, 'task_1_3': 22}, 'user2': {'task_0_0': 15}}
    assert bonus_score1_user1 == 22
    assert scores1_user1 == {'task_0_0': 1, 'task_1_3': 22}
    assert bonus_score1_user2 == 0
    assert scores1_user2 == {'task_0_0': 15}

    stats2 = second_course_db_api.get_stats()
    all_scores2 = second_course_db_api.get_all_scores()
    bonus_score2_user1 = second_course_db_api.get_bonus_score('user1')
    scores2_user1 = second_course_db_api.get_scores('user1')
    bonus_score2_user2 = second_course_db_api.get_bonus_score('user2')
    scores2_user2 = second_course_db_api.get_scores('user2')

    assert stats2 == {'task_0_0': 0.0, 'task_0_1': 0.0, 'task_0_2': 0.0,
                      'task_0_3': 0.0, 'task_0_4': 0.0, 'task_0_5': 0.0,
                      'task_1_0': 0.5, 'task_1_1': 0.5, 'task_1_2': 0.0,
                      'task_1_3': 0.0, 'task_1_4': 0.0, 'task_2_1': 0.0,
                      'task_2_2': 0.0, 'task_2_3': 0.0, 'task_2_0': 0.0,
                      'task_3_0': 0.0, 'task_3_1': 0.0, 'task_3_2': 0.0,
                      'task_3_3': 0.0, 'task_4_0': 0.0, 'task_4_1': 0.0,
                      'task_4_2': 0.0, 'task_5_0': 0.0, 'task_5_1': 0.0,
                      'task_5_2': 0.0}

    assert all_scores2 == {'user1': {'task_1_0': 99}, 'user2': {'task_1_1': 7}}
    assert bonus_score2_user1 == 0
    assert scores2_user1 == {'task_1_0': 99}
    assert bonus_score2_user2 == 0
    assert scores2_user2 == {'task_1_1': 7}


def test_deadlines(first_course_db_api, second_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])
    load_deadlines_config_and_sync_columns(second_course_db_api, DEADLINES_CONFIG_FILES[0])

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


def test_course_change_params(first_course_db_api):  # noqa
    with pytest.raises(AttributeError):
        DataBaseApi(
            database_url=SQLALCHEMY_DATABASE_URL,
            course_name="Test Course",
            gitlab_instance_host="gitlab.another_test.com",
            registration_secret="secret",
            token="test_token",
            show_allscores=True
        )

    DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Test Course",
        gitlab_instance_host="gitlab.test.com",
        registration_secret="another_secret",
        token="test_token",
        show_allscores=False
    )


def test_bad_requests(first_course_db_api, session):
    load_deadlines_config_and_sync_columns(first_course_db_api, DEADLINES_CONFIG_FILES[1])

    bonus_score = first_course_db_api.get_bonus_score('random_user')
    scores = first_course_db_api.get_scores('random_user')

    assert bonus_score == 0
    assert scores == {}

    assert session.query(User).count() == 0
    assert session.query(UserOnCourse).count() == 0
    assert session.query(Grade).count() == 0


def test_auto_tables_creation(engine):
    with pytest.raises(OperationalError):
        db_api = DataBaseApi(
            database_url=SQLALCHEMY_DATABASE_URL,
            course_name="Test Course",
            gitlab_instance_host="gitlab.test.com",
            registration_secret="secret",
            token="test_token",
            show_allscores=True
        )

    db_api = DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Test Course",
        gitlab_instance_host="gitlab.test.com",
        registration_secret="secret",
        token="test_token",
        show_allscores=True,
        create_tables_if_not_exist=True
    )

    with Session(engine) as session:
        test_empty_course(db_api, session)

def test_viewer_api():
    db_api = DataBaseApi(
        database_url=SQLALCHEMY_DATABASE_URL,
        course_name="Test Course",
        gitlab_instance_host="gitlab.test.com",
        registration_secret="secret",
        token="test_token",
        show_allscores=True,
        create_tables_if_not_exist=True
    )
    assert db_api.get_scoreboard_url() == ""

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from manytask.models import (
    Base,
    Course,
    Deadline,
    FloatDatetimeDict,
    Grade,
    Task,
    TaskGroup,
    User,
    UserOnCourse,
    validate_gitlab_instance_host,
)

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

TEST_DEADLINE_DATA_INT = 12345
TEST_GRADE_SCORE = 77
TEST_TASK_COUNT = 2
TEST_TASK_COUNT_LARGE = 3
TEST_GRADE_COUNT = 4
TEST_DEADLINE_ID = 12345
TEST_GRADE_SCORE_2 = 123456
TEST_GRADE_SCORE_3 = 1234567
TEST_GRADE_SCORE_4 = 12345678
TEST_TASK_SCORE = 100
TEST_TASK_POSITION = 7
TEST_TASK_GROUP_POSITION = 5
TEST_MAX_SUBMISSIONS = 10
TEST_SUBMISSION_PENALTY = 0.1
TEST_DEADLINE_STEPS = {0.4: datetime(2000, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Europe/Berlin"))}


@pytest.fixture(scope="module")
def engine():
    return create_engine(SQLALCHEMY_DATABASE_URL, echo=False)


@pytest.fixture(scope="module")
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    with Session(engine) as session:
        yield session


@pytest.fixture
def fixed_current_time():
    return datetime(2024, 12, 23, 12, 30, 10)


def test_user_simple(session):
    user = User(username="test_user", gitlab_instance_host="gitlab.inst.org")
    session.add(user)
    session.commit()

    retrieved = session.query(User).filter_by(username="test_user").first()
    assert retrieved is not None
    assert retrieved.username == "test_user"


def test_user_unique_username_and_gitlab_instance(session):
    user1 = User(username="unique_user1", gitlab_instance_host="gitlab.inst1.org")
    user2 = User(username="unique_user1", gitlab_instance_host="gitlab.inst2.org")
    user3 = User(username="unique_user2", gitlab_instance_host="gitlab.inst1.org")
    user4 = User(username="unique_user2", gitlab_instance_host="gitlab.inst2.org")
    user5 = User(username="unique_user1", gitlab_instance_host="gitlab.inst1.org")
    session.add_all([user1, user2, user3, user4])
    session.commit()
    session.add(user5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_course(session):
    course = Course(
        name="test_course",
        registration_secret="test_secret",
        token="test_token",
        gitlab_instance_host="gitlab.inst.org",
    )
    session.add(course)
    session.commit()

    retrieved = session.query(Course).filter_by(name="test_course").first()
    assert retrieved is not None
    assert retrieved.registration_secret == "test_secret"
    assert retrieved.gitlab_instance_host == "gitlab.inst.org"
    assert retrieved.token == "test_token"
    assert not retrieved.show_allscores
    assert retrieved.timezone == "UTC"
    assert retrieved.max_submissions is None
    assert retrieved.submission_penalty == 0


def test_course_deadlines_parameters(session):
    course = Course(
        name="test_course_deadlines_parameters",
        registration_secret="test_secret_deadlines_parameters",
        token="test_token_deadlines_parameters",
        gitlab_instance_host="gitlab.inst.org",
        show_allscores=True,
        timezone="Europe/Berlin",
        max_submissions=TEST_MAX_SUBMISSIONS,
        submission_penalty=TEST_SUBMISSION_PENALTY,
    )
    session.add(course)
    session.commit()

    retrieved = session.query(Course).filter_by(name="test_course_deadlines_parameters").first()
    assert retrieved is not None
    assert retrieved.registration_secret == "test_secret_deadlines_parameters"
    assert retrieved.gitlab_instance_host == "gitlab.inst.org"
    assert retrieved.token == "test_token_deadlines_parameters"
    assert retrieved.show_allscores
    assert retrieved.timezone == "Europe/Berlin"
    assert retrieved.max_submissions == TEST_MAX_SUBMISSIONS
    assert retrieved.submission_penalty == TEST_SUBMISSION_PENALTY


def test_course_unique_name(session):
    course1 = Course(
        name="unique_course", registration_secret="secret1", token="test_token1", gitlab_instance_host="gitlab.inst.org"
    )
    course2 = Course(
        name="unique_course", registration_secret="secret2", token="test_token2", gitlab_instance_host="gitlab.inst.org"
    )
    session.add(course1)
    session.commit()
    session.add(course2)
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_on_course(session):
    user = User(username="user1", gitlab_instance_host="gitlab.inst.org")
    course = Course(
        name="course1", registration_secret="secret1", token="test_token1_", gitlab_instance_host="gitlab.inst.org"
    )
    session.add_all([user, course])
    session.commit()

    user_on_course = UserOnCourse(user=user, course=course, repo_name="user1_repo")
    session.add(user_on_course)
    session.commit()

    retrieved_user = session.query(User).filter_by(username="user1").first()
    assert len(retrieved_user.users_on_courses.all()) == 1
    assert retrieved_user.users_on_courses[0].course.name == "course1"

    retrieved_course = session.query(Course).filter_by(name="course1").first()
    assert len(retrieved_course.users_on_courses.all()) == 1
    assert retrieved_course.users_on_courses[0].user.username == "user1"

    retrieved_user_on_course = session.query(UserOnCourse).filter_by(repo_name="user1_repo").first()
    assert retrieved_user_on_course.is_course_admin is False

    retrieved_user_on_course.is_course_admin = True
    session.commit()

    retrieved_user_on_course = session.query(UserOnCourse).filter_by(repo_name="user1_repo").first()
    assert retrieved_user_on_course.is_course_admin is True


def test_user_on_course_unique_ids(session):
    user1 = User(username="user001", gitlab_instance_host="gitlab.inst.org")
    course1 = Course(
        name="course001", registration_secret="secret001", token="test_token001", gitlab_instance_host="gitlab.inst.org"
    )
    user2 = User(username="user002", gitlab_instance_host="gitlab.inst.org")
    course2 = Course(
        name="course002", registration_secret="secret002", token="test_token002", gitlab_instance_host="gitlab.inst.org"
    )

    user_on_course1 = UserOnCourse(user=user1, course=course1, repo_name="user_repo01")
    user_on_course2 = UserOnCourse(user=user1, course=course2, repo_name="user_repo02")
    user_on_course3 = UserOnCourse(user=user2, course=course1, repo_name="user_repo03")
    user_on_course4 = UserOnCourse(user=user2, course=course2, repo_name="user_repo04")
    session.add_all([user_on_course1, user_on_course2, user_on_course3, user_on_course4])
    session.commit()

    user_on_course5 = UserOnCourse(user=user1, course=course1, repo_name="user_repo05")

    session.add(user_on_course5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deadline(session):
    course = Course(
        name="course0001", registration_secret="secret", token="test_token0001", gitlab_instance_host="gitlab.inst.org"
    )
    session.add(course)
    session.commit()

    deadline = Deadline(steps=TEST_DEADLINE_STEPS)
    session.add(deadline)
    task_group = TaskGroup(name="group1", deadline=deadline, course=course)
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group1").first()
    assert retrieved.deadline is not None

    assert retrieved.deadline.steps == TEST_DEADLINE_STEPS


def test_task_group(session):
    course = Course(
        name="course0002", registration_secret="secret", token="test_token2", gitlab_instance_host="gitlab.inst.org"
    )
    session.add(course)
    task_group = TaskGroup(name="group2", course=course, position=TEST_TASK_GROUP_POSITION)
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group2").first()
    assert retrieved.deadline is None
    assert retrieved.enabled
    assert retrieved.position == TEST_TASK_GROUP_POSITION


def test_deadline_steps(session, fixed_current_time):
    course = Course(
        name="course0003", registration_secret="secret", token="test_token3", gitlab_instance_host="gitlab.inst.org"
    )
    session.add(course)
    session.commit()

    deadline1 = Deadline(id=1001)
    deadline2 = Deadline(id=1002, steps={})
    deadline3 = Deadline(id=1003, steps=None)
    deadline4 = Deadline(id=1004, steps=TEST_DEADLINE_STEPS)
    session.add_all([deadline1, deadline2, deadline3, deadline4])
    session.commit()

    assert session.query(Deadline).filter_by(id=1001).one().steps == {}
    assert session.query(Deadline).filter_by(id=1002).one().steps == {}
    assert session.query(Deadline).filter_by(id=1003).one().steps == {}
    assert session.query(Deadline).filter_by(id=1004).one().steps == TEST_DEADLINE_STEPS

    class MyObject:
        def __init__(self, value):
            self.value = value

    deadlines_bad_type = [
        Deadline(id=1005, steps="some_data"),
        Deadline(id=1006, steps=b"binary_data"),
        Deadline(id=1007, steps=MyObject(10)),
        Deadline(id=1008, steps={1, 2, 3}),
        Deadline(id=1009, steps=fixed_current_time),
        Deadline(id=1010, steps=[]),
        Deadline(id=1011, steps=TEST_DEADLINE_DATA_INT),
    ]

    for deadline in deadlines_bad_type:
        with pytest.raises(StatementError) as exc_info:
            session.add(deadline)
            session.commit()
        session.rollback()

        assert isinstance(exc_info.value.orig, TypeError)
        assert "value must be a dict, not" in str(exc_info.value)

    deadlines_bad_key_type = [
        Deadline(id=1021, steps={TEST_DEADLINE_DATA_INT: TEST_DEADLINE_STEPS[0.4]}),
        Deadline(id=1022, steps={"0.4": TEST_DEADLINE_STEPS[0.4]}),
        Deadline(id=1023, steps={MyObject(10): TEST_DEADLINE_STEPS[0.4]}),
    ]

    for deadline in deadlines_bad_key_type:
        with pytest.raises(StatementError) as exc_info:
            session.add(deadline)
            session.commit()
        session.rollback()

        assert isinstance(exc_info.value.orig, TypeError)
        assert "must be a float, not" in str(exc_info.value)

    deadlines_bad_value_type = [
        Deadline(id=1031, steps={0.4: timedelta()}),
        Deadline(id=1032, steps={0.4: TEST_DEADLINE_STEPS[0.4].isoformat()}),
        Deadline(id=1033, steps={0.4: TEST_DEADLINE_STEPS}),
    ]

    for deadline in deadlines_bad_value_type:
        with pytest.raises(StatementError) as exc_info:
            session.add(deadline)
            session.commit()
        session.rollback()

        assert isinstance(exc_info.value.orig, TypeError)
        assert "must be a datetime, not" in str(exc_info.value)

    deadline_no_timezone = Deadline(id=1031, steps={0.4: TEST_DEADLINE_STEPS[0.4].replace(tzinfo=None)})

    with pytest.raises(StatementError) as exc_info:
        session.add(deadline_no_timezone)
        session.commit()
    session.rollback()

    assert isinstance(exc_info.value.orig, TypeError)
    assert "must have timezone information" in str(exc_info.value)


def test_task(session):
    course = Course(
        name="course3", registration_secret="secret3", token="test_token3_", gitlab_instance_host="gitlab.inst.org"
    )
    task_group = TaskGroup(name="group3", course=course)
    session.add_all([course, task_group])
    session.commit()

    task = Task(name="task1", group=task_group)
    session.add(task)
    session.commit()

    retrieved_task = session.query(Task).filter_by(name="task1").first()
    assert retrieved_task.group.course.name == "course3"
    assert retrieved_task.group.name == "group3"
    assert retrieved_task.score == 0
    assert not retrieved_task.is_bonus
    assert not retrieved_task.is_special
    assert retrieved_task.enabled
    assert not retrieved_task.url
    assert retrieved_task.position == 0

    task = Task(
        name="task_with_all_params",
        score=TEST_TASK_SCORE,
        is_bonus=True,
        is_special=True,
        enabled=False,
        url="https://www.python.org/about/gettingstarted/",
        position=TEST_TASK_POSITION,
        group=task_group,
    )
    session.add(task)
    session.commit()

    retrieved_task = session.query(Task).filter_by(name="task_with_all_params").first()
    assert retrieved_task.group.course.name == "course3"
    assert retrieved_task.group.name == "group3"
    assert retrieved_task.score == TEST_TASK_SCORE
    assert retrieved_task.is_bonus
    assert retrieved_task.is_special
    assert not retrieved_task.enabled
    assert retrieved_task.url == "https://www.python.org/about/gettingstarted/"
    assert retrieved_task.position == TEST_TASK_POSITION


def test_grade(session, fixed_current_time):
    user = User(username="user2", gitlab_instance_host="gitlab.inst.org")
    course = Course(
        name="course4", registration_secret="secret4", token="test_token4", gitlab_instance_host="gitlab.inst.org"
    )
    user_on_course = UserOnCourse(user=user, course=course, repo_name="repo_name1")
    task_group = TaskGroup(name="group4", course=course)
    task = Task(name="task2", group=task_group)
    session.add_all([user, course, user_on_course, task_group, task])
    session.commit()

    grade = Grade(user_on_course=user_on_course, task=task, score=TEST_GRADE_SCORE, last_submit_date=fixed_current_time)
    session.add(grade)
    session.commit()

    retrieved_grade = session.query(Grade).first()
    assert retrieved_grade.user_on_course.user.username == "user2"
    assert retrieved_grade.score == TEST_GRADE_SCORE
    assert retrieved_grade.last_submit_date == fixed_current_time


def test_grade_unique_ids(session, fixed_current_time):
    course = Course(
        name="course101", registration_secret="secret101", token="test_token101", gitlab_instance_host="gitlab.inst.org"
    )
    task_group = TaskGroup(name="group101", course=course)
    user1 = User(username="user101", gitlab_instance_host="gitlab.inst.org")
    user2 = User(username="user102", gitlab_instance_host="gitlab.inst.org")
    user_on_course1 = UserOnCourse(user=user1, course=course, repo_name="repo_name1")
    user_on_course2 = UserOnCourse(user=user2, course=course, repo_name="repo_name1")
    task1 = Task(name="task101", group=task_group)
    task2 = Task(name="task102", group=task_group)
    session.add_all([course, task_group, user1, user2, task1, task2, user_on_course1, user_on_course2])
    session.commit()

    grade1 = Grade(user_on_course=user_on_course1, task=task1, score=11, last_submit_date=fixed_current_time)
    grade2 = Grade(user_on_course=user_on_course1, task=task2, score=11, last_submit_date=fixed_current_time)
    grade3 = Grade(user_on_course=user_on_course2, task=task1, score=11, last_submit_date=fixed_current_time)
    grade4 = Grade(user_on_course=user_on_course2, task=task2, score=11, last_submit_date=fixed_current_time)

    session.add_all([grade1, grade2, grade3, grade4])
    session.commit()

    grade5 = Grade(user_on_course=user_on_course1, task=task1, score=11, last_submit_date=fixed_current_time)
    session.add(grade5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_course_tasks(session):
    course = Course(
        name="course11", registration_secret="secret11", token="test_token11", gitlab_instance_host="gitlab.inst.org"
    )
    task_group = TaskGroup(name="group11", course=course)
    task1 = Task(name="task11_1", group=task_group)
    task2 = Task(name="task11_2", group=task_group)
    session.add_all([course, task_group, task1, task2])
    session.commit()

    retrieved_course = session.query(Course).filter_by(name="course11").first()
    retrieved_task_group = retrieved_course.task_groups.one()

    assert len(retrieved_task_group.tasks.all()) == TEST_TASK_COUNT
    task_names = [task.name for task in retrieved_task_group.tasks]
    assert "task11_1" in task_names
    assert "task11_2" in task_names


def test_task_group_tasks(session):
    course = Course(
        name="course12", registration_secret="secret12", token="test_token12", gitlab_instance_host="gitlab.inst.org"
    )
    task_group = TaskGroup(name="group12", course=course)
    task1 = Task(name="task12_1", group=task_group)
    task2 = Task(name="task12_2", group=task_group)
    session.add_all([course, task_group, task1, task2])
    session.commit()

    retrieved_group = session.query(TaskGroup).filter_by(name="group12").first()
    assert len(retrieved_group.tasks.all()) == TEST_TASK_COUNT
    task_names = [task.name for task in retrieved_group.tasks]
    assert "task12_1" in task_names
    assert "task12_2" in task_names


def test_users_on_course_validate_gitlab_instance(session):
    course = Course(
        name="course21", registration_secret="secret", token="test_token21", gitlab_instance_host="gitlab.inst.org"
    )
    user = User(username="user21", gitlab_instance_host="another.gitlab.inst.org")
    user_on_course = UserOnCourse(user=user, course=course, repo_name="user21_repo")

    session.add_all([user, course, user_on_course])
    with pytest.raises(ValueError):
        session.commit()


def test_cascade_delete_course(session):
    course = Course(
        name="cascade_course",
        registration_secret="secret",
        token="test_token__",
        gitlab_instance_host="gitlab.inst.org",
    )
    task_group1 = TaskGroup(name="cascade_group1", course=course)
    task_group2 = TaskGroup(name="cascade_group2", course=course)
    user1 = User(username="cascade_user1", gitlab_instance_host="gitlab.inst.org")
    user2 = User(username="cascade_user2", gitlab_instance_host="gitlab.inst.org")
    user_on_course1 = UserOnCourse(user=user1, course=course, repo_name="cascade_repo1")
    user_on_course2 = UserOnCourse(user=user2, course=course, repo_name="cascade_repo2")
    session.add_all([course, task_group1, task_group2, user1, user2, user_on_course1, user_on_course2])
    session.commit()

    task1 = Task(name="cascade_task1", group=task_group1)
    task2 = Task(name="cascade_task2", group=task_group2)
    task3 = Task(name="cascade_task3", group=task_group2)
    session.add_all([task1, task2, task3])
    session.commit()

    grade1 = Grade(user_on_course=user_on_course1, task=task1, score=TEST_DEADLINE_DATA_INT)
    grade2 = Grade(user_on_course=user_on_course2, task=task1, score=TEST_DEADLINE_DATA_INT)
    grade3 = Grade(user_on_course=user_on_course2, task=task2, score=TEST_DEADLINE_DATA_INT)
    grade4 = Grade(user_on_course=user_on_course2, task=task3, score=TEST_DEADLINE_DATA_INT)
    session.add_all([grade1, grade2, grade3, grade4])
    session.commit()

    assert session.query(Course).filter_by(name="cascade_course").first() is not None
    assert (
        session.query(TaskGroup).filter(TaskGroup.name.in_(["cascade_group1", "cascade_group2"])).count()
        == TEST_TASK_COUNT
    )
    assert (
        session.query(Task).filter(Task.name.in_(["cascade_task1", "cascade_task2", "cascade_task3"])).count()
        == TEST_TASK_COUNT_LARGE
    )
    assert (
        session.query(UserOnCourse).filter(UserOnCourse.repo_name.in_(["cascade_repo1", "cascade_repo2"])).count()
        == TEST_TASK_COUNT
    )
    assert session.query(Grade).filter_by(score=TEST_DEADLINE_DATA_INT).count() == TEST_GRADE_COUNT

    session.delete(course)
    session.commit()

    assert session.query(Course).filter_by(name="cascade_course").first() is None
    assert session.query(TaskGroup).filter(TaskGroup.name.in_(["cascade_group1", "cascade_group2"])).count() == 0
    assert session.query(Task).filter(Task.name.in_(["cascade_task1", "cascade_task2", "cascade_task3"])).count() == 0
    assert (
        session.query(UserOnCourse).filter(UserOnCourse.repo_name.in_(["cascade_repo1", "cascade_repo2"])).count() == 0
    )
    assert session.query(Grade).filter_by(score=TEST_DEADLINE_DATA_INT).count() == 0

    assert session.query(User).filter(User.username.in_(["cascade_user1", "cascade_user2"])).count() == TEST_TASK_COUNT


def test_cascade_delete_task_group(session):
    course = Course(
        name="cascade_course2",
        registration_secret="secret",
        token="test_token2__",
        gitlab_instance_host="gitlab.inst.org",
    )
    deadline = Deadline(id=TEST_DEADLINE_ID, steps=TEST_DEADLINE_STEPS)
    task_group = TaskGroup(name="cascade_group3", course=course, deadline=deadline)
    task1 = Task(name="cascade_task4", group=task_group)
    task2 = Task(name="cascade_task5", group=task_group)
    session.add_all([course, deadline, task_group, task1, task2])
    session.commit()

    user = User(username="cascade_user3", gitlab_instance_host="gitlab.inst.org")
    user_on_course = UserOnCourse(user=user, course=course, repo_name="cascade_repo3")
    grade1 = Grade(user_on_course=user_on_course, task=task1, score=TEST_GRADE_SCORE_2)
    grade2 = Grade(user_on_course=user_on_course, task=task2, score=TEST_GRADE_SCORE_2)
    session.add_all([user, user_on_course, grade1, grade2])
    session.commit()

    assert session.query(TaskGroup).filter_by(name="cascade_group3").first() is not None
    assert session.query(Task).filter(Task.name.in_(["cascade_task4", "cascade_task5"])).count() == TEST_TASK_COUNT
    assert session.query(Grade).filter_by(score=TEST_GRADE_SCORE_2).count() == TEST_TASK_COUNT
    assert session.query(Deadline).filter_by(id=TEST_DEADLINE_ID).count() == 1

    session.delete(task_group)
    session.commit()

    assert session.query(TaskGroup).filter_by(name="cascade_group3").first() is None
    assert session.query(Task).filter(Task.name.in_(["cascade_task4", "cascade_task5"])).count() == 0
    assert session.query(Grade).filter_by(score=TEST_GRADE_SCORE_2).count() == 0
    assert session.query(Deadline).filter_by(id=TEST_DEADLINE_ID).count() == 0

    retrieved_user = session.query(User).filter_by(username="cascade_user3").first()
    assert retrieved_user is not None
    assert len(retrieved_user.users_on_courses.all()) == 1

    retrieved_course = session.query(Course).filter_by(name="cascade_course2").first()
    assert retrieved_course is not None
    assert len(retrieved_course.users_on_courses.all()) == 1


def test_cascade_delete_user(session):
    user = User(username="cascade_user4", gitlab_instance_host="gitlab.inst.org")
    course = Course(
        name="cascade_course3",
        registration_secret="secret",
        token="test_token3__",
        gitlab_instance_host="gitlab.inst.org",
    )
    user_on_course = UserOnCourse(user=user, course=course, repo_name="cascade_repo4")
    task_group = TaskGroup(name="cascade_group4", course=course)
    task = Task(name="cascade_task6", group=task_group)
    grade = Grade(user_on_course=user_on_course, task=task, score=TEST_GRADE_SCORE_3)
    session.add_all([user, course, user_on_course, task_group, task, grade])
    session.commit()

    assert session.query(User).filter_by(username="cascade_user4").first() is not None
    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo4").first() is not None
    assert session.query(Grade).filter_by(score=TEST_GRADE_SCORE_3).count() == 1

    session.delete(user)
    session.commit()

    assert session.query(User).filter_by(username="cascade_user4").first() is None
    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo4").first() is None
    assert session.query(Grade).filter_by(score=TEST_GRADE_SCORE_3).count() == 0

    assert session.query(Course).filter_by(name="cascade_course3").first() is not None
    assert session.query(TaskGroup).filter_by(name="cascade_group4").first() is not None


def test_cascade_delete_user_on_course(session):
    user = User(username="cascade_user5", gitlab_instance_host="gitlab.inst.org")
    course = Course(
        name="cascade_course4",
        registration_secret="secret",
        token="test_token5",
        gitlab_instance_host="gitlab.inst.org",
    )
    user_on_course = UserOnCourse(user=user, course=course, repo_name="cascade_repo5")
    task_group = TaskGroup(name="cascade_group5", course=course)
    task = Task(name="cascade_task7", group=task_group)
    grade = Grade(user_on_course=user_on_course, task=task, score=TEST_GRADE_SCORE_4)
    session.add_all([user, course, user_on_course, task_group, task, grade])
    session.commit()

    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo5").first() is not None
    assert session.query(Grade).filter_by(score=TEST_GRADE_SCORE_4).count() == 1

    session.delete(user_on_course)
    session.commit()

    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo5").first() is None
    assert session.query(Grade).filter_by(score=TEST_GRADE_SCORE_4).count() == 0

    assert session.query(User).filter_by(username="cascade_user5").first() is not None
    assert session.query(Course).filter_by(name="cascade_course4").first() is not None

    assert session.query(TaskGroup).filter_by(name="cascade_group5").first() is not None
    assert session.query(Task).filter_by(name="cascade_task7").first() is not None


def test_validate_gitlab_instance_host_missing_course():
    validate_result = validate_gitlab_instance_host(None, {}, None)
    assert validate_result is None


def test_custom_dict_type_empty(engine):
    class TestBase(DeclarativeBase):
        pass

    class TestModel(TestBase):
        __tablename__ = "test_model"

        id: Mapped[int] = mapped_column(primary_key=True)
        data: Mapped[Optional[dict[float, datetime]]] = mapped_column(FloatDatetimeDict)

    TestBase.metadata.create_all(engine)

    with Session(engine) as session:
        test_model = TestModel()
        session.add(test_model)
        session.commit()

        retrieved_model = session.query(TestModel).one()

        assert retrieved_model.data is None

    TestBase.metadata.drop_all(engine)

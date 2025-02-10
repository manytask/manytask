from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from manytask.models import (
    Base,
    Course,
    Deadline,
    Grade,
    Task,
    TaskGroup,
    User,
    UserOnCourse,
    validate_gitlab_instance_host,
)

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"


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

    deadline = Deadline(data={"test_key": "test_value"})
    session.add(deadline)
    task_group = TaskGroup(name="group1", deadline=deadline, course=course)
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group1").first()
    assert retrieved.deadline is not None
    assert retrieved.deadline.data["test_key"] == "test_value"


def test_task_group(session):
    course = Course(
        name="course0002", registration_secret="secret", token="test_token2", gitlab_instance_host="gitlab.inst.org"
    )
    session.add(course)
    task_group = TaskGroup(name="group2", course=course)
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group2").first()
    assert retrieved.deadline is None


def test_deadline_data(session, fixed_current_time):
    course = Course(
        name="course0003", registration_secret="secret", token="test_token3", gitlab_instance_host="gitlab.inst.org"
    )
    session.add(course)
    session.commit()

    deadline1 = Deadline(id=1001)
    deadline2 = Deadline(id=1002, data={})
    deadline3 = Deadline(id=1003, data=[])
    deadline4 = Deadline(id=1004, data=12345)
    deadline5 = Deadline(id=1005, data="some_data")
    session.add_all([deadline1, deadline2, deadline3, deadline4, deadline5])
    session.commit()

    assert session.query(Deadline).filter_by(id=1001).one().data == {}
    assert session.query(Deadline).filter_by(id=1002).one().data == {}
    assert session.query(Deadline).filter_by(id=1003).one().data == []
    assert session.query(Deadline).filter_by(id=1004).one().data == 12345
    assert session.query(Deadline).filter_by(id=1005).one().data == "some_data"

    class MyObject:
        def __init__(self, value):
            self.value = value

    deadlines = [
        Deadline(id=1006, data=b"binary_data"),
        Deadline(id=1007, data=MyObject(10)),
        Deadline(id=1008, data={1, 2, 3}),
        Deadline(id=1009, data=fixed_current_time),
    ]

    for deadline in deadlines:
        with pytest.raises(StatementError):
            session.add(deadline)
            session.commit()
        session.rollback()


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

    grade = Grade(user_on_course=user_on_course, task=task, score=77, last_submit_date=fixed_current_time)
    session.add(grade)
    session.commit()

    retrieved_grade = session.query(Grade).first()
    assert retrieved_grade.user_on_course.user.username == "user2"
    assert retrieved_grade.score == 77
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

    assert len(retrieved_task_group.tasks.all()) == 2
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
    assert len(retrieved_group.tasks.all()) == 2
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

    grade1 = Grade(user_on_course=user_on_course1, task=task1, score=12345)
    grade2 = Grade(user_on_course=user_on_course2, task=task1, score=12345)
    grade3 = Grade(user_on_course=user_on_course2, task=task2, score=12345)
    grade4 = Grade(user_on_course=user_on_course2, task=task3, score=12345)
    session.add_all([grade1, grade2, grade3, grade4])
    session.commit()

    assert session.query(Course).filter_by(name="cascade_course").first() is not None
    assert session.query(TaskGroup).filter(TaskGroup.name.in_(["cascade_group1", "cascade_group2"])).count() == 2
    assert session.query(Task).filter(Task.name.in_(["cascade_task1", "cascade_task2", "cascade_task3"])).count() == 3
    assert (
        session.query(UserOnCourse).filter(UserOnCourse.repo_name.in_(["cascade_repo1", "cascade_repo2"])).count() == 2
    )
    assert session.query(Grade).filter_by(score=12345).count() == 4

    session.delete(course)
    session.commit()

    assert session.query(Course).filter_by(name="cascade_course").first() is None
    assert session.query(TaskGroup).filter(TaskGroup.name.in_(["cascade_group1", "cascade_group2"])).count() == 0
    assert session.query(Task).filter(Task.name.in_(["cascade_task1", "cascade_task2", "cascade_task3"])).count() == 0
    assert (
        session.query(UserOnCourse).filter(UserOnCourse.repo_name.in_(["cascade_repo1", "cascade_repo2"])).count() == 0
    )
    assert session.query(Grade).filter_by(score=12345).count() == 0

    assert session.query(User).filter(User.username.in_(["cascade_user1", "cascade_user2"])).count() == 2


def test_cascade_delete_task_group(session):
    course = Course(
        name="cascade_course2",
        registration_secret="secret",
        token="test_token2__",
        gitlab_instance_host="gitlab.inst.org",
    )
    deadline = Deadline(id=12345, data={"test_key": "test_value"})
    task_group = TaskGroup(name="cascade_group3", course=course, deadline=deadline)
    task1 = Task(name="cascade_task4", group=task_group)
    task2 = Task(name="cascade_task5", group=task_group)
    session.add_all([course, deadline, task_group, task1, task2])
    session.commit()

    user = User(username="cascade_user3", gitlab_instance_host="gitlab.inst.org")
    user_on_course = UserOnCourse(user=user, course=course, repo_name="cascade_repo3")
    grade1 = Grade(user_on_course=user_on_course, task=task1, score=123456)
    grade2 = Grade(user_on_course=user_on_course, task=task2, score=123456)
    session.add_all([user, user_on_course, grade1, grade2])
    session.commit()

    assert session.query(TaskGroup).filter_by(name="cascade_group3").first() is not None
    assert session.query(Task).filter(Task.name.in_(["cascade_task4", "cascade_task5"])).count() == 2
    assert session.query(Grade).filter_by(score=123456).count() == 2
    assert session.query(Deadline).filter_by(id=12345).count() == 1

    session.delete(task_group)
    session.commit()

    assert session.query(TaskGroup).filter_by(name="cascade_group3").first() is None
    assert session.query(Task).filter(Task.name.in_(["cascade_task4", "cascade_task5"])).count() == 0
    assert session.query(Grade).filter_by(score=123456).count() == 0
    assert session.query(Deadline).filter_by(id=12345).count() == 0

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
    grade = Grade(user_on_course=user_on_course, task=task, score=1234567)
    session.add_all([user, course, user_on_course, task_group, task, grade])
    session.commit()

    assert session.query(User).filter_by(username="cascade_user4").first() is not None
    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo4").first() is not None
    assert session.query(Grade).filter_by(score=1234567).count() == 1

    session.delete(user)
    session.commit()

    assert session.query(User).filter_by(username="cascade_user4").first() is None
    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo4").first() is None
    assert session.query(Grade).filter_by(score=1234567).count() == 0

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
    grade = Grade(user_on_course=user_on_course, task=task, score=12345678)
    session.add_all([user, course, user_on_course, task_group, task, grade])
    session.commit()

    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo5").first() is not None
    assert session.query(Grade).filter_by(score=12345678).count() == 1

    session.delete(user_on_course)
    session.commit()

    assert session.query(UserOnCourse).filter_by(repo_name="cascade_repo5").first() is None
    assert session.query(Grade).filter_by(score=12345678).count() == 0

    assert session.query(User).filter_by(username="cascade_user5").first() is not None
    assert session.query(Course).filter_by(name="cascade_course4").first() is not None

    assert session.query(TaskGroup).filter_by(name="cascade_group5").first() is not None
    assert session.query(Task).filter_by(name="cascade_task7").first() is not None


def test_validate_gitlab_instance_host_missing_course():
    validate_result = validate_gitlab_instance_host(None, {}, None)
    assert validate_result is None

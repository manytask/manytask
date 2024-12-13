from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from manytask.models import Base, Course, Deadline, Grade, Task, TaskGroup, User, UserOnCourse


@pytest.fixture(scope='module')
def engine():
    return create_engine('sqlite:///:memory:', echo=False)


@pytest.fixture(scope='module')
def tables(engine):
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def session(engine, tables):
    with Session(engine) as session:
        yield session


def test_user_simple(session):
    user = User(username="test_user", gitlab_instance_host='gitlab.inst.org')
    session.add(user)
    session.commit()

    retrieved = session.query(User).filter_by(username="test_user").first()
    assert retrieved is not None
    assert retrieved.username == "test_user"
    # assert retrieved.is_manytask_admin is False


def test_user_unique_username_and_gitlab_instance(session):
    user1 = User(username="unique_user1", gitlab_instance_host='gitlab.inst1.org')
    user2 = User(username="unique_user1", gitlab_instance_host='gitlab.inst2.org')
    user3 = User(username="unique_user2", gitlab_instance_host='gitlab.inst1.org')
    user4 = User(username="unique_user2", gitlab_instance_host='gitlab.inst2.org')
    user5 = User(username="unique_user1", gitlab_instance_host='gitlab.inst1.org')
    session.add_all([user1, user2, user3, user4])
    session.commit()
    session.add(user5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_course(session):
    course = Course(name="test_course", registration_secret="test_secret",
                    gitlab_instance_host='gitlab.inst.org')
    session.add(course)
    session.commit()

    retrieved = session.query(Course).filter_by(name="test_course").first()
    assert retrieved is not None
    assert retrieved.registration_secret == "test_secret"
    # assert retrieved.show_allscores is False
    assert retrieved.gitlab_instance_host == 'gitlab.inst.org'


def test_course_unique_name(session):
    course1 = Course(name="unique_course", registration_secret="secret1",
                     gitlab_instance_host='gitlab.inst.org')
    course2 = Course(name="unique_course", registration_secret="secret2",
                     gitlab_instance_host='gitlab.inst.org')
    session.add(course1)
    session.commit()
    session.add(course2)
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_on_course(session):
    user = User(username="user1", gitlab_instance_host='gitlab.inst.org')
    course = Course(name="course1", registration_secret="secret1",
                    gitlab_instance_host='gitlab.inst.org')
    session.add_all([user, course])
    session.commit()

    user_on_course = UserOnCourse(
        user=user,
        course=course,
        repo_name="user1_repo"
    )
    session.add(user_on_course)
    session.commit()

    retrieved_user = session.query(User).filter_by(username="user1").first()
    assert len(retrieved_user.users_on_courses.all()) == 1
    assert retrieved_user.users_on_courses[0].course.name == "course1"

    retrieved_course = session.query(Course).filter_by(name="course1").first()
    assert len(retrieved_course.users_on_courses.all()) == 1
    assert retrieved_course.users_on_courses[0].user.username == "user1"


def test_user_on_course_unique_ids(session):
    user1 = User(username="user001", gitlab_instance_host='gitlab.inst.org')
    course1 = Course(name="course001", registration_secret="secret001",
                     gitlab_instance_host='gitlab.inst.org')
    user2 = User(username="user002", gitlab_instance_host='gitlab.inst.org')
    course2 = Course(name="course002", registration_secret="secret002",
                     gitlab_instance_host='gitlab.inst.org')

    user_on_course1 = UserOnCourse(
        user=user1,
        course=course1,
        repo_name="user_repo01"
    )
    user_on_course2 = UserOnCourse(
        user=user1,
        course=course2,
        repo_name="user_repo02"
    )
    user_on_course3 = UserOnCourse(
        user=user2,
        course=course1,
        repo_name="user_repo03"
    )
    user_on_course4 = UserOnCourse(
        user=user2,
        course=course2,
        repo_name="user_repo04"
    )
    session.add_all([user_on_course1, user_on_course2, user_on_course3, user_on_course4])
    session.commit()

    user_on_course5 = UserOnCourse(
        user=user1,
        course=course1,
        repo_name="user_repo05"
    )

    session.add(user_on_course5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_deadline(session):
    course = Course(name="course0001", registration_secret="secret",
                    gitlab_instance_host='gitlab.inst.org')
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
    course = Course(name="course0002", registration_secret="secret",
                    gitlab_instance_host='gitlab.inst.org')
    session.add(course)
    task_group = TaskGroup(name="group2", course=course)
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group2").first()
    assert retrieved.deadline is None


def test_task(session):
    course = Course(name="course3", registration_secret="secret3",
                    gitlab_instance_host='gitlab.inst.org')
    task_group = TaskGroup(name="group3", course=course)
    session.add_all([course, task_group])
    session.commit()

    task = Task(name="task1", group=task_group)
    session.add(task)
    session.commit()

    retrieved_task = session.query(Task).filter_by(name="task1").first()
    assert retrieved_task.group.course.name == "course3"
    assert retrieved_task.group.name == "group3"


def test_grade(session):
    user = User(username="user2", gitlab_instance_host='gitlab.inst.org')
    course = Course(name="course4", registration_secret="secret4",
                    gitlab_instance_host='gitlab.inst.org')
    user_on_course = UserOnCourse(
        user=user,
        course=course,
        repo_name='repo_name1'
    )
    task_group = TaskGroup(name="group4", course=course)
    task = Task(name="task2", group=task_group)
    session.add_all([user, course, user_on_course, task_group, task])
    session.commit()

    grade = Grade(
        user_on_course=user_on_course,
        task=task,
        score=77,
        last_submit_date=datetime.now(timezone.utc)
    )
    session.add(grade)
    session.commit()

    retrieved_grade = session.query(Grade).first()
    assert retrieved_grade.user_on_course.user.username == "user2"
    assert retrieved_grade.score == 77


def test_grade_unique_ids(session):
    course = Course(name="course101", registration_secret="secret101",
                    gitlab_instance_host='gitlab.inst.org')
    task_group = TaskGroup(name="group101", course=course)
    user1 = User(username="user101", gitlab_instance_host='gitlab.inst.org')
    user2 = User(username="user102", gitlab_instance_host='gitlab.inst.org')
    user_on_course1 = UserOnCourse(
        user=user1,
        course=course,
        repo_name='repo_name1'
    )
    user_on_course2 = UserOnCourse(
        user=user2,
        course=course,
        repo_name='repo_name1'
    )
    task1 = Task(name="task101", group=task_group)
    task2 = Task(name="task102", group=task_group)
    session.add_all([course, task_group, user1, user2, task1,
                    task2, user_on_course1, user_on_course2])
    session.commit()

    grade1 = Grade(
        user_on_course=user_on_course1,
        task=task1,
        score=11,
        last_submit_date=datetime.now(timezone.utc)
    )
    grade2 = Grade(
        user_on_course=user_on_course1,
        task=task2,
        score=11,
        last_submit_date=datetime.now(timezone.utc)
    )
    grade3 = Grade(
        user_on_course=user_on_course2,
        task=task1,
        score=11,
        last_submit_date=datetime.now(timezone.utc)
    )
    grade4 = Grade(
        user_on_course=user_on_course2,
        task=task2,
        score=11,
        last_submit_date=datetime.now(timezone.utc)
    )

    session.add_all([grade1, grade2, grade3, grade4])
    session.commit()

    grade5 = Grade(
        user_on_course=user_on_course1,
        task=task1,
        score=11,
        last_submit_date=datetime.now(timezone.utc)
    )
    session.add(grade5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_course_tasks(session):
    course = Course(name="course11", registration_secret="secret11",
                    gitlab_instance_host='gitlab.inst.org')
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
    course = Course(name="course12", registration_secret="secret12",
                    gitlab_instance_host='gitlab.inst.org')
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
    course = Course(name="course21", registration_secret="secret",
                    gitlab_instance_host='gitlab.inst.org')
    user = User(username="user21", gitlab_instance_host='another.gitlab.inst.org')
    user_on_course = UserOnCourse(
        user=user,
        course=course,
        repo_name="user21_repo"
    )

    session.add_all([user, course, user_on_course])
    with pytest.raises(ValueError):
        session.commit()

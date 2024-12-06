import pytest
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from manytask.models import User, Course, UserOnCourse, Deadline, TaskGroup, Task, Grade, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


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
    assert retrieved.is_manytask_admin is False


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
    course = Course(name="test_course", registration_secret="test_secret")
    session.add(course)
    session.commit()

    retrieved = session.query(Course).filter_by(name="test_course").first()
    assert retrieved is not None
    assert retrieved.registration_secret == "test_secret"
    assert retrieved.show_allscores is False


def test_course_unique_name(session):
    course1 = Course(name="unique_course", registration_secret="secret1")
    course2 = Course(name="unique_course", registration_secret="secret2")
    session.add(course1)
    session.commit()
    session.add(course2)
    with pytest.raises(IntegrityError):
        session.commit()


def test_user_on_course(session):
    user = User(username="user1", gitlab_instance_host='gitlab.inst.org')
    course = Course(name="course1", registration_secret="secret1")
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
    course1 = Course(name="course001", registration_secret="secret001")
    user2 = User(username="user002", gitlab_instance_host='gitlab.inst.org')
    course2 = Course(name="course002", registration_secret="secret002")

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
    deadline = Deadline(data={"test_key": "test_value"})
    session.add(deadline)
    task_group = TaskGroup(name="group1", deadline=deadline)
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group1").first()
    assert retrieved.deadline is not None
    assert retrieved.deadline.data["test_key"] == "test_value"


def test_task_group(session):
    task_group = TaskGroup(name="group2")
    session.add(task_group)
    session.commit()

    retrieved = session.query(TaskGroup).filter_by(name="group2").first()
    assert retrieved.deadline is None


def test_task(session):
    course = Course(name="course3", registration_secret="secret3")
    task_group = TaskGroup(name="group3")
    session.add_all([course, task_group])
    session.commit()

    task = Task(name="task1", course=course, group=task_group)
    session.add(task)
    session.commit()

    retrieved_task = session.query(Task).filter_by(name="task1").first()
    assert retrieved_task.course.name == "course3"
    assert retrieved_task.group.name == "group3"


def test_grade(session):
    user = User(username="user2", gitlab_instance_host='gitlab.inst.org')
    course = Course(name="course4", registration_secret="secret4")
    task_group = TaskGroup(name="group4")
    task = Task(name="task2", course=course, group=task_group)
    session.add_all([user, course, task_group, task])
    session.commit()

    grade = Grade(
        user=user,
        task=task,
        score=77,
        submit_date=datetime.now(timezone.utc)
    )
    session.add(grade)
    session.commit()

    retrieved_grade = session.query(Grade).first()
    assert retrieved_grade.user.username == "user2"
    assert retrieved_grade.task.name == "task2"
    assert retrieved_grade.score == 77


def test_grade_unique_ids(session):
    task_group = TaskGroup(name="group101")
    course = Course(name="course101", registration_secret="secret101")
    user1 = User(username="user101", gitlab_instance_host='gitlab.inst.org')
    user2 = User(username="user102", gitlab_instance_host='gitlab.inst.org')
    task1 = Task(name="task101", course=course, group=task_group)
    task2 = Task(name="task102", course=course, group=task_group)
    session.add_all([task_group, course, user1, user2, task1, task2])
    session.commit()

    grade1 = Grade(
        user=user1,
        task=task1,
        score=11,
        submit_date=datetime.now(timezone.utc)
    )
    grade2 = Grade(
        user=user1,
        task=task2,
        score=11,
        submit_date=datetime.now(timezone.utc)
    )
    grade3 = Grade(
        user=user2,
        task=task1,
        score=11,
        submit_date=datetime.now(timezone.utc)
    )
    grade4 = Grade(
        user=user2,
        task=task2,
        score=11,
        submit_date=datetime.now(timezone.utc)
    )

    session.add_all([grade1, grade2, grade3, grade4])
    session.commit()

    grade5 = Grade(
        user=user1,
        task=task1,
        score=11,
        submit_date=datetime.now(timezone.utc)
    )
    session.add(grade5)
    with pytest.raises(IntegrityError):
        session.commit()


def test_course_tasks(session):
    course = Course(name="course11", registration_secret="secret11")
    task_group = TaskGroup(name="group11")
    task1 = Task(name="task11_1", group=task_group, course=course)
    task2 = Task(name="task11_2", group=task_group, course=course)
    session.add_all([course, task_group, task1, task2])
    session.commit()

    retrieved_course = session.query(Course).filter_by(name="course11").first()
    assert len(retrieved_course.tasks.all()) == 2
    task_names = [task.name for task in retrieved_course.tasks]
    assert "task11_1" in task_names
    assert "task11_2" in task_names


def test_task_group_tasks(session):
    course = Course(name="course12", registration_secret="secret12")
    task_group = TaskGroup(name="group12")
    task1 = Task(name="task12_1", group=task_group, course=course)
    task2 = Task(name="task12_2", group=task_group, course=course)
    session.add_all([task_group, task1, task2])
    session.commit()

    retrieved_group = session.query(TaskGroup).filter_by(name="group12").first()
    assert len(retrieved_group.tasks.all()) == 2
    task_names = [task.name for task in retrieved_group.tasks]
    assert "task12_1" in task_names
    assert "task12_2" in task_names

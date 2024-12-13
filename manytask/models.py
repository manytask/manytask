from datetime import datetime, timezone
from typing import Iterable, List, Optional

from sqlalchemy import JSON, ForeignKey, UniqueConstraint, event
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import DeclarativeBase, DynamicMapped, Mapped, Session, mapped_column, relationship
from sqlalchemy.sql.functions import func


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    gitlab_instance_host: Mapped[str]
    # is_manytask_admin: Mapped[bool] = mapped_column(default=False) TODO: now it unused in model

    __table_args__ = (
        UniqueConstraint(
            'username',
            'gitlab_instance_host',
            name='_username_gitlab_instance_uc'
        ),
    )

    # relationships
    users_on_courses: DynamicMapped[List['UserOnCourse']] = relationship(
        back_populates='user', lazy='dynamic')

    @classmethod
    def get_or_create(
            cls,
            session: Session,
            username: str,
            gitlab_instance_host: str,
            create_if_not_exist: bool = False
    ) -> 'User':
        user = session.query(cls).filter_by(
            username=username, gitlab_instance_host=gitlab_instance_host).first()

        if user is not None:
            return user
        if not create_if_not_exist:
            raise NoResultFound(f"User with name: {username} and gitlab host: {
                                gitlab_instance_host} not found")

        user = cls(username=username, gitlab_instance_host=gitlab_instance_host)
        session.add(user)
        session.commit()

        return user


class Course(Base):
    __tablename__ = 'courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    gitlab_instance_host: Mapped[str]
    registration_secret: Mapped[str]
    show_allscores: Mapped[bool] = mapped_column(default=False)

    # relationships
    task_groups: DynamicMapped[List['TaskGroup']] = relationship(
        back_populates='course', lazy='dynamic')
    users_on_courses: DynamicMapped[List['UserOnCourse']] = relationship(
        back_populates='course', lazy='dynamic')

    @classmethod
    def update_or_create(
            cls,
            session: Session,
            name: str,
            gitlab_instance_host: str,
            registration_secret: str,
            show_allscores: bool
    ) -> 'Course':
        course = session.query(cls).filter_by(name=name).first()

        if course is not None and course.gitlab_instance_host != gitlab_instance_host:
            raise ValueError("Can't update gitlab_instance_host param on created course")

        if course is None:
            course = cls(
                name=name,
                gitlab_instance_host=gitlab_instance_host,
                registration_secret=registration_secret,
                show_allscores=show_allscores
            )

            session.add(course)
        else:
            course.registration_secret = registration_secret
            course.show_allscores = show_allscores

        session.commit()
        return course

    @classmethod
    def get_by_name(
            cls,
            session: Session,
            course_name: str
    ) -> 'Course':
        course = session.query(cls).filter_by(name=course_name).first()
        if course is None:
            raise NoResultFound(f"Course with name: {course_name} not found")

        return course

    @classmethod
    def get_all_tasks(
        cls,
        session: Session,
        course_name: str
    ) -> Iterable['Task']:
        course = cls.get_by_name(session, course_name)

        tasks = []
        for task_group in course.task_groups.all():
            tasks += list(task_group.tasks.all())

        return tasks

    @classmethod
    def get_all_users(
        cls,
        session: Session,
        course_name: str
    ) -> Iterable[str]:
        course = cls.get_by_name(session, course_name)

        return [user_on_course.user.username for user_on_course in course.users_on_courses.all()]

    @classmethod
    def get_users_on_courses_count(
            cls,
            session: Session,
            course_name: str
    ) -> int:
        course = cls.get_by_name(session, course_name)

        return session.query(func.count(UserOnCourse.id)).filter_by(course_id=course.id).one()[0]


class UserOnCourse(Base):
    __tablename__ = 'users_on_courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    # is_course_admin: Mapped[bool] = mapped_column(default=False) TODO: now it unused in model
    repo_name: Mapped[str]
    join_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='_user_course_uc'),
    )

    # relationships
    user: Mapped['User'] = relationship(back_populates='users_on_courses')
    course: Mapped['Course'] = relationship(back_populates='users_on_courses')
    grades: DynamicMapped[List['Grade']] = relationship(
        back_populates='user_on_course', lazy='dynamic')

    @classmethod
    def get_by_id(
            cls,
            session: Session,
            id: int
    ) -> Optional['UserOnCourse']:
        return session.query(cls).filter_by(id=id).first()

    @classmethod
    def get(
            cls,
            session: Session,
            username: str,
            gitlab_instance_host: str,
            course_name: str,
            repo_name: str
    ) -> Optional['UserOnCourse']:
        pass

    @classmethod
    def get_or_create(
            cls,
            session: Session,
            username: str,
            course_name: str,
            repo_name: str | None = None,
            create_if_not_exist: bool = False
    ) -> Optional['UserOnCourse']:
        if repo_name is None and create_if_not_exist:
            raise TypeError("Arguments repo_name=None and create_if_not_exist=True not valid")

        course = Course.get_by_name(session, course_name)
        user = User.get_or_create(session, username, course.gitlab_instance_host,
                                  create_if_not_exist=create_if_not_exist)

        user_on_course = session.query(cls).filter_by(
            user=user,
            course=course
        ).first()

        if user_on_course is not None:
            return user_on_course
        if not create_if_not_exist:
            raise NoResultFound(f"UserOnCourse with username: {
                                username} and course_name: {course_name} not found")

        user_on_course = UserOnCourse(
            user=user,
            course=course,
            repo_name=repo_name
        )
        session.add(user_on_course)
        session.commit()

        return user_on_course

    @classmethod
    def get_all_grades(
            cls,
            session: Session,
            user_on_course_id: int,
            only_bonus: bool = False
    ) -> Iterable['Grade']:
        user_on_course = cls.get_by_id(session, user_on_course_id)

        if only_bonus:
            # TODO: maybe not correct, need to test this
            return user_on_course.grades.join(Task).filter_by(is_bonus=True).all()

        return user_on_course.grades.all()


@event.listens_for(UserOnCourse, 'before_insert')
def validate_gitlab_instance_host(mapper, connection, target):
    if target.user.gitlab_instance_host != target.course.gitlab_instance_host:
        raise ValueError("Gitlab instances not equal")


class Deadline(Base):
    __tablename__ = 'deadlines'

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[JSON] = mapped_column(type_=JSON, default=dict)

    # relationships
    task_group: Mapped['TaskGroup'] = relationship(back_populates='deadline')


class TaskGroup(Base):
    __tablename__ = 'task_groups'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    deadline_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Deadline.id))

    # relationships
    course: Mapped['Course'] = relationship(back_populates='task_groups')
    deadline: Mapped['Deadline'] = relationship(back_populates='task_group')
    tasks: DynamicMapped[List['Task']] = relationship(back_populates='group', lazy='dynamic')

    @classmethod
    def get_by_name(
            cls,
            session: Session,
            group_name: str
    ) -> Optional['TaskGroup']:
        return session.query(cls).filter_by(name=group_name).first()

    @classmethod
    def update_or_create(
            cls,
            session: Session,
            name: str,
            course_name: str,
            deadline_data: dict
    ) -> 'TaskGroup':
        course = Course.get_by_name(session, course_name)

        task_group = session.query(cls).filter_by(name=name, course=course).first()
        if task_group is None:
            task_group = cls(name=name, course=course)
            session.add(task_group)

        if task_group.deadline is None:
            deadline = Deadline()
            session.add(deadline)
            task_group.deadline = deadline

        task_group.deadline.data = deadline_data
        session.commit()

        return task_group


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    group_id: Mapped[int] = mapped_column(ForeignKey(TaskGroup.id))
    is_bonus: Mapped[bool] = mapped_column(default=False)

    # relationships
    group: Mapped['TaskGroup'] = relationship(back_populates='tasks')
    grades: DynamicMapped[List['Grade']] = relationship(back_populates='task', lazy='dynamic')

    @classmethod
    def get_submits_count(
            cls,
            session: Session,
            task_id: int
    ) -> int:
        return session.query(func.count(Grade.id)).filter(Grade.task_id == task_id and Grade.score > 0).one()[0]

    @classmethod
    def get_by_name_and_course(
            cls,
            session: Session,
            name: str,
            course_name: str
    ) -> Optional['Task']:
        course = Course.get_by_name(session, course_name)

        task = session.query(cls).filter_by(name=name).join(
            TaskGroup).filter_by(course=course).first()
        return task

    @classmethod
    def update_or_create(
        cls,
        session: Session,
        name: str,
        is_bonus: bool,
        group_name: str,
        course_name: str,
        deadline_data: dict
    ) -> 'Task':
        task_group = TaskGroup.update_or_create(session, group_name, course_name, deadline_data)

        task = session.query(cls).filter_by(name=name, group=task_group).first()
        if task is None:
            task = cls(name=name, group=task_group)
            session.add(task)

        task.is_bonus = is_bonus
        session.commit()

        return task


class Grade(Base):
    __tablename__ = 'grades'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_on_course_id: Mapped[int] = mapped_column(ForeignKey(UserOnCourse.id))
    task_id: Mapped[int] = mapped_column(ForeignKey(Task.id))
    score: Mapped[int] = mapped_column(default=0)
    last_submit_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_on_course_id', 'task_id', name='_user_on_course_task_uc'),
    )

    # relationships
    user_on_course: Mapped['UserOnCourse'] = relationship(back_populates='grades')
    task: Mapped['Task'] = relationship(back_populates='grades')

    @classmethod
    def get_by_id(
            cls,
            session: Session,
            id: int
    ) -> Optional['Grade']:
        grade = session.query(cls).filter_by(id=id).first()
        return grade

    @classmethod
    def get_or_create(
            cls,
            session: Session,
            user_on_course_id: int,
            task_name: str,
            course_name: str
    ) -> 'Grade':
        task = Task.get_by_name_and_course(session, task_name, course_name)
        if task is None:
            raise NoResultFound(f"Task with name: {task_name} in course with name: {
                                course_name} not found")

        user_on_course = UserOnCourse.get_by_id(session, user_on_course_id)
        if user_on_course is None:
            raise NoResultFound(f"UserOnCourse with id: {user_on_course_id} not found")

        grade = session.query(cls).filter_by(user_on_course=user_on_course, task=task).first()
        if grade is None:
            grade = cls(user_on_course=user_on_course, task=task)

            session.add(grade)
            session.commit()

        return grade

    @classmethod
    def update(
            cls,
            session: Session,
            grade_id: int,
            new_score: int
    ) -> 'Grade':
        grade = cls.get_by_id(session, grade_id)
        if grade is None:
            raise NoResultFound(f"Grade with id: {grade_id} not found")

        grade.score = new_score
        grade.last_submit_date = datetime.now(timezone.utc)

        session.commit()
        return grade

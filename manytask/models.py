import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, UniqueConstraint, event, func
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, DynamicMapped, Mapped, Mapper, Session, mapped_column, relationship


logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    gitlab_instance_host: Mapped[str]

    __table_args__ = (
        UniqueConstraint(
            'username',
            'gitlab_instance_host',
            name='_username_gitlab_instance_uc'
        ),
    )

    # relationships
    users_on_courses: DynamicMapped['UserOnCourse'] = relationship(
        back_populates='user',
        cascade='all, delete-orphan'
    )


class Course(Base):
    __tablename__ = 'courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    gitlab_instance_host: Mapped[str]
    registration_secret: Mapped[str]
    show_allscores: Mapped[bool] = mapped_column(default=False)

    # relationships
    task_groups: DynamicMapped['TaskGroup'] = relationship(
        back_populates='course',
        cascade='all, delete-orphan'
    )
    users_on_courses: DynamicMapped['UserOnCourse'] = relationship(
        back_populates='course',
        cascade='all, delete-orphan'
    )


class UserOnCourse(Base):
    __tablename__ = 'users_on_courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    repo_name: Mapped[str]
    join_date: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='_user_course_uc'),
    )

    # relationships
    user: Mapped['User'] = relationship(back_populates='users_on_courses')
    course: Mapped['Course'] = relationship(back_populates='users_on_courses')
    grades: DynamicMapped['Grade'] = relationship(
        back_populates='user_on_course',
        cascade='all, delete-orphan'
    )


@event.listens_for(UserOnCourse, 'before_insert')
def validate_gitlab_instance_host(mapper: Mapper[UserOnCourse], connection: Connection, target: UserOnCourse) -> None:
    session = Session(bind=connection)

    try:
        if target.user:
            user = target.user
        else:
            user = session.query(User).filter_by(id=target.user_id).one()

        if target.course:
            course = target.course
        else:
            course = session.query(Course).filter_by(id=target.course_id).one()
    except Exception as e:  # TODO: fix swallowing exception
        logger.warning(
            f"Swallowing exception in 'before_insert' event in UserOnCourse model: {repr(e)}")
        return

    if user.gitlab_instance_host != course.gitlab_instance_host:
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
    deadline: Mapped['Deadline'] = relationship(
        back_populates='task_group',
        cascade='all, delete-orphan',
        single_parent=True
    )
    tasks: DynamicMapped['Task'] = relationship(
        back_populates='group',
        cascade='all, delete-orphan'
    )


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    group_id: Mapped[int] = mapped_column(ForeignKey(TaskGroup.id))
    is_bonus: Mapped[bool] = mapped_column(default=False)

    # relationships
    group: Mapped['TaskGroup'] = relationship(back_populates='tasks')
    grades: DynamicMapped['Grade'] = relationship(
        back_populates='task',
        cascade='all, delete-orphan'
    )


class Grade(Base):
    __tablename__ = 'grades'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_on_course_id: Mapped[int] = mapped_column(ForeignKey(UserOnCourse.id))
    task_id: Mapped[int] = mapped_column(ForeignKey(Task.id))
    score: Mapped[int] = mapped_column(default=0)
    last_submit_date: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        UniqueConstraint('user_on_course_id', 'task_id', name='_user_on_course_task_uc'),
    )

    # relationships
    user_on_course: Mapped['UserOnCourse'] = relationship(back_populates='grades')
    task: Mapped['Task'] = relationship(back_populates='grades')

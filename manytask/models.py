from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from sqlalchemy import ForeignKey, JSON, UniqueConstraint
from typing import Optional, List
from datetime import datetime, timezone


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    gitlab_instance_host: Mapped[str] = mapped_column(default='gitlab.manytask.org')
    is_manytask_admin: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        UniqueConstraint('username', 'gitlab_instance_host', name='_username_gitlab_instance_uc'),
    )

    # relationships
    users_on_courses: Mapped[List['UserOnCourse']] = relationship(back_populates='user')
    grades: Mapped[List['Grade']] = relationship(back_populates='user')


class Course(Base):
    __tablename__ = 'courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    registration_secret: Mapped[str]
    show_allscores: Mapped[bool] = mapped_column(default=False)

    # relationships
    tasks: Mapped[List['Task']] = relationship(back_populates='course')
    users_on_courses: Mapped[List['UserOnCourse']] = relationship(back_populates='course')


class UserOnCourse(Base):
    __tablename__ = 'users_on_courses'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    is_course_admin: Mapped[bool] = mapped_column(default=False)
    repo_name: Mapped[str]
    join_date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='_user_course_uc'),
    )

    # relationships
    user: Mapped['User'] = relationship(back_populates='users_on_courses')
    course: Mapped['Course'] = relationship(back_populates='users_on_courses')


class Deadline(Base):
    __tablename__ = 'deadlines'

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[JSON] = mapped_column(type_=JSON)

    # relationships
    task_group: Mapped['TaskGroup'] = relationship(back_populates='deadline')


class TaskGroup(Base):
    __tablename__ = 'task_groups'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    deadline_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Deadline.id))

    # relationships
    deadline: Mapped['Deadline'] = relationship(back_populates='task_group')
    tasks: Mapped[List['Task']] = relationship(back_populates='group')


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    group_id: Mapped[int] = mapped_column(ForeignKey(TaskGroup.id))

    # relationships
    course: Mapped['Course'] = relationship(back_populates='tasks')
    group: Mapped['TaskGroup'] = relationship(back_populates='tasks')
    grades: Mapped[List['Grade']] = relationship(back_populates='task')


class Grade(Base):
    __tablename__ = 'grades'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    task_id: Mapped[int] = mapped_column(ForeignKey(Task.id))
    score: Mapped[int]
    submit_date: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint('user_id', 'task_id', name='_user_task_uc'),
    )

    # relationships
    user: Mapped['User'] = relationship(back_populates='grades')
    task: Mapped['Task'] = relationship(back_populates='grades')


# Is it needed?
#
# class ApiRequest(Base):
#     __tablename__ = 'api_requests'

#     id: Mapped[int] = mapped_column(primary_key=True)
#     course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
#     date: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
#     # type: enum...
#     data: Mapped[JSON] = mapped_column(type_=JSON)

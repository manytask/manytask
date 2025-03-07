import logging
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, ForeignKey, MetaData, UniqueConstraint, event, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.engine import Connection
from sqlalchemy.orm import DeclarativeBase, DynamicMapped, Mapped, Mapper, Session, mapped_column, relationship

logger = logging.getLogger(__name__)

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    gitlab_instance_host: Mapped[str]

    __table_args__ = (UniqueConstraint("username", "gitlab_instance_host", name="_username_gitlab_instance_uc"),)

    # relationships
    users_on_courses: DynamicMapped["UserOnCourse"] = relationship(back_populates="user", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    unique_course_name: Mapped[str]
    gitlab_instance_host: Mapped[str]
    registration_secret: Mapped[str]
    token: Mapped[str] = mapped_column(unique=True)
    show_allscores: Mapped[bool] = mapped_column(default=False)
    gitlab_admin_token: Mapped[str]
    gitlab_course_group: Mapped[str]
    gitlab_course_public_repo: Mapped[str]
    gitlab_course_students_group: Mapped[str]
    gitlab_default_branch: Mapped[str]
    gitlab_client_id: Mapped[str]
    gitlab_client_secret: Mapped[str]

    __table_args__ = (
        UniqueConstraint("name", name="uq_courses_name"),
        UniqueConstraint("token", name="uq_courses_token"),
    )

    # relationships
    task_groups: DynamicMapped["TaskGroup"] = relationship(back_populates="course", cascade="all, delete-orphan")
    users_on_courses: DynamicMapped["UserOnCourse"] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )


class Role(str, Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class UserOnCourse(Base):
    __tablename__ = "users_on_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    repo_name: Mapped[str]
    join_date: Mapped[datetime] = mapped_column(server_default=func.now())
    role: Mapped[Role] = mapped_column(
        SQLEnum("admin", "teacher", "student", name="role", create_constraint=True, validate_strings=True),
        default=Role.STUDENT,
    )
    is_course_admin: Mapped[bool] = mapped_column(default=False)  # Keep for backward compatibility

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="_user_course_uc"),)

    # relationships
    user: Mapped["User"] = relationship(back_populates="users_on_courses")
    course: Mapped["Course"] = relationship(back_populates="users_on_courses")
    grades: DynamicMapped["Grade"] = relationship(back_populates="user_on_course", cascade="all, delete-orphan")


@event.listens_for(UserOnCourse, "before_insert")
def validate_gitlab_instance_host(mapper: Mapper[UserOnCourse], connection: Connection, target: UserOnCourse) -> None:
    session = Session(bind=connection)

    try:
        if target.user:
            user = target.user
        else:  # target missing user if we gave user_id or nothing
            user = session.query(User).filter_by(id=target.user_id).one()

        if target.course:
            course = target.course
        else:  # target missing course if we gave course_id or nothing
            course = session.query(Course).filter_by(id=target.course_id).one()
    except Exception as e:  # TODO: fix swallowing exception
        logger.warning(f"Swallowing exception in 'before_insert' event in UserOnCourse model: {repr(e)}")
        return

    if user.gitlab_instance_host != course.gitlab_instance_host:
        raise ValueError("Gitlab instances not equal")


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    data: Mapped[JSON] = mapped_column(type_=JSON, default=dict)

    # relationships
    task_group: Mapped["TaskGroup"] = relationship(back_populates="deadline")


class TaskGroup(Base):
    __tablename__ = "task_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    deadline_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Deadline.id))
    # special flag for task groups
    is_special: Mapped[bool] = mapped_column(default=False)

    # relationships
    course: Mapped["Course"] = relationship(back_populates="task_groups")
    deadline: Mapped["Deadline"] = relationship(
        back_populates="task_group", cascade="all, delete-orphan", single_parent=True
    )
    tasks: DynamicMapped["Task"] = relationship(back_populates="group", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    group_id: Mapped[int] = mapped_column(ForeignKey(TaskGroup.id))
    is_bonus: Mapped[bool] = mapped_column(default=False)
    # special flag for tasks
    is_special: Mapped[bool] = mapped_column(default=False)
    score: Mapped[int] = mapped_column(default=100)

    # relationships
    group: Mapped["TaskGroup"] = relationship(back_populates="tasks")
    grades: DynamicMapped["Grade"] = relationship(back_populates="task", cascade="all, delete-orphan")


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_on_course_id: Mapped[int] = mapped_column(ForeignKey(UserOnCourse.id))
    task_id: Mapped[int] = mapped_column(ForeignKey(Task.id))
    score: Mapped[int] = mapped_column(default=0)
    last_submit_date: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("user_on_course_id", "task_id", name="_user_on_course_task_uc"),)

    # relationships
    user_on_course: Mapped["UserOnCourse"] = relationship(back_populates="grades")
    task: Mapped["Task"] = relationship(back_populates="grades")

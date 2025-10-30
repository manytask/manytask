import enum
import logging
import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, MetaData, UniqueConstraint, func
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, DynamicMapped, Mapped, mapped_column, relationship, validates
from sqlalchemy.types import TypeDecorator

from .course import Course as AppCourse
from .course import CourseConfig as AppCourseConfig
from .course import CourseStatus, ManytaskDeadlinesType

logger = logging.getLogger(__name__)

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _validate_gitlab_slug(slug: str) -> str:
    # https://docs.gitlab.com/user/reserved_names/#:~:text=project%20or%20group-,slugs,-%3A
    if len(slug) == 0:
        raise ValueError("Slug cannot be empty")
    if not slug[0].isalnum() or not slug[-1].isalnum():
        raise ValueError(f"Slug must start and end with a letter (a-zA-Z) or digit (0-9). Got: {slug}")
    if re.search(r"[._-]{2,}", slug):
        raise ValueError(f"Slug must not contain consecutive special characters. Got: {slug}")
    if slug.endswith(".git") or slug.endswith(".atom"):
        raise ValueError(f"Slug cannot end in .git or .atom. Got: {slug}")
    if not re.match(r"^[a-zA-Z0-9._-]*$", slug):
        raise ValueError(
            f"Slug must contain only letters (a-zA-Z), digits (0-9), underscores (_), dots (.), or dashes (-). "
            f"Got: {slug}"
        )
    return slug


class UserOnNamespaceRole(enum.Enum):
    NAMESPACE_ADMIN = "namespace_admin"
    PROGRAM_MANAGER = "program_manager"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


class FloatDatetimeDict(TypeDecorator[Optional[dict[float, datetime]]]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Optional[dict[float, datetime]], dialect: Dialect) -> Optional[dict[str, str]]:
        if value is None:
            return None

        if not isinstance(value, dict):
            raise TypeError(f"value must be a dict, not {type(value)}")

        result = {}
        for k, v in value.items():
            if not isinstance(k, float):
                raise TypeError(f"Key {k} must be a float, not {type(k)}")
            if not isinstance(v, datetime):
                raise TypeError(f"Value {v} must be a datetime, not {type(v)}")
            if v.tzinfo is None:  # Check that datetime has timezone information
                raise TypeError(f"Value {v} for key {k} must have timezone information")

            result[str(k)] = v.isoformat()

        return result

    def process_result_value(
        self, value: Optional[dict[str, str]], dialect: Dialect
    ) -> Optional[dict[float, datetime]]:
        if value is None:
            return None

        result = {}
        for k, v in value.items():
            float_key = float(k)
            datetime_val = datetime.fromisoformat(v)
            result[float_key] = datetime_val

        return result


class StrStrDict(TypeDecorator[Optional[dict[str, str]]]):
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Optional[dict[str, str]], dialect: Dialect) -> Optional[dict[str, str]]:
        if value is None:
            return None

        if not isinstance(value, dict):
            raise TypeError(f"value must be a dict, not {type(value)}")

        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"Key {k} must be a str, not {type(k)}")
            if not isinstance(v, str):
                raise TypeError(f"Value {v} must be a str, not {type(v)}")

        return value

    def process_result_value(self, value: Optional[dict[str, str]], dialect: Dialect) -> Optional[dict[str, str]]:
        return value


class StrIntFloatDict(TypeDecorator[Optional[dict[str, int | float]]]):
    impl = JSON
    cache_ok = True

    def process_bind_param(
        self, value: Optional[dict[str, int | float]], dialect: Dialect
    ) -> Optional[dict[str, int | float]]:
        if value is None:
            return None

        if not isinstance(value, dict):
            raise TypeError(f"value must be a dict, not {type(value)}")

        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"Key {k} must be a str, not {type(k)}")
            if not isinstance(v, int) and not isinstance(v, float):
                raise TypeError(f"Value {v} must be a str, not {type(v)}")

        return value

    def process_result_value(
        self, value: Optional[dict[str, int | float]], dialect: Dialect
    ) -> Optional[dict[str, int | float]]:
        return value


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    rms_id: Mapped[int] = mapped_column(unique=True)
    is_instance_admin: Mapped[bool] = mapped_column(default=False, server_default="false")

    # relationships
    users_on_courses: DynamicMapped["UserOnCourse"] = relationship(back_populates="user", cascade="all, delete-orphan")
    users_on_namespaces: DynamicMapped["UserOnNamespace"] = relationship(
        back_populates="user", foreign_keys="UserOnNamespace.user_id", cascade="all, delete-orphan"
    )
    created_namespaces: DynamicMapped["Namespace"] = relationship(back_populates="created_by")
    assigned_users_on_namespaces: DynamicMapped["UserOnNamespace"] = relationship(
        back_populates="assigned_by", foreign_keys="UserOnNamespace.assigned_by_id"
    )


class Namespace(Base):
    __tablename__ = "namespaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    slug: Mapped[str] = mapped_column(unique=True)
    gitlab_group_id: Mapped[int] = mapped_column(unique=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey(User.id))

    # relationships
    created_by: Mapped["User"] = relationship(back_populates="created_namespaces")
    users_on_namespaces: DynamicMapped["UserOnNamespace"] = relationship(
        back_populates="namespace", cascade="all, delete-orphan"
    )
    courses: DynamicMapped["Course"] = relationship(back_populates="namespace", cascade="all, delete-orphan")

    @validates("slug")
    def validate_slug(self, key: str, slug: Optional[str]) -> Optional[str]:
        if slug is None:
            return None
        return _validate_gitlab_slug(slug)


class UserOnNamespace(Base):
    __tablename__ = "users_on_namespaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    namespace_id: Mapped[int] = mapped_column(ForeignKey(Namespace.id))
    role: Mapped[UserOnNamespaceRole] = mapped_column(
        Enum(UserOnNamespaceRole, name="user_on_namespace_role", native_enum=False),
    )
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey(User.id))

    __table_args__ = (UniqueConstraint("user_id", "namespace_id", name="_user_namespace_uc"),)

    # relationships
    user: Mapped["User"] = relationship(back_populates="users_on_namespaces", foreign_keys=[user_id])
    namespace: Mapped["Namespace"] = relationship(back_populates="users_on_namespaces")
    assigned_by: Mapped["User"] = relationship(
        back_populates="assigned_users_on_namespaces", foreign_keys=[assigned_by_id]
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    namespace_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Namespace.id))
    name: Mapped[str] = mapped_column(unique=True)
    registration_secret: Mapped[str]
    token: Mapped[str] = mapped_column(unique=True)
    show_allscores: Mapped[bool] = mapped_column(default=False)
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus, name="course_status", native_enum=False),
        default=CourseStatus.CREATED,
        server_default="CREATED",
    )

    # gitlab parameters
    gitlab_course_group: Mapped[str]
    gitlab_course_public_repo: Mapped[str]
    gitlab_course_students_group: Mapped[str]
    gitlab_default_branch: Mapped[str]

    # ui parameters
    task_url_template: Mapped[str]
    links: Mapped[dict[str, str]] = mapped_column(StrStrDict, server_default="{}", default=dict)

    # deadlines parameters
    timezone: Mapped[str] = mapped_column(default="UTC", server_default="UTC")
    max_submissions: Mapped[Optional[int]]
    submission_penalty: Mapped[float] = mapped_column(default=0, server_default="0")
    deadlines_type: Mapped[ManytaskDeadlinesType] = mapped_column(
        Enum(ManytaskDeadlinesType, name="deadlines_type", native_enum=False),
        default=ManytaskDeadlinesType.HARD,
        server_default="HARD",
    )

    __table_args__ = (
        UniqueConstraint("name", name="uq_courses_name"),
        UniqueConstraint("token", name="uq_courses_token"),
    )

    # relationships
    namespace: Mapped[Optional["Namespace"]] = relationship(back_populates="courses")
    task_groups: DynamicMapped["TaskGroup"] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="TaskGroup.position"
    )
    users_on_courses: DynamicMapped["UserOnCourse"] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    course_grades: DynamicMapped["ComplexFormula"] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="ComplexFormula.grade"
    )

    def to_app_course(self) -> AppCourse:
        return AppCourse(
            AppCourseConfig(
                course_name=self.name,
                gitlab_course_group=self.gitlab_course_group,
                gitlab_course_public_repo=self.gitlab_course_public_repo,
                gitlab_course_students_group=self.gitlab_course_students_group,
                gitlab_default_branch=self.gitlab_default_branch,
                registration_secret=self.registration_secret,
                token=self.token,
                show_allscores=self.show_allscores,
                status=self.status,
                task_url_template=self.task_url_template,
                links=self.links,
                deadlines_type=self.deadlines_type,
            )
        )


class UserOnCourse(Base):
    __tablename__ = "users_on_courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    join_date: Mapped[datetime] = mapped_column(server_default=func.now())
    is_course_admin: Mapped[bool] = mapped_column(default=False)
    comment: Mapped[Optional[str]] = mapped_column(default=None)

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="_user_course_uc"),)

    # relationships
    user: Mapped["User"] = relationship(back_populates="users_on_courses")
    course: Mapped["Course"] = relationship(back_populates="users_on_courses")
    grades: DynamicMapped["Grade"] = relationship(back_populates="user_on_course", cascade="all, delete-orphan")


class Deadline(Base):
    __tablename__ = "deadlines"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="2000-01-01 00:00:00+00:00")
    steps: Mapped[dict[float, datetime]] = mapped_column(FloatDatetimeDict, server_default="{}", default=dict)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default="3000-01-01 00:00:00+00:00")

    # relationships
    task_group: Mapped["TaskGroup"] = relationship(back_populates="deadline")


class TaskGroup(Base):
    __tablename__ = "task_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))
    deadline_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Deadline.id))
    enabled: Mapped[bool] = mapped_column(server_default="true", default=True)
    position: Mapped[int] = mapped_column(server_default="0", default=0)  # order number

    # relationships
    course: Mapped["Course"] = relationship(back_populates="task_groups")
    deadline: Mapped["Deadline"] = relationship(
        back_populates="task_group", cascade="all, delete-orphan", single_parent=True
    )
    tasks: Mapped[List["Task"]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Task.position"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    group_id: Mapped[int] = mapped_column(ForeignKey(TaskGroup.id))
    score: Mapped[int] = mapped_column(server_default="0", default=0)
    min_score: Mapped[int] = mapped_column(server_default="0", default=0)
    is_bonus: Mapped[bool] = mapped_column(default=False)
    is_large: Mapped[bool] = mapped_column(server_default="false", default=False)
    is_special: Mapped[bool] = mapped_column(server_default="false", default=False)
    enabled: Mapped[bool] = mapped_column(server_default="true", default=True)
    url: Mapped[Optional[str]]
    position: Mapped[int] = mapped_column(server_default="0", default=0)  # order number

    # relationships
    group: Mapped["TaskGroup"] = relationship(back_populates="tasks")
    grades: Mapped[List["Grade"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_on_course_id: Mapped[int] = mapped_column(ForeignKey(UserOnCourse.id))
    task_id: Mapped[int] = mapped_column(ForeignKey(Task.id))
    score: Mapped[int] = mapped_column(default=0)
    is_solved: Mapped[bool] = mapped_column(default=False, server_default="false")
    last_submit_date: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (UniqueConstraint("user_on_course_id", "task_id", name="_user_on_course_task_uc"),)

    # relationships
    user_on_course: Mapped["UserOnCourse"] = relationship(back_populates="grades")
    task: Mapped["Task"] = relationship(back_populates="grades")


class ComplexFormula(Base):
    __tablename__ = "complex_formulas"

    id: Mapped[int] = mapped_column(primary_key=True)
    grade: Mapped[int] = mapped_column(default=0, server_default="0")
    course_id: Mapped[int] = mapped_column(ForeignKey(Course.id))

    # relationships
    primary_formulas: DynamicMapped["PrimaryFormula"] = relationship(
        back_populates="complex_formula", cascade="all, delete-orphan"
    )
    course: Mapped["Course"] = relationship(back_populates="course_grades")


class PrimaryFormula(Base):
    __tablename__ = "primary_formulas"

    id: Mapped[int] = mapped_column(primary_key=True)
    complex_id: Mapped[int] = mapped_column(ForeignKey(ComplexFormula.id))
    primary_formula: Mapped[dict[str, int | float]] = mapped_column(StrIntFloatDict, server_default="{}", default=dict)

    # relationships
    complex_formula: Mapped["ComplexFormula"] = relationship(back_populates="primary_formulas")

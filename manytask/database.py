import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Type, TypeVar, cast
from zoneinfo import ZoneInfo

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from psycopg2.errors import DuplicateColumn, DuplicateTable, UniqueViolation
from pydantic import AnyUrl
from sqlalchemy import Row, Select, and_, create_engine, or_, select
from sqlalchemy.exc import IntegrityError, NoResultFound, ProgrammingError
from sqlalchemy.orm import Session, joinedload, selectinload, sessionmaker
from sqlalchemy.sql.functions import coalesce, func

from . import models
from .abstract import StorageApi, StoredUser
from .config import (
    ManytaskConfig,
    ManytaskDeadlinesConfig,
    ManytaskFinalGradeConfig,
    ManytaskGroupConfig,
    ManytaskTaskConfig,
)
from .course import Course as AppCourse
from .course import CourseConfig as AppCourseConfig
from .course import CourseStatus
from .models import (
    ROLE_NAMESPACE_ADMIN,
    ROLE_PROGRAM_MANAGER,
    Course,
    Deadline,
    Grade,
    Task,
    TaskGroup,
    User,
    UserOnCourse,
)

ModelType = TypeVar("ModelType", bound=models.Base)

logger = logging.getLogger(__name__)


class TaskDisabledError(Exception):
    pass


@dataclass
class DatabaseConfig:
    """Configuration for Database connection and settings."""

    database_url: str
    instance_admin_username: str
    apply_migrations: bool = False
    session_factory: Optional[Callable[[], Session]] = None


class DataBaseApi(StorageApi):
    """Class for interacting with a database with the StorageApi functionality"""

    DEFAULT_ALEMBIC_PATH = Path(__file__).parent / "alembic.ini"

    def __init__(
        self,
        config: DatabaseConfig,
    ):
        """Initialize Database connection with configuration.

        :param config: DatabaseConfig instance containing all necessary settings
        """
        self.database_url = config.database_url
        self.apply_migrations = config.apply_migrations

        self.engine = create_engine(self.database_url, echo=False)

        if config.session_factory is None:
            self._session_create: Callable[[], Session] = sessionmaker(bind=self.engine)
        else:
            self._session_create = config.session_factory

        if self._check_pending_migrations(self.database_url):
            if self.apply_migrations:
                self._apply_migrations(self.database_url)
            else:
                logger.error("There are pending migrations that have not been applied")

        # Create the zero-instance admin user if it does not exist
        with self._session_create() as session:
            self._update_or_create(
                session,
                models.User,
                username=config.instance_admin_username,
                defaults={"is_instance_admin": True},
                create_defaults={"first_name": "Instance", "last_name": "Admin", "rms_id": -1},
            )
            session.commit()

    def get_scores(
        self,
        course_name: str,
        username: str,
    ) -> dict[str, int]:
        """Method for getting all user scores

        :param course_name: course name
        :param username: student username

        :return: dict with the names of tasks and their scores
        """

        with self._session_create() as session:
            grades = self._get_scores(session, course_name, username, enabled=True, started=True, only_bonus=False)

            if grades is None:
                return {}

            scores: dict[str, int] = {}
            for grade in grades:
                scores[grade.task.name] = grade.score

        return scores

    def get_bonus_score(
        self,
        course_name: str,
        username: str,
    ) -> int:
        """Method for getting user's total bonus score

        :param course_name: course name
        :param username: student username

        :return: user's total bonus score
        """

        with self._session_create() as session:
            grades = self._get_scores(session, course_name, username, enabled=True, started=True, only_bonus=True)

        if grades is None:
            return 0

        return sum([grade.score for grade in grades])

    def get_stored_user_by_username(
        self,
        username: str,
    ) -> StoredUser:
        """Method for getting user's stored data

        :param course_name: course name
        :param username: user name

        :return: created or received StoredUser object
        """

        with self._session_create() as session:
            user = self._get(
                session,
                models.User,
                username=username,
            )

            return StoredUser(
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                rms_id=user.rms_id,
                instance_admin=user.is_instance_admin,
            )

    def get_stored_user_by_rms_id(
        self,
        rms_id: int,
    ) -> StoredUser | None:
        """Method for getting user's stored data
        :param rms_id: gitlab user id
        :return: StoredUser object if exist else None
        """

        with self._session_create() as session:
            try:
                user = self._get(
                    session,
                    models.User,
                    rms_id=rms_id,
                )

                return StoredUser(
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    rms_id=user.rms_id,
                    instance_admin=user.is_instance_admin,
                )

            except NoResultFound:
                return None

    def get_stored_user_by_id(
        self,
        user_id: int,
    ) -> StoredUser | None:
        """Method for getting user's stored data by database ID
        :param user_id: Database user ID
        :return: StoredUser object if exist else None
        """

        with self._session_create() as session:
            try:
                user = self._get(
                    session,
                    models.User,
                    id=user_id,
                )

                return StoredUser(
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    rms_id=user.rms_id,
                    instance_admin=user.is_instance_admin,
                )

            except NoResultFound:
                return None

    def check_if_instance_admin(
        self,
        username: str,
    ) -> bool:
        """Method for checking user's admin status

        :param username: user name

        :return: if the user is an admin on any course
        """
        logger.debug("Checking instance admin status for user '%s'", username)

        with self._session_create() as session:
            try:
                user = self._get(session, models.User, username=username)
                is_admin = user.is_instance_admin
                logger.info("User '%s' instance admin status: %s", username, is_admin)
                return is_admin
            except NoResultFound as e:
                logger.info("No user found with username '%s' when checking admin status: %s", username, e)
                return False

    def check_if_course_admin(
        self,
        course_name: str,
        username: str,
    ) -> bool:
        """Method for checking user's admin status

        :param course_name: course name
        :param username: user name

        :return: cif the user is an admin on the course
        """

        with self._session_create() as session:
            try:
                user = self._get(
                    session,
                    models.User,
                    username=username,
                )
                if user.is_instance_admin:
                    return True

                course = self._get(session, models.Course, name=course_name)
                user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
                return user_on_course.is_course_admin
            except NoResultFound as e:
                logger.info("No user found with username '%s' when checking admin status: %s", username, e)
                return False

    def check_if_program_manager(
        self,
        course_name: str,
        username: str,
    ) -> bool:
        with self._session_create() as session:
            try:
                user = self._get(session, models.User, username=username)
                course = self._get(session, models.Course, name=course_name)

                if course.namespace_id is None:
                    return False

                user_on_namespace = self._get(
                    session,
                    models.UserOnNamespace,
                    user_id=user.id,
                    namespace_id=course.namespace_id,
                )
                return user_on_namespace.role == models.UserOnNamespaceRole.PROGRAM_MANAGER
            except NoResultFound:
                return False

    def sync_user_on_course(self, course_name: str, username: str, course_admin: bool) -> None:
        """Method for sync user's gitlab and stored data

        :param course_name: course name
        :param username: user name

        :return: created or updated StoredUser object
        """

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
            user_on_course = self._get_or_create_user_on_course(session, username, course)
            user_on_course.is_course_admin = user_on_course.is_course_admin or course_admin

            session.commit()

    def get_all_scores_with_names(self, course_name: str) -> dict[str, tuple[dict[str, int], tuple[str, str]]]:
        """Get all users' scores with names for the given course.

        Excludes users with PROGRAM_MANAGER role in the course's namespace.
        """

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
            namespace_id = course.namespace_id

            program_managers_subquery = None
            if namespace_id is not None:
                program_managers_subquery = select(models.UserOnNamespace.user_id).where(
                    models.UserOnNamespace.namespace_id == namespace_id,
                    models.UserOnNamespace.role == models.UserOnNamespaceRole.PROGRAM_MANAGER,
                )

            statement = (
                select(
                    User.username,
                    User.first_name,
                    User.last_name,
                    Task.name,
                    coalesce(Grade.score, 0),
                    User.id,
                )
                .join(UserOnCourse, UserOnCourse.user_id == User.id)
                .join(Course, Course.id == UserOnCourse.course_id)
                .outerjoin(Grade, (Grade.user_on_course_id == UserOnCourse.id))
                .outerjoin(Grade.task)
                .outerjoin(Task.group)
                .where(
                    Course.name == course_name,
                )
            )

            if program_managers_subquery is not None:
                statement = statement.where(~User.id.in_(program_managers_subquery))

            rows = session.execute(statement).all()

            scores_and_names: dict[str, tuple[dict[str, int], tuple[str, str]]] = {}

            for username, first_name, last_name, task_name, score, _ in rows:
                if username not in scores_and_names:
                    scores_and_names[username] = ({}, (first_name, last_name))
                if task_name is not None:
                    scores_and_names[username][0][task_name] = score

            return scores_and_names

    def get_grades(self, course_name: str) -> ManytaskFinalGradeConfig:
        """Method for getting config with grades for the course

        :param course_name: course name

        :return: dict with list of possible criterions for each grade
        """

        with self._session_create() as session:
            course = DataBaseApi._get(session, models.Course, name=course_name)

            grades: dict[int, list[dict[Path, int | float]]] = {}
            for grade in course.course_grades:
                formulas = []
                for f in grade.primary_formulas.all():
                    f.primary_formula
                    formulas.append({Path(k): v for k, v in f.primary_formula.items()})

                grades[grade.grade] = formulas

            grades_order = sorted(list(grades.keys()), reverse=True)
            return ManytaskFinalGradeConfig(grades=grades, grades_order=grades_order)

    def get_stats(self, course_name: str) -> dict[str, float]:
        """Method for getting stats of all tasks

        Excludes users with PROGRAM_MANAGER role from statistics.

        :param course_name: course name

        :return: dict with the names of tasks and their stats
        """

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
            namespace_id = course.namespace_id

            program_managers_subquery = None
            if namespace_id is not None:
                program_managers_subquery = select(models.UserOnNamespace.user_id).where(
                    models.UserOnNamespace.namespace_id == namespace_id,
                    models.UserOnNamespace.role == models.UserOnNamespaceRole.PROGRAM_MANAGER,
                )

            users_count_query = (
                session.query(func.count(UserOnCourse.id))
                .join(Course, Course.id == UserOnCourse.course_id)
                .filter(Course.name == course_name)
            )
            if program_managers_subquery is not None:
                users_count_query = users_count_query.filter(~UserOnCourse.user_id.in_(program_managers_subquery))
            users_on_courses_count = users_count_query.scalar()

            # fmt: off
            return {
                task_name: (
                    submits_count / users_on_courses_count
                    if users_on_courses_count > 0
                    else 0
                )
                for task_id, task_name, submits_count in self._get_tasks_submits_count(session, course_name, program_managers_subquery)
            }
            # fmt: on

    def get_scores_update_timestamp(self, course_name: str) -> str:
        """Method(deprecated) for getting last cached scores update timestamp

        :param course_name: course name

        :return: last update timestamp
        """

        return datetime.now(timezone.utc).isoformat()

    def update_cached_scores(self, course_name: str) -> None:
        """Method(deprecated) for updating cached scores"""

        return

    def store_score(self, course_name: str, username: str, task_name: str, update_fn: Callable[..., Any]) -> int:
        """Method for storing user's task score

        :param course_name: course name
        :param username: user name
        :param task_name: task name
        :param update_fn: function for updating the score

        :return: saved score
        """
        logger.debug(
            "Attempting to store score for user '%s' in course '%s' task '%s'", username, course_name, task_name
        )

        # TODO: in GoogleDocApi imported from google table, they used to increase the deadline for the user
        # flags = ''

        with self._session_create() as session:
            try:
                course = self._get(session, models.Course, name=course_name)
                user_on_course = self._get_or_create_user_on_course(session, username, course)
                session.commit()

                try:
                    task = self._get_task_by_name_and_course_id(session, task_name, course.id)
                except NoResultFound:
                    logger.warning("Task '%s' not found in course '%s'", task_name, course_name)
                    return 0

                grade = self._get_or_create_sfu_grade(session, user_on_course.id, task.id)
                new_score = update_fn("", grade.score)
                grade.score = new_score
                grade.last_submit_date = datetime.now(timezone.utc)

                session.commit()
                logger.info(
                    "Setting score to %d for user_id=%s (username=%s) on task=%s",
                    new_score,
                    user_on_course.user.id,
                    user_on_course.user.username,
                    task_name,
                )
                return new_score

            except Exception as e:
                session.rollback()
                logger.error("Failed to update score for '%s' on '%s': %s", username, task_name, str(e))
                raise

    def get_course(
        self,
        course_name: str,
    ) -> AppCourse | None:
        """Get course.Course by course_name

        Get models.Course by course_name from database and convert it to course.Course
        """
        try:
            with self._session_create() as session:
                course: models.Course = self._get(session, models.Course, name=course_name)

            return course.to_app_course()
        except NoResultFound:
            return None

    def create_course(
        self,
        settings_config: AppCourseConfig,
    ) -> bool:
        """Create from config object

        :param settings_config: CourseConfig object

        :return: is course created, false if course created before
        """
        logger.info("Attempting to create course with name '%s'", settings_config.course_name)

        with self._session_create() as session:
            try:
                self._get(session, models.Course, name=settings_config.course_name)
                logger.info("Course '%s' already exists", settings_config.course_name)
                return False
            except NoResultFound:
                logger.debug("Creating new course '%s'", settings_config.course_name)
                self._create(
                    session,
                    models.Course,
                    name=settings_config.course_name,
                    namespace_id=settings_config.namespace_id,
                    registration_secret=settings_config.registration_secret,
                    token=settings_config.token,
                    show_allscores=settings_config.show_allscores,
                    status=settings_config.status,
                    gitlab_course_group=settings_config.gitlab_course_group,
                    gitlab_course_public_repo=settings_config.gitlab_course_public_repo,
                    gitlab_course_students_group=settings_config.gitlab_course_students_group,
                    gitlab_default_branch=settings_config.gitlab_default_branch,
                    task_url_template=settings_config.task_url_template,
                    links=settings_config.links,
                    deadlines_type=settings_config.deadlines_type,
                )
                logger.info("Successfully created course '%s'", settings_config.course_name)
                return True

    def edit_course(
        self,
        settings_config: AppCourseConfig,
    ) -> bool:
        """Edit Course by course_name from config object

        :param course_name: course name
        :param settings_config: CourseConfig object

        :return: True if course was updated, False if course not found
        """
        logger.info("Attempting to edit course '%s'", settings_config.course_name)

        with self._session_create() as session:
            try:
                self._update(
                    session,
                    models.Course,
                    defaults={
                        "gitlab_course_group": settings_config.gitlab_course_group,
                        "gitlab_course_public_repo": settings_config.gitlab_course_public_repo,
                        "gitlab_course_students_group": settings_config.gitlab_course_students_group,
                        "gitlab_default_branch": settings_config.gitlab_default_branch,
                        "registration_secret": settings_config.registration_secret,
                        "show_allscores": settings_config.show_allscores,
                        "status": settings_config.status,
                        "task_url_template": settings_config.task_url_template,
                        "links": settings_config.links,
                        "deadlines_type": settings_config.deadlines_type,
                    },
                    name=settings_config.course_name,
                )
                logger.info("Successfully updated course '%s'", settings_config.course_name)
                return True
            except NoResultFound:
                logger.error("Failed to update course: course '%s' not found", settings_config.course_name)
                return False

    def update_course(
        self,
        course_name: str,
        config: ManytaskConfig,
    ) -> None:
        """Update course settings from config objects

        :param course_name: course name
        :param config: ManytaskConfig object
        """
        logger.info("Updating course settings for course '%s'", course_name)

        with self._session_create() as session:
            self._update(
                session,
                models.Course,
                defaults={
                    "task_url_template": config.ui.task_url_template,
                    "links": config.ui.links,
                    "deadlines_type": config.deadlines.deadlines,
                },
                name=course_name,
            )

        self._update_task_groups_from_config(course_name, config.deadlines)
        self._sync_columns(course_name, config.deadlines, config.status)
        self._sync_grades_config(course_name, config.grades)

        logger.info("Successfully updated course '%s'", course_name)

    def find_task(self, course_name: str, task_name: str) -> tuple[AppCourse, ManytaskGroupConfig, ManytaskTaskConfig]:
        """Find task and its group by task name. Serialize result to Config objects.

        Raise TaskDisabledError if task or its group is disabled

        :param course_name: course name
        :param task_name: task name

        :return: pair of ManytaskGroupConfig and ManytaskTaskConfig objects
        """

        with self._session_create() as session:
            logger.debug("Looking for task '%s' in course '%s'", task_name, course_name)
            course = self._get(session, models.Course, name=course_name)
            try:
                task = self._get_task_by_name_and_course_id(session, task_name, course.id)
            except NoResultFound:
                logger.error("Task '%s' not found in course '%s'", task_name, course_name)
                raise KeyError(f"Task {task_name} not found")

            if not task.enabled:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            if not task.group.enabled:
                raise TaskDisabledError(f"Task {task_name} group {task.group.name} is disabled")

            group = task.group
            group_tasks = group.tasks
            group_deadlines = group.deadline

        logger.info("Successfully found task '%s' in course '%s'", task_name, course_name)

        group_config = ManytaskGroupConfig(
            group=group.name,
            enabled=group.enabled,
            start=group_deadlines.start,
            steps=cast(dict[float, datetime | timedelta], group_deadlines.steps),
            end=group_deadlines.end,
            tasks=[
                ManytaskTaskConfig(
                    task=group_task.name,
                    enabled=group_task.enabled,
                    score=group_task.score,
                    min_score=group_task.min_score,
                    is_bonus=group_task.is_bonus,
                    is_large=group_task.is_large,
                    is_special=group_task.is_special,
                    url=AnyUrl(group_task.url) if group_task.url is not None else None,
                )
                for group_task in group_tasks
            ],
        )

        task_config = ManytaskTaskConfig(
            task=task.name,
            enabled=task.enabled,
            score=task.score,
            min_score=task.min_score,
            is_bonus=task.is_bonus,
            is_large=task.is_large,
            is_special=task.is_special,
        )

        return course.to_app_course(), group_config, task_config

    def get_groups(
        self,
        course_name: str,
        enabled: bool | None = None,
        started: bool | None = None,
        now: datetime | None = None,
    ) -> list[ManytaskGroupConfig]:
        """Get tasks groups. Serialize result to Config object.

        :param course_name: course name
        :param enabled: flag to check for group is enabled
        :param started: flag to check for group is started
        :param now: optional param for setting current time

        :return: list of ManytaskGroupConfig objects
        """

        if now is None:
            now = self.get_now_with_timezone(course_name)

        with self._session_create() as session:
            logger.debug(
                "Fetching groups for course '%s', enabled=%s, started=%s, now=%s", course_name, enabled, started, now
            )
            course = self._get(session, models.Course, name=course_name)

            query = (
                session.query(models.TaskGroup)
                .join(models.Deadline)
                .filter(models.TaskGroup.course_id == course.id)
                .options(
                    joinedload(models.TaskGroup.deadline),
                    selectinload(models.TaskGroup.tasks).selectinload(models.Task.grades),
                )
            )

            if enabled is not None:
                query = query.filter(models.TaskGroup.enabled == enabled)

            if started is not None:
                if started:
                    query = query.filter(now >= models.Deadline.start)
                else:
                    query = query.filter(now < models.Deadline.start)

            groups = query.order_by(models.TaskGroup.position).all()
            logger.info("Found %s groups in course '%s'", len(groups), course_name)

            result_groups = []
            for group in groups:
                tasks = []

                for task in group.tasks:
                    if enabled is not None and enabled != task.enabled:
                        continue

                    tasks.append(
                        ManytaskTaskConfig(
                            task=task.name,
                            enabled=task.enabled,
                            score=task.score,
                            min_score=task.min_score,
                            is_bonus=task.is_bonus,
                            is_large=task.is_large,
                            is_special=task.is_special,
                            url=AnyUrl(task.url) if task.url is not None else None,
                        )
                    )

                result_groups.append(
                    ManytaskGroupConfig(
                        group=group.name,
                        enabled=group.enabled,
                        start=group.deadline.start,
                        steps=cast(dict[float, datetime | timedelta], group.deadline.steps),
                        end=group.deadline.end,
                        tasks=tasks,
                    )
                )

        return result_groups

    def get_now_with_timezone(self, course_name: str) -> datetime:
        """Get current time with course timezone"""

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
        return datetime.now(tz=ZoneInfo(course.timezone))

    def max_score(self, course_name: str, started: bool | None = True) -> int:
        with self._session_create() as session:
            tasks = self._get_all_tasks(session, course_name, enabled=True, started=started, is_bonus=False)

        return sum(task.score for task in tasks)

    def max_score_started(self, course_name: str) -> int:
        return self.max_score(course_name, started=True)

    def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool:
        """Sync admin flag in gitlab and db"""

        with self._session_create() as session:
            logger.debug(
                f"Syncing admin status for user '{username}' in course '{course_name}', new_status={course_admin}"
            )
            course = self._get(session, models.Course, name=course_name)
            user = self._get(session, models.User, username=username)
            user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
            if course_admin != user_on_course.is_course_admin and course_admin:
                logger.info("Granting course admin rights to '%s' in course '%s'", username, course_name)
                user_on_course = self._update(
                    session=session,
                    model=models.UserOnCourse,
                    defaults={"is_course_admin": course_admin},
                    user_id=user.id,
                    course_id=course.id,
                )
            return user_on_course.is_course_admin

    def check_user_on_course(self, course_name: str, username: str) -> bool:
        """Checking that user has been enrolled on course"""

        with self._session_create() as session:
            logger.debug("Checking if user '%s' is enrolled in course '%s'", username, course_name)
            course = self._get(session, models.Course, name=course_name)
            user = self._get(session, models.User, username=username)
            try:
                self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
                logger.info("User '%s' is enrolled in course '%s'", username, course_name)
                return True
            except Exception:
                logger.warning("User '%s' isn't enrolled in course '%s'", username, course_name)
                return False

    def update_or_create_user(self, username: str, first_name: str, last_name: str, rms_id: int) -> None:
        """Update or create user in DB"""

        with self._session_create() as session:
            logger.debug(
                f"Creating or updating user '{username}' "
                f"(first_name={first_name}, last_name={last_name}, rms_id={rms_id})"
            )
            self._update_or_create(
                session,
                models.User,
                defaults=dict(
                    rms_id=rms_id,
                ),
                create_defaults=dict(
                    first_name=first_name,
                    last_name=last_name,
                ),
                username=username,
            )
            session.commit()
            logger.info("User '%s' created or updated in database", username)

    def get_user_courses_names_with_statuses(self, username: str) -> list[tuple[str, CourseStatus]]:
        """Get a list of courses names that the user participates in"""

        with self._session_create() as session:
            logger.debug("Fetching courses with statuses for user '%s'", username)
            try:
                user = self._get(session, models.User, username=username)
            except NoResultFound:
                logger.warning("User '%s' not found in database", username)
                return []

            hidden_for_user = [CourseStatus.CREATED, CourseStatus.HIDDEN]
            user_on_courses = user.users_on_courses.filter(models.Course.status.notin_(hidden_for_user)).all()

            result = [(user_on_course.course.name, user_on_course.course.status) for user_on_course in user_on_courses]
            logger.info("User '%s' participates in %s courses", username, len(result))
            return result

    def get_all_courses_names_with_statuses(self) -> list[tuple[str, CourseStatus]]:
        """Get a list of all courses names"""

        with self._session_create() as session:
            courses = session.query(models.Course).all()
            logger.info("Fetched all courses: count=%s", len(courses))

            result = [(course.name, course.status) for course in courses]
            return result

    def get_namespace_admin_namespaces(self, username: str) -> list[int]:
        """Get list of namespace IDs where user is Namespace Admin or Owner

        :param username: username to check
        :return: list of namespace IDs
        """
        with self._session_create() as session:
            logger.debug("Fetching namespace admin namespaces for user '%s'", username)
            try:
                user = self._get(session, models.User, username=username)
            except NoResultFound:
                logger.warning("User '%s' not found when fetching namespace admin namespaces", username)
                return []

            namespace_ids = set()

            owned_namespaces = session.query(models.Namespace).filter(models.Namespace.created_by_id == user.id).all()
            namespace_ids.update(ns.id for ns in owned_namespaces)

            admin_namespaces = (
                session.query(models.UserOnNamespace)
                .filter(
                    and_(
                        models.UserOnNamespace.user_id == user.id,
                        models.UserOnNamespace.role == models.UserOnNamespaceRole.NAMESPACE_ADMIN,
                    )
                )
                .all()
            )
            namespace_ids.update(un.namespace_id for un in admin_namespaces)

            result = list(namespace_ids)
            logger.info("User '%s' is namespace admin in %d namespaces", username, len(result))
            return result

    def get_courses_by_namespace_ids(self, namespace_ids: list[int]) -> list[tuple[str, CourseStatus]]:
        """Get courses from specified namespaces

        :param namespace_ids: list of namespace IDs
        :return: list of tuples (course_name, course_status)
        """
        if not namespace_ids:
            return []

        with self._session_create() as session:
            logger.debug("Fetching courses from %d namespaces", len(namespace_ids))
            courses = session.query(models.Course).filter(models.Course.namespace_id.in_(namespace_ids)).all()

            result = [(course.name, course.status) for course in courses]
            logger.info("Found %d courses in specified namespaces", len(result))
            return result

    def get_courses_where_course_admin(self, username: str) -> list[tuple[str, CourseStatus]]:
        """Get courses where user is Course Admin

        :param username: username to check
        :return: list of tuples (course_name, course_status)
        """
        with self._session_create() as session:
            logger.debug("Fetching courses where user '%s' is course admin", username)
            try:
                user = self._get(session, models.User, username=username)
            except NoResultFound:
                logger.warning("User '%s' not found when fetching course admin courses", username)
                return []

            user_on_courses = (
                session.query(models.UserOnCourse)
                .filter(
                    and_(
                        models.UserOnCourse.user_id == user.id,
                        models.UserOnCourse.is_course_admin.is_(True),
                    )
                )
                .all()
            )

            result = [(uoc.course.name, uoc.course.status) for uoc in user_on_courses]
            logger.info("User '%s' is course admin in %d courses", username, len(result))
            return result

    def get_all_users(self) -> list[StoredUser]:
        """Get all users from the database

        :return: list of all users
        """
        with self._session_create() as session:
            users = session.query(models.User).all()
            logger.info("Fetched all users: count=%s", len(users))
            return [
                StoredUser(
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    rms_id=user.rms_id,
                    instance_admin=user.is_instance_admin,
                )
                for user in users
            ]

    def set_instance_admin_status(self, username: str, is_admin: bool) -> None:
        """Change user admin status

        :param username: user name
        :param is_admin: new admin status
        """
        logger.info("Setting instance admin status to %s for user '%s'", is_admin, username)

        with self._session_create() as session:
            try:
                if not is_admin:
                    logger.debug("Checking admin count before removing admin status from '%s'", username)
                    admin_count = session.query(func.count()).filter(models.User.is_instance_admin.is_(True)).scalar()
                    if admin_count <= 1:
                        logger.error("Cannot remove admin status from user '%s': this is the last admin", username)
                        return

                self._update(session, models.User, defaults={"is_instance_admin": is_admin}, username=username)
                logger.info("Successfully updated admin status for user '%s' to %s", username, is_admin)

            except NoResultFound:
                logger.error("Failed to set admin status: user '%s' not found in database", username)

    def update_user_profile(self, username: str, new_first_name: str | None, new_last_name: str | None) -> None:
        """Update user profile information
        :param username: user name
        :param new_first_name: new first name
        :param new_last_name: new last name
        """
        with self._session_create() as session:
            try:
                user = self._get(session, models.User, username=username)
                old_first_name, old_last_name = user.first_name, user.last_name

                if new_first_name:
                    user.first_name = new_first_name
                if new_last_name:
                    user.last_name = new_last_name

                session.commit()

                changes = []
                if new_first_name:
                    changes.append(f"first_name: {old_first_name} -> {new_first_name}")
                if new_last_name:
                    changes.append(f"last_name: {old_last_name} -> {new_last_name}")

                if changes:
                    logger.info("Updated user %s profile: %s", username, ", ".join(changes))
            except NoResultFound:
                logger.error("User %s not found in the database", username)

    def _update_task_groups_from_config(
        self,
        course_name: str,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        """Update task groups based on new deadline config data.

        This method:
        1. Finds tasks that need to be moved to different groups
        2. Creates any missing groups
        3. Updates task group assignments

        :param deadlines_config: ManytaskDeadlinesConfig object
        """
        with self._session_create() as session:
            logger.debug("Updating task groups from config for course '%s'", course_name)
            new_task_names = set()
            new_task_to_group = {}
            for group in deadlines_config.groups:
                for task_config in group.tasks:
                    new_task_names.add(task_config.name)
                    new_task_to_group[task_config.name] = group.name

            existing_tasks = session.query(models.Task).join(models.TaskGroup).all()

            # Check for duplicates (name + course)
            tasks_to_update = {}
            for existing_task in existing_tasks:
                if existing_task.name in new_task_names:
                    task_group = existing_task.group
                    task_course = task_group.course

                    if task_course.name == course_name:
                        new_group_name = new_task_to_group[existing_task.name]
                        if task_group.name != new_group_name:
                            tasks_to_update[existing_task.id] = new_group_name

            # Create any missing groups
            course = self._get(session, models.Course, name=course_name)
            needed_group_names = set(tasks_to_update.values())
            existing_groups = session.query(models.TaskGroup).filter_by(course_id=course.id).all()
            existing_group_names = {g.name for g in existing_groups}

            for group_name in needed_group_names:
                if group_name not in existing_group_names:
                    new_group = models.TaskGroup(name=group_name, course_id=course.id)
                    session.add(new_group)
                    logger.info("Created new task group '%s' for course '%s'", group_name, course_name)

            session.commit()

            # Update groups for existing tasks
            for task_id, new_group_name in tasks_to_update.items():
                existing_task = session.query(models.Task).filter_by(id=task_id).one()

                new_group = (
                    session.query(models.TaskGroup)
                    .filter_by(name=new_group_name, course_id=existing_task.group.course_id)
                    .one()
                )
                existing_task.group = new_group
                logger.info(
                    "Moved task '%s' to group '%s' in course '%s'", existing_task.name, new_group_name, course_name
                )

            session.commit()
            logger.info("Task groups updated from config for course '%s'", course_name)

    def _sync_columns(
        self,
        course_name: str,
        deadlines_config: ManytaskDeadlinesConfig,
        status: CourseStatus | None,
    ) -> None:
        """Method for updating deadlines config

        :param course_name: course name
        :param deadlines_config: ManytaskDeadlinesConfig object
        :param status: status of course
        """

        groups = deadlines_config.groups

        logger.info("Syncing deadlines config for course '%s'", course_name)
        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)

            if course.status == CourseStatus.CREATED:
                course.status = CourseStatus.HIDDEN

            if status is not None:
                course.status = status

            existing_course_tasks = (
                session.query(models.Task).join(models.TaskGroup).filter(models.TaskGroup.course_id == course.id).all()
            )
            existing_course_groups = session.query(models.TaskGroup).filter_by(course_id=course.id).all()

            # Disabling tasks and groups removed from the config
            for existing_task in existing_course_tasks:
                existing_task.enabled = False
                existing_task.position = 0
            for existing_group in existing_course_groups:
                existing_group.enabled = False
                existing_group.position = 0

            # update deadlines parameters
            course.timezone = deadlines_config.timezone
            course.max_submissions = deadlines_config.max_submissions
            course.submission_penalty = deadlines_config.submission_penalty

            # update deadlines for each group
            for group_pos, group in enumerate(groups, start=1):
                tasks = group.tasks

                deadline_start = group.start
                deadline_steps = {
                    k: self._convert_timedelta_to_datetime(group.start, v) for k, v in group.steps.items()
                }
                deadline_end = self._convert_timedelta_to_datetime(group.start, group.end)

                task_group = DataBaseApi._update_or_create(
                    session,
                    models.TaskGroup,
                    defaults={"enabled": group.enabled, "position": group_pos},
                    name=group.name,
                    course_id=course.id,
                )

                DataBaseApi._update_deadline_for_task_group(
                    session, task_group, deadline_start, deadline_steps, deadline_end
                )
                logger.debug("Updated deadline for group '%s' in course '%s'", group.name, course_name)

                for task_pos, task in enumerate(tasks, start=1):
                    self._update_or_create(
                        session,
                        models.Task,
                        defaults={
                            "score": task.score,
                            "min_score": task.min_score,
                            "is_bonus": task.is_bonus,
                            "is_large": task.is_large,
                            "is_special": task.is_special,
                            "enabled": task.enabled,
                            "url": str(task.url) if task.url is not None else None,
                            "position": task_pos,
                        },
                        name=task.name,
                        group_id=task_group.id,
                    )
                    logger.debug(
                        "Updated/created task '%s' in group '%s' (course '%s')", task.name, group.name, course_name
                    )
            session.commit()
        logger.info("Deadlines config synced for course '%s'", course_name)

    def _sync_grades_config(self, course_name: str, grades_config: ManytaskFinalGradeConfig | None) -> None:
        if grades_config is None:
            # shortcut to remove existing grade formulas
            logger.debug("No grades config provided for course=%s, skipping sync", course_name)
            grades_config = ManytaskFinalGradeConfig(grades={}, grades_order=[])
            return

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
            logger.debug("Syncing grades config for course=%s id=%s", course.name, course.id)
            existing_complex_formulas = session.query(models.ComplexFormula).filter_by(course_id=course.id).all()

            existing_complex_formulas_grades = set(
                complex_formula.grade for complex_formula in existing_complex_formulas
            )
            config_complex_formulas_grades = set(grades_config.grades.keys())

            # add new grades
            for grade in config_complex_formulas_grades - existing_complex_formulas_grades:
                logger.info("Adding new grade=%s to course_id=%s", grade, course.id)
                complex_formula = self._update_or_create(
                    session, models.ComplexFormula, grade=grade, course_id=course.id
                )

                for primary_formula in grades_config.grades[grade]:
                    primary_formula_dict = {str(k): v for k, v in primary_formula.items()}
                    logger.debug("Creating primary formula=%s for grade=%s", primary_formula_dict, grade)
                    self._create(
                        session,
                        models.PrimaryFormula,
                        primary_formula=primary_formula_dict,
                        complex_id=complex_formula.id,
                    )

            # remove deleted grades
            for grade in existing_complex_formulas_grades - config_complex_formulas_grades:
                logger.info("Removing deleted grade=%s from course_id=%s", grade, course.id)
                complex_formula = (
                    session.query(models.ComplexFormula)
                    .filter_by(
                        course_id=course.id,
                        grade=grade,
                    )
                    .one()
                )

                session.query(models.PrimaryFormula).filter_by(
                    complex_id=complex_formula.id,
                ).delete()

                session.query(models.ComplexFormula).filter_by(
                    course_id=course.id,
                    grade=grade,
                ).delete()

            # update existing grades
            for grade in existing_complex_formulas_grades & config_complex_formulas_grades:
                logger.debug("Updating existing grade=%s for course_id=%s", grade, course.id)
                complex_formula = (
                    session.query(models.ComplexFormula)
                    .filter_by(
                        course_id=course.id,
                        grade=grade,
                    )
                    .one()
                )

                existing_primary_formulas = (
                    session.query(models.PrimaryFormula).filter_by(complex_id=complex_formula.id).all()
                )
                existing_primary_formulas_set = set(
                    frozenset((k, v) for k, v in primary_formula.primary_formula.items())
                    for primary_formula in existing_primary_formulas
                )
                new_primary_formulas_set = set(
                    frozenset((str(k), v) for k, v in primary_formula.items())
                    for primary_formula in grades_config.grades[grade]
                )

                # remove deleted primary formulas
                for formula in existing_primary_formulas_set - new_primary_formulas_set:
                    formula_dict = dict()
                    for k, v in formula:
                        formula_dict[k] = v
                    logger.debug("Removing primary formula=%s from grade=%s", formula_dict, grade)
                    session.query(models.PrimaryFormula).filter_by(
                        complex_id=complex_formula.id,
                        primary_formula=formula_dict,
                    ).delete()

                # add new primary formulas
                for formula in new_primary_formulas_set - existing_primary_formulas_set:
                    formula_dict = dict()
                    for k, v in formula:
                        formula_dict[k] = v
                    logger.debug("Adding new primary formula=%s to grade=%s", formula_dict, grade)
                    self._create(
                        session,
                        models.PrimaryFormula,
                        primary_formula=formula_dict,
                        complex_id=complex_formula.id,
                    )

            session.commit()
            logger.info("Grades config sync completed for course=%s id=%s", course.name, course.id)

    def _check_pending_migrations(self, database_url: str) -> bool:
        logger.debug("Checking pending migrations for database_url=%s", database_url)
        alembic_cfg = Config(self.DEFAULT_ALEMBIC_PATH, config_args={"sqlalchemy.url": database_url})

        with self.engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection

            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

            script = ScriptDirectory.from_config(alembic_cfg)
            head_rev = script.get_current_head()

            logger.debug("Current revision=%s, head revision=%s", current_rev, head_rev)
            if current_rev == head_rev:
                logger.info("No pending migrations found")
                return False

            logger.info("Pending migrations detected")
            return True

    def _apply_migrations(self, database_url: str) -> None:
        logger.info("Applying migrations for database_url=%s", database_url)
        alembic_cfg = Config(self.DEFAULT_ALEMBIC_PATH, config_args={"sqlalchemy.url": database_url})

        try:
            with self.engine.begin() as connection:
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")  # models.Base.metadata.create_all(self.engine)
            logger.info("Migrations applied successfully")
        except IntegrityError as e:  # if tables are created concurrently
            if not isinstance(e.orig, UniqueViolation):
                raise
        except ProgrammingError as e:  # if tables are created concurrently
            if not isinstance(e.orig, DuplicateColumn):
                raise
        except DuplicateTable:  # if tables are created concurrently
            pass

    def _get_or_create_user_on_course(
        self, session: Session, username: str, course: models.Course
    ) -> models.UserOnCourse:
        user = self._get(
            session,
            models.User,
            username=username,
        )

        user_on_course = self._get_or_create(session, models.UserOnCourse, user_id=user.id, course_id=course.id)

        return user_on_course

    def _get_scores(
        self,
        session: Session,
        course_name: str,
        username: str,
        enabled: bool | None = None,
        started: bool | None = None,
        only_bonus: bool = False,
    ) -> Optional[Iterable["models.Grade"]]:
        try:
            course = self._get(session, models.Course, name=course_name)
            user = self._get(session, models.User, username=username)

            user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
        except NoResultFound:
            return None

        grades = self._get_all_grades(
            user_on_course, enabled=enabled, started=started, only_bonus=only_bonus, include_bonus_score=True
        )
        return grades

    @staticmethod
    def _convert_timedelta_to_datetime(start: datetime, value: datetime | timedelta) -> datetime:
        if isinstance(value, datetime):
            return value
        return start + value

    @staticmethod
    def _get(
        session: Session,
        model: Type[ModelType],
        **kwargs: Any,  # params for get
    ) -> ModelType:
        try:
            logger.debug("Getting %s with params: %s", model.__name__, kwargs)
            return session.query(model).filter_by(**kwargs).one()
        except NoResultFound:
            logger.error("%s not found with params: %s", model.__name__, kwargs)
            raise NoResultFound(f"{model.__name__} not found with params: {kwargs}")

    @staticmethod
    def _update(
        session: Session,
        model: Type[ModelType],
        defaults: Optional[dict[str, Any]] = None,  # params for update
        **kwargs: Any,  # params for get
    ) -> ModelType:
        instance = DataBaseApi._get(session, model, **kwargs)

        if defaults:
            logger.debug("Updating %s %s", model.__name__, kwargs)
            for key, value in defaults.items():
                setattr(instance, key, value)
            session.commit()
        return instance

    @staticmethod
    def _create(
        session: Session,
        model: Type[ModelType],
        **kwargs: Any,  # params for create
    ) -> ModelType:
        try:
            logger.debug("Creating %s with params: %s", model.__name__, kwargs)
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
            return instance
        except IntegrityError:
            session.rollback()
            logger.warning("%s with params %s already exists, fetching existing", model.__name__, kwargs)
            return session.query(model).filter_by(**kwargs).one()

    @staticmethod
    def _query_with_for_update(
        session: Session, model: Type[ModelType], allow_none: bool = True, **kwargs: Any
    ) -> Optional[ModelType]:
        """Query a model with SELECT FOR UPDATE to prevent concurrent modifications.

        :param session: SQLAlchemy session
        :param model: Model class to query
        :param allow_none: If True, returns None if no instance found, otherwise raises NoResultFound
        :param kwargs: Filter parameters
        :return: Model instance or None if allow_none is True and no instance found
        :raises: NoResultFound if allow_none is False and no instance found
        """
        query = session.query(model).with_for_update().filter_by(**kwargs)
        return query.one_or_none() if allow_none else query.one()

    @staticmethod
    def _create_or_update_instance(
        session: Session,
        model: Type[ModelType],
        instance: Optional[ModelType],
        defaults: Optional[dict[str, Any]] = None,
        create_defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ModelType:
        """Create a new instance or update existing one with defaults.

        :param session: SQLAlchemy session
        :param model: Model class
        :param instance: Existing instance if any
        :param defaults: Default values to update on the instance
        :param create_defaults: Additional defaults to use only for creation
        :param kwargs: Parameters for instance creation
        :return: Created or updated instance
        """
        if instance:
            logger.debug("Updating existing %s with defaults: %s", model.__name__, defaults)
            if defaults:
                for key, value in defaults.items():
                    setattr(instance, key, value)
                session.flush()
            return instance

        if defaults is not None:
            kwargs.update(defaults)
        if create_defaults is not None:
            kwargs.update(create_defaults)

        try:
            logger.debug("Creating new %s with params: %s", model.__name__, kwargs)
            new_instance = model(**kwargs)
            session.add(new_instance)
            session.flush()
            return new_instance
        except IntegrityError:
            session.rollback()
            logger.warning("%s creation conflict, fetching existing", model.__name__)
            existing_instance = cast(
                ModelType, DataBaseApi._query_with_for_update(session, model, allow_none=False, **kwargs)
            )
            if defaults:
                for key, value in defaults.items():
                    setattr(existing_instance, key, value)
            session.flush()
            return existing_instance

    @staticmethod
    def _get_or_create(
        session: Session,
        model: Type[ModelType],
        defaults: Optional[dict[str, Any]] = None,  # params for create
        **kwargs: Any,  # params for get
    ) -> ModelType:
        try:
            instance = DataBaseApi._query_with_for_update(session, model, **kwargs)
            return DataBaseApi._create_or_update_instance(
                session,
                model,
                instance,
                defaults=None,
                create_defaults=defaults,
                **kwargs,
            )
        except Exception:
            session.rollback()
            logger.exception("Failed to get or create %s with params %s", model.__name__, kwargs)
            raise

    @staticmethod
    def _update_or_create(
        session: Session,
        model: Type[ModelType],
        defaults: Optional[dict[str, Any]] = None,  # params for update
        create_defaults: Optional[dict[str, Any]] = None,  # params for create
        **kwargs: Any,  # params for get
    ) -> ModelType:
        try:
            instance = DataBaseApi._query_with_for_update(session, model, **kwargs)
            return DataBaseApi._create_or_update_instance(session, model, instance, defaults, create_defaults, **kwargs)
        except Exception:
            session.rollback()
            logger.exception("Failed to update or create %s with params %s", model.__name__, kwargs)
            raise

    @staticmethod
    def _get_or_create_sfu_grade(
        session: Session,
        user_on_course_id: int,
        task_id: int,
    ) -> models.Grade:
        """Get or create a Grade with SELECT FOR UPDATE to prevent concurrent modifications.

        :param session: SQLAlchemy session
        :param user_on_course_id: ID of the UserOnCourse
        :param task_id: ID of the Task
        :return: The existing or newly created Grade
        """
        try:
            grade = DataBaseApi._query_with_for_update(
                session, models.Grade, user_on_course_id=user_on_course_id, task_id=task_id
            )
            return DataBaseApi._create_or_update_instance(
                session,
                models.Grade,
                grade,
                create_defaults={"score": 0},
                user_on_course_id=user_on_course_id,
                task_id=task_id,
            )
        except Exception:
            session.rollback()
            logger.exception(
                f"Failed to get or create grade for user_on_course_id={user_on_course_id}, task_id={task_id}"
            )
            raise

    @staticmethod
    def _get_task_by_name_and_course_id(session: Session, name: str, course_id: int) -> models.Task:
        logger.debug("Fetching task '%s' for course_id=%s", name, course_id)
        return (
            session.query(models.Task).filter_by(name=name).join(models.TaskGroup).filter_by(course_id=course_id).one()
        )

    @staticmethod
    def _update_deadline_for_task_group(
        session: Session,
        task_group: models.TaskGroup,
        deadline_start: datetime,
        deadline_steps: dict[Any, Any],  # json steps
        deadline_end: datetime,
    ) -> None:
        if task_group.deadline_id is None:
            deadline = DataBaseApi._create(
                session, models.Deadline, start=deadline_start, steps=deadline_steps, end=deadline_end
            )
            DataBaseApi._update(session, models.TaskGroup, defaults={"deadline_id": deadline.id}, id=task_group.id)
            logger.info("Created new deadline for task group '%s'", task_group.name)
        else:
            DataBaseApi._update(
                session,
                models.Deadline,
                defaults={"start": deadline_start, "steps": deadline_steps, "end": deadline_end},
                id=task_group.deadline.id,
            )
            logger.debug("Updated deadline for task group '%s'", task_group.name)

    def _get_all_grades(
        self,
        user_on_course: models.UserOnCourse,
        enabled: bool | None = None,
        started: bool | None = None,
        only_bonus: bool = False,
        include_bonus_score: bool = False,
    ) -> Iterable["models.Grade"]:
        query = (
            user_on_course.grades.options(selectinload(models.Grade.task))
            .join(models.Task)
            .join(models.TaskGroup)
            .join(models.Deadline)
        )

        if enabled is not None:
            cond = and_(models.Task.enabled == enabled, models.TaskGroup.enabled == enabled)
            if include_bonus_score:
                cond = or_(cond, models.Task.name == "bonus_score")
            query = query.filter(cond)

        if started is not None:
            if started:
                query = query.filter(self.get_now_with_timezone(user_on_course.course.name) >= models.Deadline.start)
            else:
                query = query.filter(self.get_now_with_timezone(user_on_course.course.name) < models.Deadline.start)

        if only_bonus:
            query = query.filter(models.Task.is_bonus)

        return query.all()

    def _get_all_tasks(
        self,
        session: Session,
        course_name: str,
        enabled: bool | None = None,
        started: bool | None = None,
        is_bonus: bool | None = None,
    ) -> Iterable["models.Task"]:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        query = (
            session.query(models.Task)
            .join(models.TaskGroup)
            .join(models.Deadline)
            .filter(models.TaskGroup.course_id == course.id)
            .options(selectinload(models.Task.grades))
        )

        if enabled is not None:
            query = query.filter(and_(models.Task.enabled == enabled, models.TaskGroup.enabled == enabled))

        if is_bonus is not None:
            query = query.filter(models.Task.is_bonus == is_bonus)

        if started is not None:
            now = self.get_now_with_timezone(course_name)
            if started:
                query = query.filter(now >= models.Deadline.start)
            else:
                query = query.filter(now < models.Deadline.start)

        return query.all()

    @staticmethod
    def _get_course_users_on_courses_count(
        session: Session,
        course_name: str,
    ) -> int:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        return session.query(func.count(models.UserOnCourse.id)).filter_by(course_id=course.id).one()[0]

    def _get_tasks_submits_count(
        self,
        session: Session,
        course_name: str,
        program_managers_subquery: Select[tuple[int]] | None = None,
    ) -> list[Row[tuple[int, str, int]]]:
        """Get count of task submits, optionally excluding program managers.

        :param session: Database session
        :param course_name: Name of the course
        :param program_managers_subquery: Subquery to select user IDs to exclude (program managers)
        :return: List of (task_id, task_name, submits_count) tuples
        """
        join_conditions = [Grade.task_id == Task.id]
        if program_managers_subquery is not None:
            join_conditions.append(
                Grade.user_on_course_id.in_(
                    select(UserOnCourse.id).where(
                        and_(
                            UserOnCourse.course_id == Course.id,
                            ~UserOnCourse.user_id.in_(program_managers_subquery),
                        )
                    )
                )
            )

        query = (
            session.query(
                Task.id,
                Task.name,
                func.count(Grade.id),
            )
            .join(TaskGroup, Task.group_id == TaskGroup.id)
            .join(Course, Course.id == TaskGroup.course_id)
            .join(Deadline, TaskGroup.deadline_id == Deadline.id)
            .outerjoin(Grade, and_(*join_conditions))
        )

        return (
            query.filter(
                Course.name == course_name,
                Task.enabled.is_(True),
                TaskGroup.enabled.is_(True),
                self.get_now_with_timezone(course_name) >= models.Deadline.start,
            )
            .group_by(Task.id, Task.name)
            .all()
        )

    def get_student_comment(self, course_name: str, username: str) -> str | None:
        with self._session_create() as session:
            try:
                course = self._get(session, models.Course, name=course_name)
                user_on_course = self._get_or_create_user_on_course(session, username, course)
                return user_on_course.comment
            except NoResultFound:
                logger.warning(f"User {username} not found in course {course_name}")
                return None

    def update_student_comment(self, course_name: str, username: str, comment: str | None) -> None:
        with self._session_create() as session:
            try:
                course = self._get(session, models.Course, name=course_name)
                user_on_course = self._get_or_create_user_on_course(session, username, course)

                user_on_course.comment = comment
                session.commit()

                logger.info(f"Updated comment for user {username} in course {course_name}: -> '{comment}'")
            except NoResultFound:
                logger.error(f"User {username} not found in course {course_name}")
                raise

    def create_namespace(
        self,
        name: str,
        slug: str,
        description: str | None,
        gitlab_group_id: int,
        created_by_username: str,
    ) -> models.Namespace:
        """Create a new namespace and assign creator as namespace_admin.

        :param name: Display name of the namespace
        :param slug: URL slug for the namespace
        :param description: Optional description
        :param gitlab_group_id: GitLab group ID
        :param created_by_username: Username of the creator
        :return: Created Namespace object
        :raises IntegrityError: If slug or gitlab_group_id already exists
        """
        with self._session_create() as session:
            try:
                logger.info("Creating namespace name=%s slug=%s for user=%s", name, slug, created_by_username)

                creator = self._get(session, models.User, username=created_by_username)

                namespace = self._create(
                    session,
                    models.Namespace,
                    name=name,
                    slug=slug,
                    description=description,
                    gitlab_group_id=gitlab_group_id,
                    created_by_id=creator.id,
                )

                self._create(
                    session,
                    models.UserOnNamespace,
                    user_id=creator.id,
                    namespace_id=namespace.id,
                    role=models.UserOnNamespaceRole.NAMESPACE_ADMIN,
                    assigned_by_id=creator.id,
                )

                logger.info(
                    "Namespace created successfully id=%s slug=%s, creator %s assigned as namespace_admin",
                    namespace.id,
                    slug,
                    created_by_username,
                )

                return namespace

            except IntegrityError as e:
                session.rollback()
                logger.error("Failed to create namespace slug=%s: %s", slug, str(e))
                raise

    def get_all_namespaces(self) -> list[models.Namespace]:
        """Get all namespaces (for Instance Admin).

        :return: List of all Namespace objects
        """
        with self._session_create() as session:
            logger.debug("Fetching all namespaces")
            namespaces = session.query(models.Namespace).all()
            logger.info("Fetched %d namespaces", len(namespaces))
            session.expunge_all()
            return namespaces

    def get_user_namespaces(self, username: str) -> list[tuple[models.Namespace, str]]:
        """Get namespaces where user has a role.

        :param username: Username to filter by
        :return: List of tuples (Namespace, role_name)
        """
        with self._session_create() as session:
            logger.debug("Fetching namespaces for user=%s", username)

            try:
                user = self._get(session, models.User, username=username)
            except NoResultFound:
                logger.warning("User %s not found", username)
                return []

            results = (
                session.query(models.Namespace, models.UserOnNamespace.role)
                .join(models.UserOnNamespace, models.UserOnNamespace.namespace_id == models.Namespace.id)
                .filter(models.UserOnNamespace.user_id == user.id)
                .all()
            )

            logger.info("User %s has access to %d namespaces", username, len(results))

            namespace_role_pairs = [(ns, role.value) for ns, role in results]
            session.expunge_all()

            return namespace_role_pairs

    def get_namespace_by_id(self, namespace_id: int, username: str) -> tuple[models.Namespace, str | None]:
        """Get namespace by ID with access control.

        Instance Admin can access any namespace (role=None).
        Regular users can only access namespaces where they have a role.

        :param namespace_id: ID of the namespace
        :param username: Username to check access
        :return: (Namespace, role) where role=None for Instance Admin
        :raises NoResultFound: if namespace doesn't exist
        :raises PermissionError: if user doesn't have access
        """
        with self._session_create() as session:
            logger.debug("Fetching namespace id=%s for user=%s", namespace_id, username)

            try:
                namespace = self._get(session, models.Namespace, id=namespace_id)
            except NoResultFound:
                logger.warning("Namespace id=%s not found", namespace_id)
                raise PermissionError(f"Access denied to namespace {namespace_id}")

            try:
                user = self._get(session, models.User, username=username)
            except NoResultFound:
                logger.warning("User %s not found", username)
                raise PermissionError(f"Access denied to namespace {namespace_id}")

            if user.is_instance_admin:
                logger.info("Instance Admin %s accessing namespace id=%s", username, namespace_id)
                session.expunge(namespace)
                return (namespace, None)

            try:
                user_on_namespace = self._get(
                    session,
                    models.UserOnNamespace,
                    user_id=user.id,
                    namespace_id=namespace_id,
                )
                role = user_on_namespace.role.value
                logger.info("User %s has role %s in namespace id=%s", username, role, namespace_id)
                session.expunge(namespace)
                return (namespace, role)
            except NoResultFound:
                logger.warning("User %s has no access to namespace id=%s", username, namespace_id)
                raise PermissionError(f"Access denied to namespace {namespace_id}")

    def add_user_to_namespace(
        self,
        namespace_id: int,
        user_id: int,
        role: str,
        assigned_by_username: str,
    ) -> models.UserOnNamespace:
        """Add a user to a namespace with a specific role.

        :param namespace_id: ID of the namespace
        :param user_id: RMS ID (GitLab ID) of the user to add
        :param role: Role to assign ("namespace_admin" or "program_manager")
        :param assigned_by_username: Username of the user assigning the role
        :return: Created UserOnNamespace object
        :raises NoResultFound: If user or namespace not found
        :raises ValueError: If role is invalid
        :raises IntegrityError: If user already has a role in this namespace
        """
        with self._session_create() as session:
            logger.info(
                "Adding user with rms_id=%s to namespace_id=%s with role=%s by user=%s",
                user_id,
                namespace_id,
                role,
                assigned_by_username,
            )

            try:
                user = self._get(session, models.User, rms_id=user_id)
            except NoResultFound:
                logger.error("User with rms_id=%s not found", user_id)
                raise NoResultFound(f"User with rms_id={user_id} not found")

            try:
                namespace = self._get(session, models.Namespace, id=namespace_id)
            except NoResultFound:
                logger.error("Namespace with id=%s not found", namespace_id)
                raise NoResultFound(f"Namespace with id={namespace_id} not found")

            try:
                assigned_by = self._get(session, models.User, username=assigned_by_username)
            except NoResultFound:
                logger.error("Assigning user %s not found", assigned_by_username)
                raise NoResultFound(f"User {assigned_by_username} not found")

            if role == ROLE_NAMESPACE_ADMIN:
                role_enum = models.UserOnNamespaceRole.NAMESPACE_ADMIN
            elif role == ROLE_PROGRAM_MANAGER:
                role_enum = models.UserOnNamespaceRole.PROGRAM_MANAGER
            else:
                logger.error("Invalid role: %s", role)
                raise ValueError(f"Invalid role: {role}. Must be '{ROLE_NAMESPACE_ADMIN}' or '{ROLE_PROGRAM_MANAGER}'")

            user_db_id = user.id
            user_username = user.username
            namespace_slug = namespace.slug

            user_on_namespace = models.UserOnNamespace(
                user_id=user.id,
                namespace_id=namespace.id,
                role=role_enum,
                assigned_by_id=assigned_by.id,
            )
            session.add(user_on_namespace)

            try:
                session.commit()

                session.refresh(user_on_namespace)

                logger.info(
                    "User %s (id=%s) added to namespace %s (id=%s) with role %s",
                    user_username,
                    user_db_id,
                    namespace_slug,
                    namespace_id,
                    role,
                )

                _ = user_on_namespace.id
                _ = user_on_namespace.user_id
                _ = user_on_namespace.namespace_id

                session.expunge(user_on_namespace)
                session.expunge(user)
                session.expunge(namespace)
                return user_on_namespace

            except IntegrityError:
                session.rollback()
                logger.warning(
                    "User id=%s (rms_id=%s) already has a role in namespace id=%s",
                    user_db_id,
                    user_id,
                    namespace_id,
                )
                raise

    def get_namespace_users(self, namespace_id: int) -> list[tuple[int, str]]:
        """Get list of users with their roles in a namespace.

        :param namespace_id: ID of the namespace
        :return: List of tuples (user_id, role_string) where user_id is the database User.id
        """
        with self._session_create() as session:
            logger.debug("Fetching users for namespace_id=%s", namespace_id)

            results = (
                session.query(models.User.id, models.UserOnNamespace.role)
                .join(models.UserOnNamespace, models.UserOnNamespace.user_id == models.User.id)
                .filter(models.UserOnNamespace.namespace_id == namespace_id)
                .all()
            )

            logger.info("Found %d users in namespace_id=%s", len(results), namespace_id)

            user_role_pairs = [(user_id, role.value) for user_id, role in results]

            return user_role_pairs

    def remove_user_from_namespace(self, namespace_id: int, user_id: int) -> tuple[str, int]:
        """Remove a user from a namespace.

        :param namespace_id: ID of the namespace
        :param user_id: Database User.id (not rms_id)
        :return: Tuple of (role_string, rms_id) of the removed user
        :raises NoResultFound: If the user is not in the namespace
        """
        with self._session_create() as session:
            logger.info("Removing user_id=%s from namespace_id=%s", user_id, namespace_id)

            try:
                user_on_namespace = self._get(
                    session,
                    models.UserOnNamespace,
                    user_id=user_id,
                    namespace_id=namespace_id,
                )

                role = user_on_namespace.role.value
                user = self._get(session, models.User, id=user_id)
                rms_id = user.rms_id
                username = user.username

                session.delete(user_on_namespace)
                session.commit()

                logger.info(
                    "Successfully removed user %s (id=%s, rms_id=%s) with role %s from namespace_id=%s",
                    username,
                    user_id,
                    rms_id,
                    role,
                    namespace_id,
                )

                return (role, rms_id)

            except NoResultFound:
                logger.warning("User id=%s not found in namespace_id=%s", user_id, namespace_id)
                raise NoResultFound(f"User {user_id} is not in namespace {namespace_id}")

    def get_namespace_courses(self, namespace_id: int) -> list[dict[str, Any]]:
        """Get list of courses in a namespace with information about owners.

        :param namespace_id: ID of the namespace
        :return: List of dictionaries with course information:
            - id: Course database ID
            - name: Course name
            - status: Course status (value string)
            - gitlab_course_group: GitLab group path
            - owners: List of owner usernames
        """
        with self._session_create() as session:
            logger.info("Fetching courses for namespace_id=%s", namespace_id)

            courses = session.query(models.Course).filter_by(namespace_id=namespace_id).all()

            result = []
            for course in courses:
                course_admins = (
                    session.query(models.User.username)
                    .join(models.UserOnCourse)
                    .filter(
                        models.UserOnCourse.course_id == course.id,
                        models.UserOnCourse.is_course_admin == True,
                    )
                    .all()
                )

                owner_usernames = [admin[0] for admin in course_admins]

                result.append(
                    {
                        "id": course.id,
                        "name": course.name,
                        "status": course.status.value,
                        "gitlab_course_group": course.gitlab_course_group,
                        "owners": owner_usernames,
                    }
                )

            logger.info("Found %d courses for namespace_id=%s", len(result), namespace_id)
            return result

    def add_course_owners(
        self,
        course_id: int,
        owner_rms_ids: list[int],
        namespace_id: int,
    ) -> list[int]:
        """Add owners to a course.

        Validates that each owner has namespace_admin role in the course's namespace,
        then adds them as course admins.

        :param course_id: ID of the course
        :param owner_rms_ids: List of RMS IDs (GitLab user IDs) to add as owners
        :param namespace_id: ID of the namespace (for validation)
        :return: List of successfully added user RMS IDs
        :raises ValueError: If any owner doesn't have namespace_admin role in the namespace
        :raises NoResultFound: If course or users not found
        """
        with self._session_create() as session:
            logger.info(
                "Adding owners to course_id=%s: rms_ids=%s (validating against namespace_id=%s)",
                course_id,
                owner_rms_ids,
                namespace_id,
            )

            if not owner_rms_ids:
                logger.info("No owners to add")
                return []

            try:
                course = self._get(session, models.Course, id=course_id)
            except NoResultFound:
                logger.error("Course id=%s not found", course_id)
                raise NoResultFound(f"Course {course_id} not found")

            if course.namespace_id != namespace_id:
                logger.error(
                    "Course id=%s belongs to namespace_id=%s, not %s",
                    course_id,
                    course.namespace_id,
                    namespace_id,
                )
                raise ValueError(f"Course {course_id} does not belong to namespace {namespace_id}")

            added_owners = []

            for rms_id in owner_rms_ids:
                try:
                    user = self._get(session, models.User, rms_id=rms_id)

                    try:
                        user_on_namespace = self._get(
                            session,
                            models.UserOnNamespace,
                            user_id=user.id,
                            namespace_id=namespace_id,
                        )

                        if user_on_namespace.role != models.UserOnNamespaceRole.NAMESPACE_ADMIN:
                            logger.error(
                                "User %s (rms_id=%s) has role %s in namespace_id=%s, not namespace_admin",
                                user.username,
                                rms_id,
                                user_on_namespace.role.value,
                                namespace_id,
                            )
                            raise ValueError(
                                f"User with rms_id={rms_id} must have namespace_admin role in namespace {namespace_id}"
                            )
                    except NoResultFound:
                        logger.error(
                            "User %s (rms_id=%s) is not in namespace_id=%s",
                            user.username,
                            rms_id,
                            namespace_id,
                        )
                        raise ValueError(f"User with rms_id={rms_id} is not in namespace {namespace_id}")

                    user_on_course = self._update_or_create(
                        session,
                        models.UserOnCourse,
                        defaults={"is_course_admin": True},
                        user_id=user.id,
                        course_id=course_id,
                    )

                    logger.info(
                        "Added user %s (rms_id=%s, id=%s) as owner of course_id=%s",
                        user.username,
                        rms_id,
                        user.id,
                        course_id,
                    )

                    added_owners.append(rms_id)

                except NoResultFound:
                    logger.error("User with rms_id=%s not found in database", rms_id)
                    raise ValueError(f"User with rms_id={rms_id} not found")

            session.commit()

            logger.info(
                "Successfully added %d owners to course_id=%s",
                len(added_owners),
                course_id,
            )

            return added_owners

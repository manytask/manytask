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
from sqlalchemy import and_, create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.functions import func

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

    def get_stored_user(
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

    def check_if_instance_admin(
        self,
        username: str,
    ) -> bool:
        """Method for checking user's admin status

        :param username: user name

        :return: if the user is an admin on any course
        """

        with self._session_create() as session:
            try:
                user = self._get(session, models.User, username=username)
                return user.is_instance_admin
            except NoResultFound as e:
                logger.info(f"There was an exception when checking user admin status: {e}")
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
                course = self._get(session, models.Course, name=course_name)
                user = self._get(
                    session,
                    models.User,
                    username=username,
                )
                user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
                return user_on_course.is_course_admin
            except NoResultFound as e:
                logger.info(f"There was an exception when checking user admin status: {e}")
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
        """Method for getting all users scores with names
        :param course_name: course name
        :return: dict with the usernames as keys and a tuple of (first_name, last_name) and scores dict as values
        """

        with self._session_create() as session:
            all_users = self._get_all_users_on_course(session, course_name)

        scores_and_names: dict[str, tuple[dict[str, int], tuple[str, str]]] = {}
        for user in all_users:
            scores_and_names[user.username] = (
                self.get_scores(course_name, user.username),
                (user.first_name, user.last_name),
            )

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

        :param course_name: course name

        :return: dict with the names of tasks and their stats
        """

        with self._session_create() as session:
            tasks = self._get_all_tasks(session, course_name, enabled=True, started=True)

            users_on_courses_count = self._get_course_users_on_courses_count(session, course_name)
            tasks_stats: dict[str, float] = {}
            for task in tasks:
                if users_on_courses_count == 0:
                    tasks_stats[task.name] = 0
                else:
                    tasks_stats[task.name] = self._get_task_submits_count(session, task.id) / users_on_courses_count

        return tasks_stats

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
                    return 0

                grade = self._get_or_create_sfu_grade(session, user_on_course.id, task.id)
                new_score = update_fn("", grade.score)
                grade.score = new_score
                grade.last_submit_date = datetime.now(timezone.utc)

                session.commit()
                logger.info(f"Setting score = {new_score}")
                return new_score

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update score for {username} on {task_name}: {str(e)}")
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

            return AppCourse(
                AppCourseConfig(
                    course_name=course_name,
                    gitlab_course_group=course.gitlab_course_group,
                    gitlab_course_public_repo=course.gitlab_course_public_repo,
                    gitlab_course_students_group=course.gitlab_course_students_group,
                    gitlab_default_branch=course.gitlab_default_branch,
                    registration_secret=course.registration_secret,
                    token=course.token,
                    show_allscores=course.show_allscores,
                    status=course.status,
                    task_url_template=course.task_url_template,
                    links=course.links,
                )
            )
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

        with self._session_create() as session:
            try:
                self._get(session, models.Course, name=settings_config.course_name)
            except NoResultFound:
                self._create(
                    session,
                    models.Course,
                    name=settings_config.course_name,
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
                )
                return True

            return False

    def edit_course(
        self,
        settings_config: AppCourseConfig,
    ) -> bool:
        """Edit Course by course_name from config object

        :param course_name: course name
        :param settings_config: CourseConfig object

        :return: True if course was updated, False if course not found
        """

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
                    },
                    name=settings_config.course_name,
                )
                return True
            except NoResultFound:
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

        with self._session_create() as session:
            self._update(
                session,
                models.Course,
                defaults={
                    "task_url_template": config.ui.task_url_template,
                    "links": config.ui.links,
                },
                name=course_name,
            )

        self._update_task_groups_from_config(course_name, config.deadlines)
        self._sync_columns(course_name, config.deadlines, config.status)
        self._sync_grades_config(course_name, config.grades)

    def find_task(self, course_name: str, task_name: str) -> tuple[ManytaskGroupConfig, ManytaskTaskConfig]:
        """Find task and its group by task name. Serialize result to Config objects.

        Raise TaskDisabledError if task or its group is disabled

        :param course_name: course name
        :param task_name: task name

        :return: pair of ManytaskGroupConfig and ManytaskTaskConfig objects
        """

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
            try:
                task = self._get_task_by_name_and_course_id(session, task_name, course.id)
            except NoResultFound:
                raise KeyError(f"Task {task_name} not found")

            if not task.enabled:
                raise TaskDisabledError(f"Task {task_name} is disabled")
            if not task.group.enabled:
                raise TaskDisabledError(f"Task {task_name} group {task.group.name} is disabled")

            group = task.group
            group_tasks = group.tasks.all()
            group_deadlines = group.deadline

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

        return group_config, task_config

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
            course = self._get(session, models.Course, name=course_name)

            query = (
                session.query(models.TaskGroup).join(models.Deadline).filter(models.TaskGroup.course_id == course.id)
            )

            if enabled is not None:
                query = query.filter(models.TaskGroup.enabled == enabled)

            if started is not None:
                if started:
                    query = query.filter(now >= models.Deadline.start)
                else:
                    query = query.filter(now < models.Deadline.start)

            groups = query.order_by(models.TaskGroup.position).all()

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
            course = self._get(session, models.Course, name=course_name)
            user = self._get(session, models.User, username=username)
            user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
            if course_admin != user_on_course.is_course_admin and course_admin:
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
            course = self._get(session, models.Course, name=course_name)
            user = self._get(session, models.User, username=username)
            try:
                self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
                return True
            except Exception:
                return False

    def create_user_if_not_exist(self, username: str, first_name: str, last_name: str, rms_id: int) -> None:
        """Create user in DB if not exist"""

        with self._session_create() as session:
            self._get_or_create(
                session,
                models.User,
                defaults=dict(
                    first_name=first_name,
                    rms_id=rms_id,
                    last_name=last_name,
                ),
                username=username,
            )
            session.commit()

    def get_user_courses_names_with_statuses(self, username: str) -> list[tuple[str, CourseStatus]]:
        """Get a list of courses names that the user participates in"""

        with self._session_create() as session:
            try:
                user = self._get(session, models.User, username=username)
            except NoResultFound:
                return []

            hidden_for_user = [CourseStatus.CREATED, CourseStatus.HIDDEN]
            user_on_courses = user.users_on_courses.filter(models.Course.status.notin_(hidden_for_user)).all()

            result = [(user_on_course.course.name, user_on_course.course.status) for user_on_course in user_on_courses]
            return result

    def get_all_courses_names_with_statuses(self) -> list[tuple[str, CourseStatus]]:
        """Get a list of all courses names"""

        with self._session_create() as session:
            courses = session.query(models.Course).all()

            result = [(course.name, course.status) for course in courses]
            return result

    def get_all_users(self) -> list[StoredUser]:
        """Get all users from the database

        :return: list of all users
        """
        with self._session_create() as session:
            users = session.query(models.User).all()
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
        with self._session_create() as session:
            try:
                if not is_admin:
                    admin_count = session.query(func.count()).filter(models.User.is_instance_admin.is_(True)).scalar()
                    if admin_count <= 1:
                        logger.error("Cannot remove the last admin")
                        return

                self._update(session, models.User, defaults={"is_instance_admin": is_admin}, username=username)

            except NoResultFound:
                logger.error(f"User {username} not found in the database")

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
                    logger.info(f"Updated user {username} profile: {', '.join(changes)}")
            except NoResultFound:
                logger.error(f"User {username} not found in the database")

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

            session.commit()

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

        logger.info("Syncing course in database...")
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
            session.commit()

    def _sync_grades_config(self, course_name: str, grades_config: ManytaskFinalGradeConfig | None) -> None:
        if grades_config is None:
            return

        with self._session_create() as session:
            course = self._get(session, models.Course, name=course_name)
            existing_complex_formulas = session.query(models.ComplexFormula).filter_by(course_id=course.id).all()

            existing_complex_formulas_grades = set(
                complex_formula.grade for complex_formula in existing_complex_formulas
            )
            config_complex_formulas_grades = set(grades_config.grades.keys())

            # add new grades
            for grade in config_complex_formulas_grades - existing_complex_formulas_grades:
                complex_formula = self._update_or_create(
                    session, models.ComplexFormula, grade=grade, course_id=course.id
                )

                for primary_formula in grades_config.grades[grade]:
                    primary_formula_dict = {str(k): v for k, v in primary_formula.items()}
                    self._create(
                        session,
                        models.PrimaryFormula,
                        primary_formula=primary_formula_dict,
                        complex_id=complex_formula.id,
                    )

            # remove deleted grafes
            for grade in existing_complex_formulas_grades - config_complex_formulas_grades:
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

                    session.query(models.PrimaryFormula).filter_by(
                        complex_id=complex_formula.id,
                        primary_formula=formula_dict,
                    ).delete()

                # add new primary formulas
                for formula in new_primary_formulas_set - existing_primary_formulas_set:
                    formula_dict = dict()
                    for k, v in formula:
                        formula_dict[k] = v

                    self._create(
                        session,
                        models.PrimaryFormula,
                        primary_formula=formula_dict,
                        complex_id=complex_formula.id,
                    )

            session.commit()

    def _check_pending_migrations(self, database_url: str) -> bool:
        alembic_cfg = Config(self.DEFAULT_ALEMBIC_PATH, config_args={"sqlalchemy.url": database_url})

        with self.engine.begin() as connection:
            alembic_cfg.attributes["connection"] = connection

            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

            script = ScriptDirectory.from_config(alembic_cfg)
            head_rev = script.get_current_head()

            if current_rev == head_rev:
                return False

            return True

    def _apply_migrations(self, database_url: str) -> None:
        alembic_cfg = Config(self.DEFAULT_ALEMBIC_PATH, config_args={"sqlalchemy.url": database_url})

        try:
            with self.engine.begin() as connection:
                alembic_cfg.attributes["connection"] = connection
                command.upgrade(alembic_cfg, "head")  # models.Base.metadata.create_all(self.engine)
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

        grades = self._get_all_grades(user_on_course, enabled=enabled, started=started, only_bonus=only_bonus)
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
            return session.query(model).filter_by(**kwargs).one()
        except NoResultFound:
            raise NoResultFound(f"{model} not found with params: {kwargs}")

    @staticmethod
    def _update(
        session: Session,
        model: Type[ModelType],
        defaults: Optional[dict[str, Any]] = None,  # params for update
        **kwargs: Any,  # params for get
    ) -> ModelType:
        instance = DataBaseApi._get(session, model, **kwargs)

        if defaults:
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
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
            return instance
        except IntegrityError:
            session.rollback()
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
            new_instance = model(**kwargs)
            session.add(new_instance)
            session.flush()
            return new_instance
        except IntegrityError:
            session.rollback()
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
            raise

    @staticmethod
    def _get_task_by_name_and_course_id(session: Session, name: str, course_id: int) -> models.Task:
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
        else:
            DataBaseApi._update(
                session,
                models.Deadline,
                defaults={"start": deadline_start, "steps": deadline_steps, "end": deadline_end},
                id=task_group.deadline.id,
            )

    def _get_all_grades(
        self,
        user_on_course: models.UserOnCourse,
        enabled: bool | None = None,
        started: bool | None = None,
        only_bonus: bool = False,
    ) -> Iterable["models.Grade"]:
        query = user_on_course.grades.join(models.Task).join(models.TaskGroup).join(models.Deadline)

        if enabled is not None:
            query = query.filter(and_(models.Task.enabled == enabled, models.TaskGroup.enabled == enabled))

        if started is not None:
            if started:
                query = query.filter(self.get_now_with_timezone(user_on_course.course.name) >= models.Deadline.start)
            else:
                query = query.filter(self.get_now_with_timezone(user_on_course.course.name) < models.Deadline.start)

        if only_bonus:
            query = query.filter(models.Task.is_bonus)

        return query.all()

    @staticmethod
    def _get_all_users_on_course(
        session: Session,
        course_name: str,
    ) -> Iterable["models.User"]:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        return [user_on_course.user for user_on_course in course.users_on_courses.all()]

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
        )

        if enabled is not None:
            query = query.filter(and_(models.Task.enabled == enabled, models.TaskGroup.enabled == enabled))

        if is_bonus is not None:
            query = query.filter(and_(models.Task.is_bonus == is_bonus))

        if started is not None:
            if started:
                query = query.filter(self.get_now_with_timezone(course_name) >= models.Deadline.start)
            else:
                query = query.filter(self.get_now_with_timezone(course_name) < models.Deadline.start)

        return query.all()

    @staticmethod
    def _get_course_users_on_courses_count(
        session: Session,
        course_name: str,
    ) -> int:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        return session.query(func.count(models.UserOnCourse.id)).filter_by(course_id=course.id).one()[0]

    @staticmethod
    def _get_task_submits_count(
        session: Session,
        task_id: int,
    ) -> int:
        return (
            session.query(func.count(models.Grade.id))
            .filter(and_(models.Grade.task_id == task_id, models.Grade.score > 0))
            .one()[0]
        )

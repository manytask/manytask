import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Type, TypeVar, cast

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from psycopg2.errors import DuplicateColumn, DuplicateTable, UniqueViolation
from sqlalchemy import and_, create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound, ProgrammingError
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import func

from . import models
from .abstract import Role, StorageApi, StoredUser, ViewerApi
from .config import ManytaskConfig, ManytaskDeadlinesConfig
from .glab import Student

ModelType = TypeVar("ModelType", bound=models.Base)

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Configuration for Database connection and settings."""

    database_url: str
    course_name: str
    unique_course_name: str
    gitlab_instance_host: str
    registration_secret: str
    token: str
    show_allscores: bool
    gitlab_admin_token: str
    gitlab_course_group: str
    gitlab_course_public_repo: str
    gitlab_course_students_group: str
    gitlab_default_branch: str
    gitlab_client_id: str
    gitlab_client_secret: str
    apply_migrations: bool = False


class DataBaseApi(ViewerApi, StorageApi):
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
        self.course_name = config.course_name
        self.unique_course_name = config.unique_course_name
        self.gitlab_instance_host = config.gitlab_instance_host
        self.registration_secret = config.registration_secret
        self.token = config.token
        self.show_allscores = config.show_allscores
        self.gitlab_admin_token = config.gitlab_admin_token
        self.gitlab_course_group = config.gitlab_course_group
        self.gitlab_course_public_repo = config.gitlab_course_public_repo
        self.gitlab_course_students_group = config.gitlab_course_students_group
        self.gitlab_default_branch = config.gitlab_default_branch
        self.gitlab_client_id = config.gitlab_client_id
        self.gitlab_client_secret = config.gitlab_client_secret
        self.apply_migrations = config.apply_migrations

        self.engine = create_engine(self.database_url, echo=False)

        if self._check_pending_migrations(self.database_url):
            if self.apply_migrations:
                self._apply_migrations(self.database_url)
            else:
                logger.error("There are pending migrations that have not been applied")

        if self.unique_course_name:
            with Session(self.engine) as session:
                try:
                    course = self._get(session, models.Course, unique_course_name=self.unique_course_name)

                    if course.gitlab_instance_host != self.gitlab_instance_host:
                        raise AttributeError("Can't update gitlab_instance_host param on created course")

                    if self.registration_secret and course.registration_secret != self.registration_secret:
                        course.registration_secret = self.registration_secret
                        session.commit()

                    if isinstance(self.show_allscores, bool) and course.show_allscores != self.show_allscores:
                        course.show_allscores = self.show_allscores
                        session.commit()

                except NoResultFound:
                    if all(
                        [
                            self.gitlab_instance_host,
                            self.registration_secret,
                            self.token,
                            self.gitlab_admin_token,
                            self.gitlab_course_group,
                            self.gitlab_course_public_repo,
                            self.gitlab_course_students_group,
                            self.gitlab_default_branch,
                            self.gitlab_client_id,
                            self.gitlab_client_secret,
                        ]
                    ):
                        self._create(
                            session,
                            models.Course,
                            name=self.course_name,
                            unique_course_name=self.unique_course_name,
                            gitlab_instance_host=self.gitlab_instance_host,
                            registration_secret=self.registration_secret,
                            token=self.token,
                            show_allscores=self.show_allscores,
                            gitlab_admin_token=self.gitlab_admin_token,
                            gitlab_course_group=self.gitlab_course_group,
                            gitlab_course_public_repo=self.gitlab_course_public_repo,
                            gitlab_course_students_group=self.gitlab_course_students_group,
                            gitlab_default_branch=self.gitlab_default_branch,
                            gitlab_client_id=self.gitlab_client_id,
                            gitlab_client_secret=self.gitlab_client_secret,
                        )
                        session.commit()

    def get_scoreboard_url(self) -> str:
        return ""

    def get_scores(
        self,
        username: str,
    ) -> dict[str, int]:
        """Method for getting all user scores

        :param username: student username

        :return: dict with the names of tasks and their scores
        """

        with Session(self.engine) as session:
            grades = self._get_scores(session, username, only_bonus=False)

            if grades is None:
                return {}

            scores: dict[str, int] = {}
            for grade in grades:
                scores[grade.task.name] = grade.score

        return scores

    def get_bonus_score(
        self,
        username: str,
    ) -> int:
        """Method for getting user's total bonus score

        :param username: student username

        :return: user's total bonus score
        """

        with Session(self.engine) as session:
            grades = self._get_scores(session, username, only_bonus=True)

        if grades is None:
            return 0

        return sum([grade.score for grade in grades])

    def get_stored_user(
        self,
        student: Student,
    ) -> StoredUser:
        """Method for getting user's stored data

        :param student: Student object

        :return: created or received StoredUser object
        """

        with Session(self.engine) as session:
            course = self._get(session, models.Course, name=self.course_name)
            user_on_course = self._get_or_create_user_on_course(session, student, course)
            session.commit()

            return StoredUser(
                username=user_on_course.user.username,
                role=Role(user_on_course.role),
                course_admin=user_on_course.is_course_admin,
            )

    def sync_stored_user(
        self,
        student: Student,
        is_registration: bool = False,
    ) -> StoredUser:
        """Method for sync user's gitlab and stored data

        :param student: Student object
        :param is_registration: Whether this is a new user registration

        :return: created or updated StoredUser object
        """

        with Session(self.engine) as session:
            course = self._get(session, models.Course, name=self.course_name)
            user_on_course = self._get_or_create_user_on_course(session, student, course)

            if student.course_admin:
                user_on_course.role = models.Role.ADMIN
                user_on_course.is_course_admin = True  # Keep for backward compatibility
            elif is_registration:
                user_on_course.role = models.Role.STUDENT
                user_on_course.is_course_admin = False

            if user_on_course.repo_name != student.repo and student.repo is not None:
                user_on_course.repo_name = student.repo
                session.flush()

            session.commit()

            stored_user = StoredUser(
                username=user_on_course.user.username,
                role=Role(user_on_course.role),
                course_admin=user_on_course.is_course_admin,  # Keep for backward compatibility
            )

            return stored_user

    def set_user_role(
        self,
        username: str,
        role: Role,
    ) -> StoredUser:
        with Session(self.engine) as session:
            course = self._get(session, models.Course, name=self.course_name)
            user = self._get(session, models.User, username=username, gitlab_instance_host=course.gitlab_instance_host)
            user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)

            user_on_course.role = models.Role(role.value)
            if role == Role.ADMIN:
                user_on_course.is_course_admin = True
            elif role != Role.ADMIN and user_on_course.is_course_admin:
                user_on_course.is_course_admin = False

            session.commit()

            return StoredUser(
                username=user_on_course.user.username,
                role=Role(user_on_course.role.value),
                course_admin=user_on_course.is_course_admin,
            )

    def get_users_by_role(
        self,
        role: Role,
    ) -> list[StoredUser]:
        with Session(self.engine) as session:
            course = self._get(session, models.Course, name=self.course_name)
            users_on_course = (
                session.query(models.UserOnCourse)
                .filter(models.UserOnCourse.course_id == course.id)
                .filter(models.UserOnCourse.role == models.Role(role.value))
                .all()
            )

            return [
                StoredUser(
                    username=user_on_course.user.username,
                    role=Role(user_on_course.role.value),
                    course_admin=user_on_course.is_course_admin,
                )
                for user_on_course in users_on_course
            ]

    def get_all_scores(self) -> dict[str, dict[str, int]]:
        """Method for getting all scores for all users

        :return: dict with usernames and all their scores
        """

        with Session(self.engine) as session:
            all_users = self._get_all_users(session, self.course_name)

        all_scores: dict[str, dict[str, int]] = {}
        for username in all_users:
            all_scores[username] = self.get_scores(username)

        return all_scores

    def get_stats(self) -> dict[str, float]:
        """Method for getting stats of all tasks

        :return: dict with the names of tasks and their stats
        """

        with Session(self.engine) as session:
            tasks = self._get_all_tasks(session, self.course_name)

            users_on_courses_count = self._get_course_users_on_courses_count(session, self.course_name)
            tasks_stats: dict[str, float] = {}
            for task in tasks:
                if users_on_courses_count == 0:
                    tasks_stats[task.name] = 0
                else:
                    tasks_stats[task.name] = self._get_task_submits_count(session, task.id) / users_on_courses_count

        return tasks_stats

    def get_scores_update_timestamp(self) -> str:
        """Method(deprecated) for getting last cached scores update timestamp

        :return: last update timestamp
        """

        return datetime.now(timezone.utc).isoformat()

    def update_cached_scores(self) -> None:
        """Method(deprecated) for updating cached scores"""

        return

    def store_score(
        self,
        student: Student,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int:
        """Method for storing user's task score

        :param student: Student object
        :param task_name: task name
        :param update_fn: function for updating the score

        :return: saved score
        """

        # TODO: in GoogleDocApi imported from google table, they used to increase the deadline for the user
        # flags = ''

        with Session(self.engine) as session:
            try:
                course = self._get(session, models.Course, name=self.course_name)

                user_on_course = self._get_or_create_user_on_course(session, student, course)
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
                return new_score

            except Exception:
                session.rollback()
                raise

    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        """Method for updating deadlines config

        :param deadlines_config: ManytaskDeadlinesConfig object
        """

        groups = deadlines_config.get_groups(enabled=True, started=True)
        tasks = deadlines_config.get_tasks(enabled=True, started=True)

        logger.info("Syncing database tasks...")
        with Session(self.engine) as session:
            course = self._get(session, models.Course, unique_course_name=self.unique_course_name)

            for group in groups:
                exist_tasks = [task for task in group.tasks if task in tasks]

                if len(exist_tasks) == 0:
                    continue

                deadline_data = DataBaseApi._serialize_deadline_data(group.start, group.steps, group.end)

                task_group = DataBaseApi._get_or_create(session, models.TaskGroup, name=group.name, course_id=course.id)

                DataBaseApi._update_deadline_for_task_group(session, task_group, deadline_data)

                for task in exist_tasks:
                    self._update_or_create(
                        session,
                        models.Task,
                        defaults={"is_bonus": task.is_bonus},
                        name=task.name,
                        group_id=task_group.id,
                    )
            session.commit()

    def get_course(
        self,
        course_name: str,
    ) -> models.Course | None:
        try:
            with Session(self.engine) as session:
                return self._get(session, models.Course, name=course_name)
        except NoResultFound:
            return None

    def get_course_by_unique_name(
        self,
        unique_course_name: str,
    ) -> models.Course | None:
        try:
            with Session(self.engine) as session:
                return self._get(session, models.Course, unique_course_name=unique_course_name)
        except NoResultFound:
            return None

    def create_course(
        self,
        config: "ManytaskConfig",
    ) -> None:
        with Session(self.engine) as session:
            try:
                self._create(
                    session,
                    models.Course,
                    name=config.settings.course_name,
                    unique_course_name=config.settings.unique_course_name,
                    gitlab_instance_host=str(config.settings.gitlab_base_url),
                    registration_secret=config.settings.registration_secret,
                    token=config.settings.token,
                    show_allscores=config.settings.show_allscores,
                    gitlab_admin_token=config.settings.gitlab_admin_token,
                    gitlab_course_group=config.settings.gitlab_course_group,
                    gitlab_course_public_repo=config.settings.gitlab_course_public_repo,
                    gitlab_course_students_group=config.settings.gitlab_course_students_group,
                    gitlab_default_branch=config.settings.gitlab_default_branch,
                    gitlab_client_id=config.settings.gitlab_client_id,
                    gitlab_client_secret=config.settings.gitlab_client_secret,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def update_task_groups_from_config(
        self,
        config_data: dict[str, Any],
    ) -> None:
        """Update task groups based on new config data.

        This method:
        1. Finds tasks that need to be moved to different groups
        2. Creates any missing groups
        3. Updates task group assignments

        :param config_data: Raw config data from yaml
        """
        with Session(self.engine) as session:
            if "settings" not in config_data:
                config_data["settings"] = {}

            settings = config_data["settings"]
            if "course_name" not in settings:
                course = self._get(session, models.Course, unique_course_name=self.unique_course_name)
                settings["course_name"] = course.name

            new_config = ManytaskConfig(**config_data)

            new_task_names = set()
            new_task_to_group = {}
            for group in new_config.deadlines.get_groups(enabled=True, started=True):
                for task_config in group.tasks:
                    if task_config.enabled:
                        new_task_names.add(task_config.name)
                        new_task_to_group[task_config.name] = group.name

            existing_tasks = session.query(models.Task).join(models.TaskGroup).all()

            # Check for duplicates (name + course)
            tasks_to_update = {}
            for existing_task in existing_tasks:
                if existing_task.name in new_task_names:
                    task_group = existing_task.group
                    task_course = task_group.course

                    if task_course.unique_course_name == self.unique_course_name:
                        new_group_name = new_task_to_group[existing_task.name]
                        if task_group.name != new_group_name:
                            tasks_to_update[existing_task.id] = new_group_name

            # Create any missing groups
            course = self._get(session, models.Course, unique_course_name=self.unique_course_name)
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

    def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool:
        """Sync admin flag in gitlab and db"""

        with Session(self.engine) as session:
            course = self._get(session, models.Course, name=course_name)
            user = self._get(
                session, models.User, username=student.username, gitlab_instance_host=course.gitlab_instance_host
            )
            user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
            if student.course_admin != user_on_course.is_course_admin and student.course_admin:
                user_on_course = self._update(
                    session=session,
                    model=models.UserOnCourse,
                    defaults={"is_course_admin": student.course_admin},
                    user_id=user.id,
                    course_id=course.id,
                )
                session.refresh(user_on_course)
            return user_on_course.is_course_admin

    def check_user_on_course(self, course_name: str, student: Student) -> bool:
        """Checking that user has been enrolled on course"""
        with Session(self.engine) as session:
            try:
                course = self._get(session, models.Course, name=course_name)
                user = self._get(
                    session, models.User, username=student.username, gitlab_instance_host=course.gitlab_instance_host
                )
                self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
                return True
            except Exception:
                return False

    def get_or_create_user(self, student: Student, course_name: str) -> models.User:
        """Get user in DB or create if not"""

        with Session(self.engine) as session:
            course = self._get(session, models.Course, name=course_name)
            user = self._get_or_create(
                session, models.User, username=student.username, gitlab_instance_host=course.gitlab_instance_host
            )
            session.commit()
            session.refresh(user)

        return user

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
        self, session: Session, student: Student, course: models.Course
    ) -> models.UserOnCourse:
        user = self._get_or_create(
            session, models.User, username=student.username, gitlab_instance_host=course.gitlab_instance_host
        )

        try:
            user_on_course = self._get(
                session,
                models.UserOnCourse,
                user_id=user.id,
                course_id=course.id,
            )
            if user_on_course.repo_name != student.repo and student.repo is not None:
                user_on_course.repo_name = student.repo
                session.flush()

            return user_on_course

        except NoResultFound:
            initial_role = models.Role.ADMIN if student.course_admin else models.Role.STUDENT
            user_on_course = models.UserOnCourse(
                user_id=user.id,
                course_id=course.id,
                repo_name=student.repo,
                role=initial_role,
                is_course_admin=student.course_admin,
            )
            session.add(user_on_course)
            session.flush()

            return user_on_course

    def _get_scores(
        self, session: Session, username: str, only_bonus: bool = False
    ) -> Optional[Iterable["models.Grade"]]:
        try:
            course = self._get(session, models.Course, name=self.course_name)
            user = self._get(session, models.User, username=username, gitlab_instance_host=course.gitlab_instance_host)

            user_on_course = self._get(session, models.UserOnCourse, user_id=user.id, course_id=course.id)
        except NoResultFound:
            return None

        grades = self._get_all_grades(user_on_course, only_bonus=only_bonus)
        return grades

    @staticmethod
    def _serialize_deadline_data(  # serialize data to json from config.ManytaskGroupConfig params
        start: datetime, steps: dict[float, datetime | timedelta], end: datetime | timedelta
    ) -> dict[str, str | dict[str, str]]:
        def convert(value: datetime | timedelta) -> str:
            if isinstance(value, datetime):
                return value.isoformat()
            return (start + value).isoformat()

        serialized: dict[str, str | dict[str, str]] = {
            "start": convert(start),
            "steps": {str(k): convert(v) for k, v in steps.items()},
            "end": convert(end),
        }

        return serialized

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
            return DataBaseApi._create_or_update_instance(session, model, instance, defaults, **kwargs)
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
        task = (
            session.query(models.Task).filter_by(name=name).join(models.TaskGroup).filter_by(course_id=course_id).one()
        )
        return task

    @staticmethod
    def _update_deadline_for_task_group(
        session: Session,
        task_group: models.TaskGroup,
        deadline_data: dict[Any, Any],  # json data
    ) -> None:
        if task_group.deadline_id is None:
            deadline = DataBaseApi._create(session, models.Deadline, data=deadline_data)
            DataBaseApi._update(session, models.TaskGroup, defaults={"deadline_id": deadline.id}, id=task_group.id)
        else:
            DataBaseApi._update(session, models.Deadline, defaults={"data": deadline_data}, id=task_group.deadline.id)

    @staticmethod
    def _get_all_grades(user_on_course: models.UserOnCourse, only_bonus: bool = False) -> Iterable["models.Grade"]:
        if only_bonus:
            return user_on_course.grades.join(models.Task).filter_by(is_bonus=True).all()
        return user_on_course.grades.all()

    @staticmethod
    def _get_all_users(
        session: Session,
        course_name: str,
    ) -> Iterable[str]:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        return [user_on_course.user.username for user_on_course in course.users_on_courses.all()]

    @staticmethod
    def _get_all_tasks(
        session: Session,
        course_name: str,
    ) -> Iterable["models.Task"]:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        return session.query(models.Task).join(models.TaskGroup).filter(models.TaskGroup.course_id == course.id).all()

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

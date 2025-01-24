import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional, Type, TypeVar, cast

from psycopg2.errors import UniqueViolation
from sqlalchemy import and_, create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import func

from . import models
from .abstract import StorageApi
from .config import ManytaskDeadlinesConfig
from .glab import Student


ModelType = TypeVar('ModelType', bound=models.Base)

logger = logging.getLogger(__name__)


class DataBaseApi(StorageApi):
    """Class for interacting with a database with the StorageApi functionality"""

    def __init__(
            self,
            database_url: str,
            course_name: str,
            gitlab_instance_host: str,
            registration_secret: str,
            show_allscores: bool,
            create_tables_if_not_exist: bool = False
    ):
        """Constructor of DataBaseApi class

        Creates a couse with specified parameters if it doesn't exist yet

        :param database_url: full url for database connection
        :param course_name: unique course name
        :param gitlab_instance_host: gitlab instance host url
        :param registration_secret: secret to registering for course
        :param show_allscores: flag for showing results to all users
        :param create_tables_if_not_exist: flag for creating database tables if they don't exist
        """

        self.engine = create_engine(database_url, echo=False)

        if create_tables_if_not_exist:
            self._create_tables()

        with Session(self.engine) as session:
            try:
                course = self._get(session, models.Course, name=course_name)
                if course.gitlab_instance_host != gitlab_instance_host:
                    raise AttributeError(
                        "Can't update gitlab_instance_host param on created course")
                course.registration_secret = registration_secret
                course.show_allscores = show_allscores
                session.commit()
            except NoResultFound:
                self._create(
                    session,
                    models.Course,
                    name=course_name,
                    gitlab_instance_host=gitlab_instance_host,
                    registration_secret=registration_secret,
                    show_allscores=show_allscores
                )
                session.commit()

            self.course_name = course_name

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

            users_on_courses_count = self._get_course_users_on_courses_count(
                session, self.course_name)
            tasks_stats: dict[str, float] = {}
            for task in tasks:
                if users_on_courses_count == 0:
                    tasks_stats[task.name] = 0
                else:
                    tasks_stats[task.name] = self._get_task_submits_count(
                        session, task.id) / users_on_courses_count

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
                # Always create user and user_on_course
                user = self._get_or_create(
                    session,
                    models.User,
                    username=student.username,
                    gitlab_instance_host=course.gitlab_instance_host
                )

                user_on_course = self._get_or_create(
                    session,
                    models.UserOnCourse,
                    defaults={'repo_name': student.repo},
                    user_id=user.id,
                    course_id=course.id
                )
                session.commit()

                try:
                    task = self._get_task_by_name_and_course_id(session, task_name, course.id)
                except NoResultFound:
                    return 0

                grade = self._get_or_create_sfu_grade(session, user_on_course.id, task.id)
                new_score = update_fn('', grade.score)
                grade.score = new_score
                grade.last_submit_date = datetime.now(timezone.utc)

                session.commit()
                logger.info(f"Setting score = {new_score}")
                return new_score

            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update score for {student.username} on {task_name}: {str(e)}")
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
            course = self._get(session, models.Course, name=self.course_name)

            for group in groups:
                exist_tasks = [task for task in group.tasks if task in tasks]

                if len(exist_tasks) == 0:
                    continue

                deadline_data = DataBaseApi._serialize_deadline_data(
                    group.start, group.steps, group.end)

                task_group = DataBaseApi._get_or_create(
                    session,
                    models.TaskGroup,
                    name=group.name,
                    course_id=course.id
                )

                DataBaseApi._update_deadline_for_task_group(session, task_group, deadline_data)

                for task in exist_tasks:
                    self._update_or_create(
                        session,
                        models.Task,
                        defaults={
                            'is_bonus': task.is_bonus
                        },
                        name=task.name,
                        group_id=task_group.id
                    )
            session.commit()

    def _create_tables(self) -> None:
        try:
            models.Base.metadata.create_all(self.engine)
        except IntegrityError as e:  # if tables are created concurrently
            if not isinstance(e.orig, UniqueViolation):
                raise

    def _get_scores(
            self,
            session: Session,
            username: str,
            only_bonus: bool = False
    ) -> Optional[Iterable['models.Grade']]:
        try:
            course = self._get(session, models.Course, name=self.course_name)
            user = self._get(
                session,
                models.User,
                username=username,
                gitlab_instance_host=course.gitlab_instance_host
            )

            user_on_course = self._get(
                session,
                models.UserOnCourse,
                user_id=user.id,
                course_id=course.id
            )
        except NoResultFound:
            return None

        grades = self._get_all_grades(user_on_course, only_bonus=only_bonus)
        return grades

    @staticmethod
    def _serialize_deadline_data(  # serialize data to json from config.ManytaskGroupConfig params
            start: datetime,
            steps: dict[float, datetime | timedelta],
            end: datetime | timedelta
    ) -> dict[str, str | dict[str, str]]:
        def convert(value: datetime | timedelta) -> str:
            if isinstance(value, datetime):
                return value.isoformat()
            return (start + value).isoformat()

        serialized: dict[str, str | dict[str, str]] = {
            'start': convert(start),
            'steps': {str(k): convert(v) for k, v in steps.items()},
            'end': convert(end)
        }

        return serialized

    @staticmethod
    def _get(
            session: Session,
            model: Type[ModelType],
            **kwargs: Any  # params for get
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
            **kwargs: Any  # params for get
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
            **kwargs: Any  # params for create
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
            session: Session,
            model: Type[ModelType],
            allow_none: bool = True,
            **kwargs: Any
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
            **kwargs: Any
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
            existing_instance = cast(ModelType,
                                     DataBaseApi._query_with_for_update(session, model, allow_none=False, **kwargs))
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
            **kwargs: Any  # params for get
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
            **kwargs: Any  # params for get
    ) -> ModelType:
        try:
            instance = DataBaseApi._query_with_for_update(session, model, **kwargs)
            return DataBaseApi._create_or_update_instance(
                session, model, instance, defaults, create_defaults, **kwargs)
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
                session,
                models.Grade,
                user_on_course_id=user_on_course_id,
                task_id=task_id
            )
            return DataBaseApi._create_or_update_instance(
                session,
                models.Grade,
                grade,
                create_defaults={'score': 0},
                user_on_course_id=user_on_course_id,
                task_id=task_id
            )
        except Exception:
            session.rollback()
            raise

    @staticmethod
    def _get_task_by_name_and_course_id(
            session: Session,
            name: str,
            course_id: int
    ) -> models.Task:
        return session.query(models.Task).filter_by(name=name).join(
            models.TaskGroup).filter_by(course_id=course_id).one()

    @staticmethod
    def _update_deadline_for_task_group(
            session: Session,
            task_group: models.TaskGroup,
            deadline_data: dict[Any, Any]  # json data
    ) -> None:

        if task_group.deadline_id is None:
            deadline = DataBaseApi._create(session, models.Deadline, data=deadline_data)
            DataBaseApi._update(
                session,
                models.TaskGroup,
                defaults={
                    'deadline_id': deadline.id
                },
                id=task_group.id
            )
        else:
            DataBaseApi._update(
                session,
                models.Deadline,
                defaults={
                    'data': deadline_data
                },
                id=task_group.deadline.id
            )

    @staticmethod
    def _get_all_grades(
            user_on_course: models.UserOnCourse,
            only_bonus: bool = False
    ) -> Iterable['models.Grade']:
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
    ) -> Iterable['models.Task']:
        course = DataBaseApi._get(session, models.Course, name=course_name)

        return session.query(models.Task).join(
            models.TaskGroup
        ).filter(
            models.TaskGroup.course_id == course.id
        ).all()

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
        return session.query(func.count(models.Grade.id)).filter(
            and_(models.Grade.task_id == task_id, models.Grade.score > 0)).one()[0]

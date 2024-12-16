import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, List, Optional, Type, TypeVar, Union

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, NoResultFound
from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import func

from . import models
from .abstract import StorageApi
from .config import ManytaskDeadlinesConfig
from .glab import Student


logger = logging.getLogger(__name__)


class DataBaseApi(StorageApi):
    T = TypeVar('T', bound=models.Base)

    def __init__(
        self,
        database_url: str,
        course_name: str,
        gitlab_instance_host: str,
        registration_secret: str,
        show_allscores: bool
    ):
        """
        :param database_url:
        :param course_name:
        :param gitlab_instance_host:
        :param registration_secret:
        :param show_allscores:
        """

        self.engine = create_engine(database_url, echo=False)

        with Session(self.engine) as session:
            try:
                course = self.get(session, models.Course, name=course_name)
                if course.gitlab_instance_host != gitlab_instance_host:
                    AttributeError("Can't update gitlab_instance_host param on created course")
            except NoResultFound:
                pass

            self.course_name = self.update_or_create(
                session,
                models.Course,
                defaults={
                    'gitlab_instance_host': gitlab_instance_host,
                    'registration_secret': registration_secret,
                    'show_allscores': show_allscores
                },
                name=course_name
            ).name

    def get_scores(
        self,
        username: str,
    ) -> dict[str, int]:
        with Session(self.engine) as session:
            try:
                course = self.get(session, models.Course, name=self.course_name)
                user = self.get(
                    session,
                    models.User,
                    username=username,
                    gitlab_instance_host=course.gitlab_instance_host
                )

                user_on_course = self.get(
                    session,
                    models.UserOnCourse,
                    user_id=user.id,
                    course_id=course.id
                )
            except NoResultFound:
                return {}

            grades = self.get_all_grades(user_on_course, only_bonus=False)

            scores: dict[str, int] = {}
            for grade in grades:
                scores[grade.task.name] = grade.score

        return scores

    def get_bonus_score(
        self,
        username: str,
    ) -> int:
        with Session(self.engine) as session:
            try:
                course = self.get(session, models.Course, name=self.course_name)
                user = self.get(
                    session,
                    models.User,
                    username=username,
                    gitlab_instance_host=course.gitlab_instance_host
                )

                user_on_course = self.get(
                    session,
                    models.UserOnCourse,
                    user_id=user.id,
                    course_id=course.id
                )
            except NoResultFound:
                return 0

            grades = self.get_all_grades(user_on_course, only_bonus=True)

        return sum([grade.score for grade in grades])

    def get_all_scores(self) -> dict[str, dict[str, int]]:
        with Session(self.engine) as session:
            all_users = self.get_all_users(session, self.course_name)

        all_scores: dict[str, dict[str, int]] = {}
        for username in all_users:
            all_scores[username] = self.get_scores(username)

        return all_scores

    def get_stats(self) -> dict[str, float]:
        with Session(self.engine) as session:
            tasks = self.get_all_tasks(session, self.course_name)

            users_on_courses_count = self.get_course_users_on_courses_count(
                session, self.course_name)
            tasks_stats: dict[str, float] = {}
            for task in tasks:
                if users_on_courses_count == 0:
                    tasks_stats[task.name] = 0
                else:
                    tasks_stats[task.name] = self.get_task_submits_count(
                        session, task.id) / users_on_courses_count

        return tasks_stats

    def get_scores_update_timestamp(self) -> str:
        return str(datetime.now(timezone.utc))

    def update_cached_scores(self) -> None:
        return None

    def store_score(
        self,
        student: Student,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int:
        flags = ''  # TODO: in GoogleDocApi imported from google table, they used to increase the deadline for the user

        with Session(self.engine) as session:
            course = self.get(session, models.Course, name=self.course_name)
            user = self.get_or_create(
                session,
                models.User,
                username=student.username,
                gitlab_instance_host=course.gitlab_instance_host
            )

            user_on_course = self.get_or_create(
                session,
                models.UserOnCourse,
                defaults={
                    'repo_name': student.repo
                },
                user_id=user.id,
                course_id=course.id
            )

            try:
                task = self.get_task_by_name_and_course_id(session, task_name, course.id)
            except NoResultFound:
                return 0

            grade = self.get_or_create(
                session,
                models.Grade,
                user_on_course_id=user_on_course.id,
                task_id=task.id
            )

            new_score = update_fn(flags, grade.score)
            self.update(
                session,
                models.Grade,
                defaults={
                    'score': new_score,
                    'last_submit_date': datetime.now(timezone.utc)
                },
                id=grade.id
            )

        logger.info(f"Setting score = {new_score}")

        return new_score

    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        groups = deadlines_config.get_groups(enabled=True, started=True)
        tasks = deadlines_config.get_tasks(enabled=True, started=True)

        logger.info("Syncing database tasks...")
        with Session(self.engine) as session:
            course = self.get(session, models.Course, name=self.course_name)

            for group in groups:
                exist_tasks = [task for task in group.tasks if task in tasks]

                if len(exist_tasks) == 0:
                    continue

                deadline_data = DataBaseApi.serialize_deadline_data(
                    group.start, group.steps, group.end)

                task_group = DataBaseApi.get_or_create(
                    session,
                    models.TaskGroup,
                    name=group.name,
                    course_id=course.id
                )

                DataBaseApi.update_deadline_for_task_group(session, task_group, deadline_data)

                for task in exist_tasks:
                    self.update_or_create(
                        session,
                        models.Task,
                        defaults={
                            'is_bonus': task.is_bonus
                        },
                        name=task.name,
                        group_id=task_group.id
                    )

    @staticmethod
    def serialize_deadline_data(
        start: datetime,
        steps: dict[float, Union[datetime, timedelta]],
        end: Union[datetime, timedelta]
    ) -> dict[str, Union[str, dict[str, str]]]:
        def convert(value: Union[datetime, timedelta]) -> str:
            if isinstance(value, datetime):
                return value.isoformat()
            return (start + value).isoformat()

        serialized: dict[str, Union[str, dict[str, str]]] = {
            'start': convert(start),
            'steps': {str(k): convert(v) for k, v in steps.items()},
            'end': convert(end)
        }

        return serialized

    @staticmethod
    def get(
        session: Session,
        model: Type[T],
        **kwargs: Any
    ) -> T:
        try:
            return session.query(model).filter_by(**kwargs).one()
        except NoResultFound:
            raise NoResultFound(f"{model} not found with params: {kwargs}")

    @staticmethod
    def update(
        session: Session,
        model: Type[T],
        defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any
    ) -> T:
        instance = DataBaseApi.get(session, model, **kwargs)

        if defaults:
            for key, value in defaults.items():
                setattr(instance, key, value)
            session.commit()
        return instance

    @staticmethod
    def create(
        session: Session,
        model: Type[T],
        **kwargs: Any
    ) -> T:
        try:
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
            return instance
        except IntegrityError:
            session.rollback()
            return session.query(model).filter_by(**kwargs).one()

    @staticmethod
    def get_or_create(
        session: Session,
        model: Type[T],
        defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any
    ) -> T:
        instance = session.query(model).filter_by(**kwargs).one_or_none()
        if instance:
            return instance

        if defaults is not None:
            kwargs.update(defaults)

        return DataBaseApi.create(session, model, **kwargs)

    @staticmethod
    def update_or_create(
        session: Session,
        model: Type[T],
        defaults: Optional[dict[str, Any]] = None,
        create_defaults: Optional[dict[str, Any]] = None,
        **kwargs: Any
    ) -> T:
        instance = session.query(model).filter_by(**kwargs).one_or_none()
        if instance:
            if defaults:
                for key, value in defaults.items():
                    setattr(instance, key, value)
                session.commit()
            return instance

        if defaults is not None:
            kwargs.update(defaults)
        if create_defaults is not None:
            kwargs.update(create_defaults)

        return DataBaseApi.create(session, model, **kwargs)

    @staticmethod
    def get_task_by_name_and_course_id(
        session: Session,
        name: str,
        course_id: int
    ) -> models.Task:
        return session.query(models.Task).filter_by(name=name).join(
            models.TaskGroup).filter_by(course_id=course_id).one()

    @staticmethod
    def update_deadline_for_task_group(
        session: Session,
        task_group: models.TaskGroup,
        deadline_data: dict[Any, Any]
    ) -> None:

        if task_group.deadline_id is None:
            deadline = DataBaseApi.create(session, models.Deadline, data=deadline_data)
            DataBaseApi.update(
                session,
                models.TaskGroup,
                defaults={
                    'deadline_id': deadline.id
                },
                id=task_group.id
            )
        else:
            DataBaseApi.update(
                session,
                models.Deadline,
                defaults={
                    'data': deadline_data
                },
                id=task_group.deadline.id
            )

    @staticmethod
    def get_all_grades(
        user_on_course: models.UserOnCourse,
        only_bonus: bool = False
    ) -> Iterable['models.Grade']:
        if only_bonus:
            return user_on_course.grades.join(models.Task).filter_by(is_bonus=True).all()
        return user_on_course.grades.all()

    @staticmethod
    def get_all_users(
        session: Session,
        course_name: str,
    ) -> Iterable[str]:
        course = DataBaseApi.get(session, models.Course, name=course_name)

        return [user_on_course.user.username for user_on_course in course.users_on_courses.all()]

    @staticmethod
    def get_all_tasks(
        session: Session,
        course_name: str,
    ) -> Iterable['models.Task']:
        course = DataBaseApi.get(session, models.Course, name=course_name)

        tasks: List['models.Task'] = []
        for task_group in course.task_groups.all():
            tasks.extend(task_group.tasks.all())

        return tasks

    @staticmethod
    def get_course_users_on_courses_count(
        session: Session,
        course_name: str,
    ) -> int:
        course = DataBaseApi.get(session, models.Course, name=course_name)

        return session.query(func.count(models.UserOnCourse.id)).filter_by(course_id=course.id).one()[0]

    @staticmethod
    def get_task_submits_count(
        session: Session,
        task_id: int,
    ) -> int:
        return session.query(func.count(models.Grade.id)).filter(
            models.Grade.task_id == task_id and models.Grade.score > 0).one()[0]

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from . import models
from .abstract import StorageApi
from .config import ManytaskDeadlinesConfig
from .glab import Student


logger = logging.getLogger(__name__)


class DataBaseApi(StorageApi):
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
            self.course_name = models.Course.update_or_create(
                session, course_name, gitlab_instance_host, registration_secret, show_allscores).name

    def get_scores(
        self,
        username: str,
    ) -> dict[str, int]:
        with Session(self.engine) as session:
            try:
                user_on_course_id = models.UserOnCourse.get_or_create(
                    session, username, self.course_name).id
            except NoResultFound:
                return {}

            grades = models.UserOnCourse.get_all_grades(
                session, user_on_course_id, only_bonus=False)

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
                user_on_course_id = models.UserOnCourse.get_or_create(
                    session, username, self.course_name).id
            except NoResultFound:
                return 0

            grades = models.UserOnCourse.get_all_grades(session, user_on_course_id, only_bonus=True)

        return sum([grade.score for grade in grades])

    def get_all_scores(self) -> dict[str, dict[str, int]]:
        with Session(self.engine) as session:
            all_users = models.Course.get_all_users(session, self.course_name)

        all_scores: dict[str, dict[str, int]] = {}
        for username in all_users:
            all_scores[username] = self.get_scores(username)

        return all_scores

    def get_stats(self) -> dict[str, float]:
        with Session(self.engine) as session:
            tasks = models.Course.get_all_tasks(session, self.course_name)

            users_on_courses_count = models.Course.get_users_on_courses_count(
                session, self.course_name)
            tasks_stats: dict[str, float] = {}
            for task in tasks:
                if users_on_courses_count == 0:
                    tasks_stats[task.name] = 0
                else:
                    tasks_stats[task.name] = models.Task.get_submits_count(
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
            user_on_course_id = models.UserOnCourse.get_or_create(
                session, student.username, self.course_name, student.repo, create_if_not_exist=True).id

            try:
                grade = models.Grade.get_or_create(
                    session, user_on_course_id, task_name, self.course_name)
            except NoResultFound:
                return 0
            new_score = update_fn(flags, grade.score)
            models.Grade.update(session, grade.id, new_score)
            logger.info(f"Setting score = {new_score}")

        return new_score

    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        groups = deadlines_config.get_groups(enabled=True, started=True)
        tasks = deadlines_config.get_tasks(enabled=True, started=True)
        task_name_to_group_index = {
            task.name: index for index in range(len(groups)) for task in groups[index].tasks if task in tasks}

        logger.info("Syncing database tasks...")
        with Session(self.engine) as session:
            for task in tasks:
                group = groups[task_name_to_group_index[task.name]]
                deadline_data = {
                    'start': group.start,
                    'steps': group.steps,
                    'end': group.end
                }
                models.Task.update_or_create(
                    session, task.name, task.is_bonus, group.name, self.course_name,
                    json.dumps(deadline_data, default=str)  # TODO: Not sure json.dumps is correct solution
                )

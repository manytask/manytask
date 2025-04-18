from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from cachelib import BaseCache
from pydantic import ValidationError

from . import abstract, glab, solutions
from .config import ManytaskConfig, ManytaskDeadlinesConfig

logger = logging.getLogger(__name__)
DEFAULT_TIMEZONE = ZoneInfo("Europe/Moscow")


def parse_time(time: str, tz: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    date = datetime.strptime(time, "%Y-%m-%d %H:%M")
    date = date.replace(tzinfo=tz)
    print("Got", time, "return", date)
    return date


def get_current_time(tz: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    return datetime.now(tz=tz)


def validate_submit_time(commit_time: datetime | None, current_time: datetime) -> datetime:
    """Check if commit_time 'to far' from current_time, use current_time, else use commit_time"""
    if not commit_time:
        return current_time

    if commit_time > current_time:
        print(f"WTF: commit_time {commit_time} > current_time {current_time}")
        return current_time

    return current_time


@dataclass
class CourseConfig:
    """Configuration for Course settings and APIs."""

    storage_api: abstract.StorageApi
    gitlab_api: glab.GitLabApi

    gitlab_course_group: str
    gitlab_course_public_repo: str
    gitlab_course_students_group: str
    gitlab_default_branch: str

    solutions_api: solutions.SolutionsApi
    registration_secret: str
    token: str
    show_allscores: bool
    cache: BaseCache
    manytask_version: str | None = None
    debug: bool = False


class Course:
    def __init__(
        self,
        config: CourseConfig,
    ):
        """Initialize Course with configuration.

        :param config: CourseConfig instance containing all necessary settings
        """
        self.storage_api = config.storage_api
        self.gitlab_api = config.gitlab_api

        self.__gitlab_course_group = config.gitlab_course_group
        self.__gitlab_course_public_repo = config.gitlab_course_public_repo
        self.__gitlab_course_students_group = config.gitlab_course_students_group
        self.__gitlab_default_branch = config.gitlab_default_branch

        self.solutions_api = config.solutions_api
        self.registration_secret = config.registration_secret
        self.token = config.token
        self.show_allscores = config.show_allscores
        self._cache = config.cache
        self.manytask_version = config.manytask_version
        self.debug = config.debug

    @property
    def gitlab_course_group(self) -> str:
        return self.__gitlab_course_group

    @property
    def gitlab_course_public_repo(self) -> str:
        return self.__gitlab_course_public_repo

    @property
    def gitlab_course_students_group(self) -> str:
        return self.__gitlab_course_students_group

    @property
    def gitlab_default_branch(self) -> str:
        return self.__gitlab_default_branch

    @property
    def favicon(self) -> str:
        return "favicon.ico"

    @property
    def name(self) -> str:
        if self.config:
            return self.config.settings.course_name
        else:
            return "not_ready"

    @property
    def deadlines_cache_time(self) -> datetime:
        return self._cache.get("__deadlines_cache_time__")

    @property
    def config(self) -> ManytaskConfig | None:  # noqa: F811
        logger.info("Fetching config...")
        content = self._cache.get("__config__")

        if content is None:
            logger.info("Config not found in cache")
            return None

        return ManytaskConfig(**content)

    def store_config(self, content: dict[str, Any]) -> None:
        # For validation purposes
        ManytaskConfig(**content)
        if "deadlines" not in content:
            raise ValidationError("Field required: deadlines")
        deadlines_config = ManytaskDeadlinesConfig(**content["deadlines"])

        # Update task groups (if necessary -- if there is an override) first
        self.storage_api.update_task_groups_from_config(deadlines_config)

        # Save deadlines to storage
        self.storage_api.sync_columns(deadlines_config)

        content_without_deadlines = {k: v for k, v in content.items() if k != "deadlines"}

        # Save config to cache
        self._cache.set("__config__", content_without_deadlines)

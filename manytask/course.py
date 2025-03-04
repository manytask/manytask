from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from cachelib import BaseCache
from sqlalchemy.orm import Session

from . import abstract, glab, solutions
from .config import ManytaskConfig, ManytaskDeadlinesConfig
from .models import Course

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

    viewer_api: abstract.ViewerApi
    storage_api: abstract.StorageApi
    gitlab_api: glab.GitLabApi
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
        self.viewer_api = config.viewer_api
        self.storage_api = config.storage_api
        self.gitlab_api = config.gitlab_api
        self.solutions_api = config.solutions_api
        self.registration_secret = config.registration_secret
        self.token = config.token
        self.show_allscores = config.show_allscores
        self._cache = config.cache
        self.manytask_version = config.manytask_version
        self.debug = config.debug

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
    def deadlines(self) -> ManytaskDeadlinesConfig:
        assert self.config is not None, "Config is not ready, we should never fetch deadlines without config"
        return self.config.deadlines

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
        config = ManytaskConfig(**content)
        
        if config.settings.course_name:
            course_data = self.storage_api.get_course_by_unique_name(config.settings.course_name)
            if course_data:
                with Session(self.storage_api.engine) as session:
                    course = session.query(Course).filter_by(unique_course_name=config.settings.course_name).one()
                    course.name = config.settings.course_name
                    course.gitlab_instance_host = config.settings.gitlab_base_url
                    session.commit()
                    logger.info(f"Updated course {config.settings.course_name} in database")
        
        self._cache.set("__config__", content)

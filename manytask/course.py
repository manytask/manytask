from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from cachelib import BaseCache

from .config import ManytaskConfig, ManytaskDeadlinesConfig


logger = logging.getLogger(__name__)
DEFAULT_TIMEZONE = ZoneInfo('Europe/Moscow')


def parse_time(time: str, tz: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    date = datetime.strptime(time, '%Y-%m-%d %H:%M')
    date = date.replace(tzinfo=tz)
    print('Got', time, 'return', date)
    return date


def get_current_time(tz: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    return datetime.now(tz=tz)


def validate_submit_time(commit_time: datetime | None, current_time: datetime) -> datetime:
    """Check if commit_time 'to far' from current_time, use current_time, else use commit_time"""
    if not commit_time:
        return current_time

    if commit_time > current_time:
        print(f'WTF: commit_time {commit_time} > current_time {current_time}')
        return current_time

    return current_time


from . import config, gdoc, glab, solutions  # noqa: E402, F401


class Course:
    def __init__(
            self,
            googledoc_api: gdoc.GoogleDocApi,
            gitlab_api: glab.GitLabApi,
            solutions_api: solutions.SolutionsApi,
            registration_secret: str,
            cache: BaseCache,
            manytask_version: str | None = None,
            *,
            debug: bool = False,
    ):
        self.googledoc_api = googledoc_api
        self.gitlab_api = gitlab_api
        self.solutions_api = solutions_api

        self.registration_secret = registration_secret

        self._cache = cache

        self.manytask_version = manytask_version
        self.debug = debug

    @property
    def favicon(self) -> str:
        return 'favicon.ico'

    @property
    def name(self) -> str:
        if self.config:
            return self.config.settings.course_name
        else:
            return 'not_ready'

    @property
    def deadlines(self) -> ManytaskDeadlinesConfig:
        return self.config.deadlines

    @property
    def config(self) -> ManytaskConfig:  # noqa: F811
        logger.info('Fetching config...')
        content = self._cache.get('__config__')

        assert content is not None, 'Course config is not set'
        return ManytaskConfig(**content)

    def store_config(self, content: dict[str, Any]) -> None:
        # For validation purposes
        ManytaskConfig(**content)
        self._cache.set('__config__', content)

    @property
    def rating_table(self) -> 'gdoc.RatingTable':
        return self.googledoc_api.fetch_rating_table()

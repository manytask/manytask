from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from cachelib import BaseCache

from .config import CourseConfig


logger = logging.getLogger(__name__)
MOSCOW_TIMEZONE = ZoneInfo('Europe/Moscow')
CONFIDENCE_INTERVAL = timedelta(minutes=10)


def parse_time(time: str) -> datetime:
    date = datetime.strptime(time, '%d-%m-%Y %H:%M')
    return date.replace(tzinfo=MOSCOW_TIMEZONE)


def get_current_time() -> datetime:
    return datetime.now(tz=MOSCOW_TIMEZONE)


def validate_commit_time(commit_time: datetime | None, current_time: datetime) -> datetime:
    """Check if commit_time 'to far' from current_time, use current_time, else use commit_time"""
    if not commit_time:
        return current_time

    if commit_time > current_time:
        print(f'WTF: commit_time {commit_time} > current_time {current_time}')
        return current_time

    if current_time - CONFIDENCE_INTERVAL < commit_time < current_time:
        return commit_time

    return current_time


class Task:
    def __init__(
            self,
            name: str,
            score: int,
            tags: list[str],
            start: str,
            deadline: str,
            second_deadline: str,
            scoring_func: str,
            url: str | None,
            is_bonus: bool
    ):
        self.name = name
        self.score = score
        self.tags = tags
        self.start = parse_time(start)
        self.deadline = parse_time(deadline)
        self.second_deadline = parse_time(second_deadline)
        self.scoring_func = scoring_func
        self.url = url
        self.is_bonus = is_bonus

    def is_started(self) -> bool:
        return get_current_time() > self.start

    def is_overdue(self, extra_time: timedelta = timedelta(), submit_time: datetime | None = None) -> bool:
        submit_time = submit_time or get_current_time()
        return submit_time - extra_time > self.deadline

    def is_overdue_second(self, extra_time: timedelta = timedelta(), submit_time: datetime | None = None) -> bool:
        submit_time = submit_time or get_current_time()
        return submit_time - extra_time > self.second_deadline


class Group:
    def __init__(
            self, name: str, start: str, deadline: str, second_deadline: str, tasks: list[Task], special: bool = False, hw: bool = False
    ):
        self.name = name
        self.start = parse_time(start)
        self.deadline = parse_time(deadline)
        self.second_deadline = parse_time(second_deadline)
        self.pretty_deadline = deadline
        self.pretty_second_deadline = second_deadline
        self.tasks = tasks
        self.special = special
        self.hw = special
        if hw:
            logger.warning('hw is deprecated, use special instead')
            self.special = hw

    @property
    def is_open(self) -> bool:
        return get_current_time() > self.start


from . import deadlines, gdoc, glab, solutions  # noqa: E402, F401


class Course:
    def __init__(
            self,
            deadlines_api: 'deadlines.DeadlinesApi',
            googledoc_api: gdoc.GoogleDocApi,
            gitlab_api: glab.GitLabApi,
            solutions_api: solutions.SolutionsApi,
            registration_secret: str,
            cache: BaseCache,
            manytask_version: str | None = None,
            *,
            debug: bool = False,
    ):
        self.deadlines_api = deadlines_api
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
        if self.course_config:
            return self.course_config.name
        else:
            return 'not_ready'

    @property
    def deadlines(self) -> 'deadlines.Deadlines':  # noqa: F811
        return self.deadlines_api.fetch()

    @property
    def course_config(self) -> CourseConfig | None:
        logger.info('Fetching config...')
        content = self._cache.get('__config__')

        if not content:
            return None

        return CourseConfig(
            name=content['name'],
            deadlines=content['deadlines'],
            second_deadline_max=float(content['second_deadline_max']),
            max_low_demand_bonus=float(content['max_low_demand_bonus']),
            layout=content.get('layout', 'groups'),
            lms_url=content.get('lms_url', None),
            telegram_channel_invite=content.get('telegram_channel_invite', None),
            telegram_chat_invite=content.get('telegram_chat_invite', None),
        )

    def store_deadlines(self, content: list[dict[str, Any]]) -> None:
        self.deadlines_api.store(content)

    def store_course_config(self, content: dict[str, Any]) -> None:
        logger.info('Storing course config...')

        # TODO: make it better. read from git?
        if content.get('deadlines') != 'hard':
            raise RuntimeError('Only deadlines=hard available')

        # For validation purposes
        CourseConfig(
            name=content['name'],
            deadlines=content['deadlines'],
            second_deadline_max=float(content['second_deadline_max']),
            max_low_demand_bonus=float(content['max_low_demand_bonus']),
            lms_url=content.get('lms_url', None),
            telegram_channel_invite=content.get('telegram_channel_invite', None),
            telegram_chat_invite=content.get('telegram_chat_invite', None),
        )
        self._cache.set('__config__', content)

    @property
    def rating_table(self) -> 'gdoc.RatingTable':
        return self.googledoc_api.fetch_rating_table()

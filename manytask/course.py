from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


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
    ):
        self.name = name
        self.score = score
        self.tags = tags
        self.start = parse_time(start)
        self.deadline = parse_time(deadline)
        self.second_deadline = parse_time(second_deadline)
        self.scoring_func = scoring_func

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
            self, name: str, start: str, deadline: str, second_deadline: str, tasks: list[Task], hw: bool = False
    ):
        self.name = name
        self.start = parse_time(start)
        self.deadline = parse_time(deadline)
        self.second_deadline = parse_time(second_deadline)
        self.pretty_deadline = deadline
        self.pretty_second_deadline = second_deadline
        self.tasks = tasks
        self.hw = hw

    @property
    def is_open(self) -> bool:
        return get_current_time() > self.start


from . import deadlines, gdoc, glab  # noqa: E402, F401


class Course:
    def __init__(
            self,
            deadlines_api: 'deadlines.DeadlinesApi',
            googledoc_api: gdoc.GoogleDocApi,
            gitlab_api: glab.GitLabApi,
            registration_secret: str,
            lms_url: str,
            tg_invite_link: str,
            course_name: str | None = None,
            deadlines_style: str = 'hard',
            second_deadline_formula: float = 0.5,
            max_demand_multiplier: float = 1.1,
            *,
            debug: bool = False,
    ):
        self.deadlines_api = deadlines_api
        self.googledoc_api = googledoc_api
        self.gitlab_api = gitlab_api
        self.registration_secret = registration_secret
        self.lms_url = lms_url
        self.tg_invite_link = tg_invite_link
        self.course_name = course_name or 'manytask'
        self.deadlines_style = deadlines_style
        self.second_deadline_formula = second_deadline_formula
        self.max_demand_multiplier = max_demand_multiplier

        self.debug = debug

    @property
    def favicon(self) -> str:
        return 'favicon.ico'

    @property
    def name(self) -> str:
        return self.course_name

    @property
    def deadlines(self) -> 'deadlines.Deadlines':
        return self.deadlines_api.fetch()

    def store_deadlines(self, content: list[dict[str, Any]]) -> None:
        self.deadlines_api.store(content)

    @property
    def rating_table(self) -> 'gdoc.RatingTable':
        return self.googledoc_api.fetch_rating_table()

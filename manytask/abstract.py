from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .config import (
    ManytaskDeadlinesConfig,
    ManytaskGroupConfig,
    ManytaskSettingsConfig,
    ManytaskTaskConfig,
    ManytaskUiConfig,
)
from .course import Course
from .glab import Student


@dataclass
class StoredUser:
    username: str
    course_admin: bool = False
    # we can add more fields that we store

    def __repr__(self) -> str:
        return f"StoredUser(username={self.username})"


class StorageApi(ABC):
    @abstractmethod
    def get_scores(
        self,
        course_name: str,
        username: str,
    ) -> dict[str, int]: ...

    @abstractmethod
    def get_bonus_score(
        self,
        course_name: str,
        username: str,
    ) -> int: ...

    @abstractmethod
    def get_stored_user(
        self,
        course_name: str,
        student: Student,
    ) -> StoredUser: ...

    @abstractmethod
    def sync_stored_user(
        self,
        course_name: str,
        student: Student,
    ) -> StoredUser: ...

    @abstractmethod
    def get_all_scores(self, course_name: str) -> dict[str, dict[str, int]]: ...

    @abstractmethod
    def get_stats(self, course_name: str) -> dict[str, float]: ...

    @abstractmethod
    def get_scores_update_timestamp(self) -> str: ...

    @abstractmethod
    def update_cached_scores(self) -> None: ...

    @abstractmethod
    def store_score(
        self,
        course_name: str,
        student: Student,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int: ...

    @abstractmethod
    def sync_columns(
        self,
        course_name: str,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None: ...

    @abstractmethod
    def get_course(
        self,
        course_name: str,
    ) -> Course | None: ...

    @abstractmethod
    def update_task_groups_from_config(
        self,
        course_name: str,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None: ...

    @abstractmethod
    def create_course(
        self,
        settings_config: ManytaskSettingsConfig,
    ) -> bool: ...

    @abstractmethod
    def update_course(
        self,
        course_name: str,
        ui_config: ManytaskUiConfig,
    ) -> None: ...

    @abstractmethod
    def find_task(self, course_name: str, task_name: str) -> tuple[ManytaskGroupConfig, ManytaskTaskConfig]: ...

    @abstractmethod
    def get_groups(
        self,
        course_name: str,
        enabled: bool | None = None,
        started: bool | None = None,
        now: datetime | None = None,
    ) -> list[ManytaskGroupConfig]: ...

    @abstractmethod
    def get_now_with_timezone(
        self,
        course_name: str,
    ) -> datetime: ...

    @abstractmethod
    def max_score(self, course_name: str, started: bool | None = True) -> int: ...

    @abstractmethod
    def max_score_started(self, course_name: str) -> int: ...

    @abstractmethod
    def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool: ...

    @abstractmethod
    def check_user_on_course(self, course_name: str, student: Student) -> bool: ...

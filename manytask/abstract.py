from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .config import ManytaskDeadlinesConfig, ManytaskGroupConfig, ManytaskTaskConfig, ManytaskUiConfig
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
        username: str,
    ) -> dict[str, int]: ...

    @abstractmethod
    def get_bonus_score(
        self,
        username: str,
    ) -> int: ...

    @abstractmethod
    def get_stored_user(
        self,
        student: Student,
    ) -> StoredUser: ...

    @abstractmethod
    def sync_stored_user(
        self,
        student: Student,
        repo_name: str,
        course_admin: bool,
    ) -> StoredUser: ...

    @abstractmethod
    def get_all_scores(self) -> dict[str, dict[str, int]]: ...

    @abstractmethod
    def get_stats(self) -> dict[str, float]: ...

    @abstractmethod
    def get_scores_update_timestamp(self) -> str: ...

    @abstractmethod
    def update_cached_scores(self) -> None: ...

    @abstractmethod
    def store_score(
        self,
        student: Student,
        repo_name: str,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int: ...

    @abstractmethod
    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None: ...

    @abstractmethod
    def update_task_groups_from_config(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None: ...

    @abstractmethod
    def update_course(
        self,
        ui_config: ManytaskUiConfig,
    ) -> None: ...

    @abstractmethod
    def get_course(
        self,
        course_name: str,
    ) -> Course | None: ...

    @abstractmethod
    def find_task(self, task_name: str) -> tuple[ManytaskGroupConfig, ManytaskTaskConfig]: ...

    @abstractmethod
    def get_groups(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        now: datetime | None = None,
    ) -> list[ManytaskGroupConfig]: ...

    @abstractmethod
    def get_now_with_timezone(self) -> datetime: ...

    @abstractmethod
    def max_score(self, started: bool | None = True) -> int: ...

    @property
    @abstractmethod
    def max_score_started(self) -> int: ...

    @abstractmethod
    def sync_and_get_admin_status(self, course_name: str, student: Student, course_admin: bool) -> bool: ...

    @abstractmethod
    def check_user_on_course(self, course_name: str, student: Student) -> bool: ...

    @abstractmethod
    def create_user_if_not_exist(self, student: Student, course_name: str) -> None: ...

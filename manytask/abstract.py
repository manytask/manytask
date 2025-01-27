from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from .config import ManytaskDeadlinesConfig
from .glab import Student


@dataclass
class StoredUser:
    username: str
    course_admin: bool = False
    # we can add more fields that we store

    def __repr__(self) -> str:
        return f"StoredUser(username={self.username})"


class ViewerApi(ABC):
    @abstractmethod
    def get_spreadsheet_url(self) -> str:
        ...


class StorageApi(ABC):
    @abstractmethod
    def get_scores(
        self,
        username: str,
    ) -> dict[str, int]:
        ...

    @abstractmethod
    def get_bonus_score(
        self,
        username: str,
    ) -> int:
        ...

    @abstractmethod
    def get_stored_user(
        self,
        student: Student,
    ) -> StoredUser:
        ...

    @abstractmethod
    def sync_stored_user(
        self,
        student: Student,
    ) -> StoredUser:
        ...

    @abstractmethod
    def get_all_scores(self) -> dict[str, dict[str, int]]:
        ...

    @abstractmethod
    def get_stats(self) -> dict[str, float]:
        ...

    @abstractmethod
    def get_scores_update_timestamp(self) -> str:
        ...

    @abstractmethod
    def update_cached_scores(self) -> None:
        ...

    @abstractmethod
    def store_score(
        self,
        student: Student,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int:
        ...

    @abstractmethod
    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        ...

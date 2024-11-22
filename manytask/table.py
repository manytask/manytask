from typing import Any, Callable
from abc import ABC, abstractmethod

from .config import ManytaskDeadlinesConfig

from . import glab


class TableApi(ABC):
    @abstractmethod
    def fetch_rating_table(self) -> "RatingTableAbs":
        pass
    
    @abstractmethod
    def get_spreadsheet_url(self) -> str: # TODO: remove this?
        pass


class RatingTableAbs(ABC):

    @abstractmethod
    def get_scores(
        self,
        username: str,
    ) -> dict[str, int]:
        pass

    @abstractmethod
    def get_bonus_score(
        self,
        username: str,
    ) -> int:
        pass

    @abstractmethod
    def get_all_scores(self) -> dict[str, dict[str, int]]:
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, float]:
        pass

    @abstractmethod
    def get_scores_update_timestamp(self) -> str:
        pass

    @abstractmethod
    def update_cached_scores(self) -> None:
        pass

    @abstractmethod
    def store_score(
        self,
        student: glab.Student,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int:
        pass

    @abstractmethod
    def sync_columns(
        self,
        deadlines_config: ManytaskDeadlinesConfig,
    ) -> None:
        pass

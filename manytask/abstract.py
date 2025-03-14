from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable

from .config import ManytaskConfig, ManytaskDeadlinesConfig
from .glab import Student
from .role import Role


@dataclass
class StoredUser:
    username: str
    role: Role = Role.STUDENT
    course_admin: bool = False  # todo remove. kept for now for backward compatibility

    def __repr__(self) -> str:
        return f"StoredUser(username={self.username}, role={self.role})"

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN or self.course_admin

    @property
    def is_teacher(self) -> bool:
        return self.role == Role.TEACHER

    @property
    def is_student(self) -> bool:
        return self.role == Role.STUDENT


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
    def get_course_by_unique_name(
        self,
        unique_course_name: str,
    ) -> Any: ...

    @abstractmethod
    def create_course(
        self,
        config: "ManytaskConfig",
    ) -> None: ...

    @abstractmethod
    def get_stored_user(
        self,
        student: Student,
    ) -> StoredUser: ...

    @abstractmethod
    def sync_stored_user(
        self,
        student: Student,
        is_registration: bool = False,
    ) -> StoredUser: ...

    @abstractmethod
    def set_user_role(
        self,
        username: str,
        role: Role,
    ) -> StoredUser: ...

    @abstractmethod
    def get_users_by_role(
        self,
        role: Role,
    ) -> list[StoredUser]: ...

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
        config_data: dict[str, Any],
    ) -> None: ...

    @abstractmethod
    def sync_and_get_admin_status(self, course_name: str, student: Student) -> bool: ...

    @abstractmethod
    def check_user_on_course(self, course_name: str, student: Student) -> bool: ...

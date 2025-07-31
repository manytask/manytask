from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from .config import ManytaskConfig, ManytaskGroupConfig, ManytaskTaskConfig
from .course import Course, CourseConfig


@dataclass
class StoredUser:
    username: str
    first_name: str
    last_name: str
    rms_id: int
    course_admin: bool = False
    # we can add more fields that we store

    def __repr__(self) -> str:
        return f"StoredUser(username={self.username})"


@dataclass
class Student:
    id: int
    username: str
    name: str

    def __repr__(self) -> str:
        return f"Student(username={self.username})"


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
        username: str,
    ) -> StoredUser: ...

    @abstractmethod
    def check_if_instance_admin(
        self,
        username: str,
    ) -> bool: ...

    @abstractmethod
    def check_if_course_admin(
        self,
        course_name: str,
        username: str,
    ) -> bool: ...

    @abstractmethod
    def sync_stored_user(
        self,
        course_name: str,
        username: str,
        repo_name: str,
        course_admin: bool,
    ) -> StoredUser: ...

    @abstractmethod
    def get_all_scores_with_names(self, course_name: str) -> dict[str, tuple[dict[str, int], tuple[str, str]]]: ...

    @abstractmethod
    def get_stats(self, course_name: str) -> dict[str, float]: ...

    @abstractmethod
    def get_scores_update_timestamp(self, course_name: str) -> str: ...

    @abstractmethod
    def update_cached_scores(self, course_name: str) -> None: ...

    @abstractmethod
    def store_score(
        self,
        course_name: str,
        username: str,
        repo_name: str,
        task_name: str,
        update_fn: Callable[..., Any],
    ) -> int: ...

    @abstractmethod
    def create_course(
        self,
        settings_config: CourseConfig,
    ) -> bool: ...

    @abstractmethod
    def edit_course(
        self,
        settings_config: CourseConfig,
    ) -> bool: ...

    @abstractmethod
    def update_course(
        self,
        course_name: str,
        config: ManytaskConfig,
    ) -> None: ...

    @abstractmethod
    def get_course(
        self,
        course_name: str,
    ) -> Course | None: ...

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
    def get_now_with_timezone(self, course_name: str) -> datetime: ...

    @abstractmethod
    def max_score(self, course_name: str, started: bool | None = True) -> int: ...

    @abstractmethod
    def max_score_started(self, course_name: str) -> int: ...

    @abstractmethod
    def sync_and_get_admin_status(self, course_name: str, username: str, course_admin: bool) -> bool: ...

    @abstractmethod
    def check_user_on_course(self, course_name: str, username: str) -> bool: ...

    @abstractmethod
    def create_user_if_not_exist(self, username: str, first_name: str, last_name: str, rms_id: int) -> None: ...

    @abstractmethod
    def get_user_courses_names(self, username: str) -> list[str]: ...

    @abstractmethod
    def get_all_courses_names(self) -> list[str]: ...

    @abstractmethod
    def get_all_users(self) -> list[StoredUser]: ...

    @abstractmethod
    def set_instance_admin_status(
        self,
        username: str,
        is_admin: bool,
    ) -> None: ...

    @abstractmethod
    def update_user_profile(self, username: str, new_first_name: str | None, new_last_name: str | None) -> None: ...


@dataclass
class RmsUser:
    id: int
    username: str
    name: str

    def __repr__(self) -> str:
        return f"RmsUser(username={self.username})"


class RmsApi(ABC):
    _base_url: str

    @property
    def base_url(self) -> str:
        return self._base_url

    @abstractmethod
    def register_new_user(
        self,
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str,
    ) -> None: ...

    @abstractmethod
    def create_public_repo(
        self,
        course_group: str,
        course_public_repo: str,
    ) -> None: ...

    @abstractmethod
    def create_students_group(
        self,
        course_students_group: str,
    ) -> None: ...

    @abstractmethod
    def check_project_exists(
        self,
        project_name: str,
        project_group: str,
    ) -> bool: ...

    @abstractmethod
    def create_project(
        self,
        rms_user: RmsUser,
        course_students_group: str,
        course_public_repo: str,
    ) -> None: ...

    @abstractmethod
    def get_url_for_task_base(self, course_public_repo: str, default_branch: str) -> str: ...

    @abstractmethod
    def get_url_for_repo(
        self,
        username: str,
        course_students_group: str,
    ) -> str: ...

    @abstractmethod
    def get_rms_user_by_id(
        self,
        user_id: int,
    ) -> RmsUser: ...

    @abstractmethod
    def get_rms_user_by_username(
        self,
        username: str,
    ) -> RmsUser: ...

    @abstractmethod
    def check_authenticated_rms_user(
        self,
        oauth_token: str,
    ) -> None: ...

    @abstractmethod
    def get_authenticated_rms_user(
        self,
        oauth_token: str,
    ) -> RmsUser: ...

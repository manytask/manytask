from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from authlib.integrations.flask_client import OAuth

from .config import ManytaskConfig, ManytaskFinalGradeConfig, ManytaskGroupConfig, ManytaskTaskConfig
from .course import Course, CourseConfig, CourseStatus


@dataclass
class StoredUser:
    username: str
    first_name: str
    last_name: str
    rms_id: int
    instance_admin: bool = False
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
    def get_stored_user_by_username(
        self,
        username: str,
    ) -> StoredUser: ...

    @abstractmethod
    def get_stored_user_by_rms_id(
        self,
        rms_id: int,
    ) -> StoredUser | None: ...

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
    def check_if_program_manager(
        self,
        course_name: str,
        username: str,
    ) -> bool: ...

    @abstractmethod
    def sync_user_on_course(self, course_name: str, username: str, course_admin: bool) -> None: ...

    @abstractmethod
    def get_all_scores_with_names(
        self, course_name: str
    ) -> dict[str, tuple[dict[str, tuple[int, bool]], tuple[str, str]]]: ...

    @abstractmethod
    def get_student_comment(self, course_name: str, username: str) -> str | None: ...

    @abstractmethod
    def update_student_comment(self, course_name: str, username: str, comment: str | None) -> None: ...

    @abstractmethod
    def get_grades(self, course_name: str) -> ManytaskFinalGradeConfig: ...

    @abstractmethod
    def get_stats(self, course_name: str) -> dict[str, float]: ...

    @abstractmethod
    def get_scores_update_timestamp(self, course_name: str) -> str: ...

    @abstractmethod
    def update_cached_scores(self, course_name: str) -> None: ...

    @abstractmethod
    def store_score(self, course_name: str, username: str, task_name: str, update_fn: Callable[..., Any]) -> int: ...

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
    def find_task(self, course_name: str, task_name: str) -> tuple[Course, ManytaskGroupConfig, ManytaskTaskConfig]: ...

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
    def update_or_create_user(self, username: str, first_name: str, last_name: str, rms_id: int) -> None: ...

    @abstractmethod
    def get_user_courses_names_with_statuses(self, username: str) -> list[tuple[str, CourseStatus]]: ...

    @abstractmethod
    def get_all_courses_names_with_statuses(self) -> list[tuple[str, CourseStatus]]: ...

    @abstractmethod
    def get_namespace_admin_namespaces(self, username: str) -> list[int]: ...

    @abstractmethod
    def get_courses_by_namespace_ids(self, namespace_ids: list[int]) -> list[tuple[str, CourseStatus]]: ...

    @abstractmethod
    def get_courses_where_course_admin(self, username: str) -> list[tuple[str, CourseStatus]]: ...

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

    @abstractmethod
    def create_namespace(
        self,
        name: str,
        slug: str,
        description: str | None,
        gitlab_group_id: int,
        created_by_username: str,
    ) -> Any: ...

    @abstractmethod
    def get_all_namespaces(self) -> list[Any]: ...

    @abstractmethod
    def get_user_namespaces(self, username: str) -> list[tuple[Any, str]]: ...

    @abstractmethod
    def get_namespace_by_id(self, namespace_id: int, username: str) -> tuple[Any, str | None]: ...

    @abstractmethod
    def add_user_to_namespace(
        self,
        namespace_id: int,
        user_id: int,
        role: str,
        assigned_by_username: str,
    ) -> Any: ...

    @abstractmethod
    def get_namespace_users(self, namespace_id: int) -> list[tuple[int, str]]: ...

    @abstractmethod
    def add_course_owners(
        self,
        course_id: int,
        owner_rms_ids: list[int],
        namespace_id: int,
    ) -> list[int]:
        """
        :returns: list of successfully added user_ids
        """
        ...

    @abstractmethod
    def get_stored_user_by_id(
        self,
        user_id: int,
    ) -> StoredUser | None: ...

    @abstractmethod
    def get_namespace_courses(self, namespace_id: int) -> list[dict[str, Any]]: ...

    @abstractmethod
    def remove_user_from_namespace(self, namespace_id: int, user_id: int) -> tuple[str, int]: ...

    @abstractmethod
    def update_user_role_in_namespace(self, namespace_id: int, user_id: int, new_role: str) -> tuple[str, str, int]: ...

    @abstractmethod
    def get_course_id_by_name(self, course_name: str) -> int | None: ...


@dataclass
class RmsUser:
    id: int
    username: str
    name: str

    def __repr__(self) -> str:
        return f"RmsUser(username={self.username})"


class RmsApiException(Exception):
    pass


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
    ) -> RmsUser: ...

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
        parent_group_id: int | None = None,
    ) -> Any:
        """
        :returns: Group object or None
        """
        ...

    @abstractmethod
    def create_namespace_group(
        self,
        name: str,
        path: str,
        description: str | None = None,
    ) -> int: ...

    @abstractmethod
    def add_user_to_namespace_group(
        self,
        gitlab_group_id: int,
        user_id: int,
    ) -> None: ...

    @abstractmethod
    def remove_user_from_namespace_group(
        self,
        gitlab_group_id: int,
        user_id: int,
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
    def get_authenticated_rms_user(
        self,
        oauth_access_token: str,
    ) -> RmsUser: ...

    @abstractmethod
    def create_course_group(
        self,
        parent_group_id: int,
        course_name: str,
        course_slug: str,
    ) -> int:
        """
        :returns: course_group_id
        """
        ...

    @abstractmethod
    def delete_group(self, group_id: int) -> None: ...

    @abstractmethod
    def delete_project(self, project_id: int) -> None: ...

    @abstractmethod
    def get_group_path_by_id(self, group_id: int) -> str | None: ...


@dataclass
class AuthenticatedUser:
    id: int
    username: str

    def __repr__(self) -> str:
        return f"AuthenticatedUser(username={self.username})"


@dataclass
class ClientProfile:
    username: str

    def __repr__(self) -> str:
        return f"ClientProfile(username={self.username})"


class AuthApi(ABC):
    @abstractmethod
    def check_user_is_authenticated(
        self,
        oauth: OAuth,
        oauth_access_token: str,
        oauth_refresh_token: str,
    ) -> bool: ...

    @abstractmethod
    def get_authenticated_user(
        self,
        oauth_access_token: str,
    ) -> AuthenticatedUser: ...

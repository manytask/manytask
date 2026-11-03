from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
DEFAULT_TIMEZONE = ZoneInfo("Europe/Moscow")


class CourseStatus(Enum):
    CREATED = "created"
    HIDDEN = "hidden"
    IN_PROGRESS = "in_progress"
    ALL_TASKS_ISSUED = "all_tasks_issued"
    DORESHKA = "doreshka"
    FINISHED = "finished"


def parse_time(time: str, tz: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    date = datetime.strptime(time, "%Y-%m-%d %H:%M")
    date = date.replace(tzinfo=tz)
    print("Got", time, "return", date)
    return date


def get_current_time(tz: ZoneInfo = DEFAULT_TIMEZONE) -> datetime:
    return datetime.now(tz=tz)


def validate_submit_time(commit_time: datetime | None, current_time: datetime) -> datetime:
    """Check if commit_time 'to far' from current_time, use current_time, else use commit_time"""
    if not commit_time:
        return current_time

    if commit_time > current_time:
        print(f"WTF: commit_time {commit_time} > current_time {current_time}")
        return current_time

    return current_time


class ManytaskDeadlinesType(Enum):
    HARD = "hard"
    INTERPOLATE = "interpolate"


@dataclass
class ProtectedBranchSettings:
    """Desired GitLab protected-branch state for a single branch."""

    name: str
    push_access_level: str  # "no_access" | "developer" | "maintainer"
    merge_access_level: str  # "no_access" | "developer" | "maintainer"
    allow_force_push: bool


def resolve_effective_ci_config_path(configured: Optional[str], course_public_repo: str) -> str:
    return configured if configured else f".gitlab-ci.yml@{course_public_repo}"


def resolve_effective_protected_branches(
    configured: Optional[list[ProtectedBranchSettings]], default_branch: str
) -> list[ProtectedBranchSettings]:
    if configured:
        return configured
    return [
        ProtectedBranchSettings(
            name=default_branch,
            push_access_level="developer",
            merge_access_level="developer",
            allow_force_push=True,
        )
    ]


@dataclass
class CourseConfig:
    """Configuration for Course settings."""

    course_name: str
    namespace_id: Optional[int]

    gitlab_course_group: str
    gitlab_course_public_repo: str
    gitlab_course_students_group: str
    gitlab_default_branch: str

    registration_secret: str
    token: str
    show_allscores: bool

    status: CourseStatus = CourseStatus.CREATED

    task_url_template: str = ""
    links: dict[str, str] = field(default_factory=dict)
    deadlines_type: ManytaskDeadlinesType = ManytaskDeadlinesType.HARD

    ci_config_path: Optional[str] = None
    protected_branches: Optional[list[ProtectedBranchSettings]] = None


class Course:
    def __init__(
        self,
        config: CourseConfig,
    ):
        """Initialize Course with configuration.

        :param config: CourseConfig instance containing all necessary settings
        """

        self.course_name = config.course_name
        self.namespace_id = config.namespace_id

        self.__gitlab_course_group = config.gitlab_course_group
        self.__gitlab_course_public_repo = config.gitlab_course_public_repo
        self.__gitlab_course_students_group = config.gitlab_course_students_group
        self.__gitlab_default_branch = config.gitlab_default_branch

        self.registration_secret = config.registration_secret
        self.token = config.token
        self.show_allscores = config.show_allscores
        self.deadlines_type = config.deadlines_type

        self.status = config.status

        self.task_url_template = config.task_url_template
        self.links = config.links

        self.__ci_config_path = config.ci_config_path
        self.__protected_branches = config.protected_branches

    @property
    def ci_config_path(self) -> str:
        return resolve_effective_ci_config_path(self.__ci_config_path, self.gitlab_course_public_repo)

    @property
    def protected_branches(self) -> list[ProtectedBranchSettings]:
        return resolve_effective_protected_branches(self.__protected_branches, self.gitlab_default_branch)

    @property
    def gitlab_course_group(self) -> str:
        return self.__gitlab_course_group

    @property
    def gitlab_course_public_repo(self) -> str:
        return self.__gitlab_course_public_repo

    @property
    def gitlab_course_students_group(self) -> str:
        return self.__gitlab_course_students_group

    @property
    def gitlab_default_branch(self) -> str:
        return self.__gitlab_default_branch

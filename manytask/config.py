from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AnyUrl, BaseModel, Field, field_validator, model_validator

from manytask.course import CourseStatus, ManytaskDeadlinesType
from manytask.utils.generic import lerp

MAX_COURSE_NAME_LENGTH = 100


class RowData(BaseModel):
    username: str
    total_score: int
    percent: float
    large_count: int
    grade: int
    scores: dict[str, int]
    grade_is_override: bool = False  # Indicates if grade is manually overridden by admin


class ManytaskUpdateDatabasePayload(BaseModel):
    new_scores: dict[str, Any] = Field(...)
    row_data: RowData


class CreateNamespaceRequest(BaseModel):
    name: str
    slug: str
    description: str | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, slug: str) -> str:
        from manytask.models import _validate_gitlab_slug

        return _validate_gitlab_slug(slug)


class AddUserToNamespaceRequest(BaseModel):
    user_id: int
    role: Literal["namespace_admin", "program_manager"]


ROLE_STUDENT = "student"


class UpdateUserRoleRequest(BaseModel):
    """Request to update a user's role in a namespace.

    role can be 'namespace_admin', 'program_manager', or 'student'.
    Setting role to 'student' will remove the user from the namespace entirely.
    """

    role: Literal["namespace_admin", "program_manager", "student"]


class ErrorResponse(BaseModel):
    error: str


class NamespaceResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str]
    gitlab_group_id: int
    gitlab_group_path: Optional[str] = None


class NamespaceWithRoleResponse(NamespaceResponse):
    role: str


class NamespaceListResponse(BaseModel):
    namespaces: list[Union[NamespaceResponse, NamespaceWithRoleResponse]]


class UserOnNamespaceResponse(BaseModel):
    id: int
    user_id: int
    namespace_id: int
    role: str


class NamespaceUserItem(BaseModel):
    user_id: int
    role: str


class NamespaceUsersListResponse(BaseModel):
    users: list[NamespaceUserItem]


class CreateCourseRequest(BaseModel):
    namespace_id: int
    course_name: str
    slug: str
    owners: Optional[list[str]] = None  # gitlab user_ids

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, slug: str) -> str:
        from manytask.models import _validate_gitlab_slug

        return _validate_gitlab_slug(slug)

    @field_validator("course_name")
    @classmethod
    def validate_course_name(cls, course_name: str) -> str:
        if not course_name or len(course_name.strip()) == 0:
            raise ValueError("course_name cannot be empty")
        if len(course_name) > MAX_COURSE_NAME_LENGTH:
            raise ValueError(f"course_name must be at most {MAX_COURSE_NAME_LENGTH} characters")
        return course_name.strip()


class CourseResponse(BaseModel):
    id: int
    course_name: str
    slug: str
    namespace_id: int
    gitlab_course_group: str
    gitlab_course_public_repo: str
    gitlab_course_students_group: str
    status: str
    owners: list[str]  # gitlab user_ids


class ManytaskUiConfig(BaseModel):
    task_url_template: str  # $GROUP_NAME $TASK_NAME $USER_NAME vars are available
    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("task_url_template")
    @classmethod
    def check_task_url_template(cls, data: str | None) -> str | None:
        if data is not None and (not data.startswith("http://") and not data.startswith("https://")):
            raise ValueError("task_url_template should be http or https")
        # if data is not None and "$GROUP_NAME" not in data and "$TASK_NAME" not in data:
        #     raise ValueError("task_url should contain at least one of $GROUP_NAME and $TASK_NAME vars")
        return data


class ManytaskTaskConfig(BaseModel):
    task: str

    enabled: bool = True

    score: int
    # Minimum score to count the task, only significant for large tasks
    min_score: int = 0
    special: int = 0

    is_bonus: bool = False
    is_large: bool = False
    is_special: bool = False

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    url: Optional[AnyUrl] = None

    @property
    def name(self) -> str:
        return self.task


class ManytaskGroupConfig(BaseModel):
    group: str

    enabled: bool = True

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    start: datetime
    steps: dict[float, Union[datetime, timedelta]] = Field(default_factory=dict)
    end: Union[datetime, timedelta]

    tasks: list[ManytaskTaskConfig] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.group

    def get_percents_before_deadline(self) -> list[tuple[datetime, float]]:
        return list(zip(map(self.get_deadline, [*self.steps.values(), self.end]), [1.0, *self.steps.keys()]))

    def get_percents_after_deadline(self) -> list[tuple[datetime, float]]:
        return list(zip(map(self.get_deadline, [self.start, *self.steps.values()]), [1.0, *self.steps.keys()]))

    def get_displayed_deadlines(self, deadlines_type: ManytaskDeadlinesType) -> list[tuple[datetime, float]]:
        if deadlines_type == ManytaskDeadlinesType.HARD:
            return self.get_percents_before_deadline()
        else:
            return self.get_percents_after_deadline()[1:]

    def get_deadline(self, date_or_delta: datetime | timedelta) -> datetime:
        if isinstance(date_or_delta, datetime):
            return date_or_delta
        return self.start + date_or_delta

    def get_current_percent_multiplier(self, now: datetime, deadlines_type: ManytaskDeadlinesType) -> float:
        if now >= self.get_deadline(self.end):
            return 0.0
        last_point = None
        for date, percent in self.get_percents_after_deadline():
            if now >= date:
                last_point = (date, percent)
                continue

            if deadlines_type == ManytaskDeadlinesType.HARD or last_point is None:
                break
            start = last_point[0]
            return lerp(
                p1=(0.0, last_point[1]),
                p2=((date - start).total_seconds(), percent),
                x=(now - start).total_seconds(),
            )

        # None if now is before start, ok if last_point[1] is zero
        return (last_point and last_point[1]) or 0.0

    def replace_timezone(self, timezone: ZoneInfo) -> None:
        self.start = self.start.replace(tzinfo=timezone)
        self.end = self.end.replace(tzinfo=timezone) if isinstance(self.end, datetime) else self.end
        self.steps = {k: v.replace(tzinfo=timezone) for k, v in self.steps.items() if isinstance(v, datetime)}

    @model_validator(mode="after")
    def check_dates(self) -> "ManytaskGroupConfig":
        # check end
        if isinstance(self.end, timedelta) and self.end < timedelta():
            raise ValueError(f"end timedelta <{self.end}> should be positive")
        if isinstance(self.end, datetime) and self.end < self.start:
            raise ValueError(f"end datetime <{self.end}> should be after the start <{self.start}>")

        # check steps
        last_step_date_or_delta: datetime | timedelta = self.start
        for _, date_or_delta in self.steps.items():
            step_date = self.start + date_or_delta if isinstance(date_or_delta, timedelta) else date_or_delta
            last_step_date = (
                self.start + last_step_date_or_delta
                if isinstance(last_step_date_or_delta, timedelta)
                else last_step_date_or_delta
            )

            if isinstance(date_or_delta, timedelta) and date_or_delta < timedelta():
                raise ValueError(f"step timedelta <{date_or_delta}> should be positive")
            if isinstance(date_or_delta, datetime) and date_or_delta <= self.start:
                raise ValueError(f"step datetime <{date_or_delta}> should be after the start {self.start}")

            if step_date <= last_step_date:
                raise ValueError(
                    f"step datetime/timedelta <{date_or_delta}> "
                    f"should be after the last step <{last_step_date_or_delta}>"
                )
            last_step_date_or_delta = date_or_delta

        return self


class ManytaskDeadlinesConfig(BaseModel):
    timezone: str

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    deadlines: ManytaskDeadlinesType = ManytaskDeadlinesType.HARD
    max_submissions: Optional[int] = None
    submission_penalty: float = 0

    schedule: list[ManytaskGroupConfig]  # list of groups with tasks

    @field_validator("max_submissions")
    @classmethod
    def check_max_submissions(cls, data: int | None) -> int | None:
        if data is not None and data <= 0:
            raise ValueError("max_submissions should be positive")
        return data

    @field_validator("submission_penalty")
    @classmethod
    def check_submission_penalty(cls, data: float) -> float:
        if data < 0:
            raise ValueError("submission_penalty should be non-negative")
        return data

    @field_validator("timezone")
    @classmethod
    def check_valid_timezone(cls, timezone: str) -> str:
        try:
            ZoneInfo(timezone)
        except ZoneInfoNotFoundError as e:
            raise ValueError(str(e))
        return timezone

    @field_validator("schedule")
    @classmethod
    def check_group_task_names_unique(cls, data: list[ManytaskGroupConfig]) -> list[ManytaskGroupConfig]:
        group_names = [group.name for group in data]
        tasks_names = [task.name for group in data for task in group.tasks]

        # group names unique
        group_names_duplicates = [name for name in group_names if group_names.count(name) > 1]
        if group_names_duplicates:
            raise ValueError(f"Group names should be unique, duplicates: {group_names_duplicates}")

        # task names unique
        tasks_names_duplicates = [name for name in tasks_names if tasks_names.count(name) > 1]
        if tasks_names_duplicates:
            raise ValueError(f"Task names should be unique, duplicates: {tasks_names_duplicates}")

        # # group names and task names not intersect (except single task in a group with the same name)
        # no_single_task_groups = [group for group in data if not (len(group.tasks) == 1
        # and group.name == group.tasks[0].name)]

        return data

    @model_validator(mode="after")
    def set_timezone(self) -> "ManytaskDeadlinesConfig":
        timezone = ZoneInfo(self.timezone)
        for group in self.schedule:
            group.replace_timezone(timezone)
        return self

    @model_validator(mode="before")
    @classmethod
    def add_extra_group(cls, data: dict[str, Any]) -> Any:
        schedule = data.get("schedule", [])

        schedule.append(
            {
                "group": "Bonus group",
                "start": datetime(2000, 1, 1, 0, 0, tzinfo=timezone.utc),
                "end": datetime(3000, 1, 1, 0, 0, tzinfo=timezone.utc),
                "enabled": False,
                "tasks": [{"task": "bonus_score", "score": 0, "is_bonus": True}],
            }
        )
        data["schedule"] = schedule
        return data

    @property
    def groups(
        self,
    ) -> list[ManytaskGroupConfig]:
        return self.schedule


class ManytaskFinalGradeConfig(BaseModel):
    grades: dict[int, list[dict[Path, Union[int, float]]]] = Field(default_factory=dict)
    grades_order: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_grades_order(self) -> ManytaskFinalGradeConfig:
        self.grades_order = sorted(list(self.grades.keys()), reverse=True)
        return self

    def evaluate(self, scores: dict[str, Any]) -> Optional[int]:
        for grade in self.grades_order:
            if ManytaskFinalGradeConfig.evaluate_grade(self.grades[grade], scores):
                return grade

        # shortcut for courses that do not use builtin grading system
        if len(self.grades_order) == 0:
            return 0

        raise ValueError("No grade matched")

    @staticmethod
    def get_attribute(path: Path, scores: dict[str, Any]) -> Any:
        # empty path means always true: dummy case for lowest mark
        if len(path.parts) == 0:
            return True

        attribute = scores
        for dir in path.parts:
            if not isinstance(attribute, dict):
                raise ValueError(f"Path <{path}> not found in scores data <{scores}>")
            try:
                attribute = attribute[dir]
            except KeyError:
                raise ValueError(f"Path <{path}> not found in scores data <{scores}>")

        return attribute

    @staticmethod
    def evaluate_primary_formula(formula: dict[Path, Union[int, float]], scores: dict[str, Any]) -> bool:
        for path, limit in formula.items():
            try:
                attribute = ManytaskFinalGradeConfig.get_attribute(path, scores)
            except ValueError:
                return False
            if attribute < limit:
                return False
        return True

    @staticmethod
    def evaluate_grade(grade_config: list[dict[Path, Union[int, float]]], scores: dict[str, Any]) -> bool:
        for formula in grade_config:
            if ManytaskFinalGradeConfig.evaluate_primary_formula(formula, scores):
                return True
        return False


class ManytaskConfig(BaseModel):
    """Manytask configuration."""

    version: int  # if config exists, version is always present
    status: CourseStatus | None = None

    ui: ManytaskUiConfig
    deadlines: ManytaskDeadlinesConfig
    grades: Optional[ManytaskFinalGradeConfig] = None

    @field_validator("version")
    @classmethod
    def check_version(cls, data: int) -> int:
        if data != 1:
            raise ValueError(f"Only version 1 is supported for {cls.__name__}")
        return data

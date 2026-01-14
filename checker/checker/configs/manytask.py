from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional, Union
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AnyUrl, Field, field_validator, model_validator

from .utils import CustomBaseModel, YamlLoaderMixin


class ManytaskSettingsConfig(CustomBaseModel):
    """Manytask settings."""

    course_name: str
    gitlab_base_url: AnyUrl
    public_repo: str
    students_group: str


class ManytaskUiConfig(CustomBaseModel):
    task_url_template: str  # $GROUP_NAME $TASK_NAME vars are available
    links: dict[str, str] = Field(default_factory=dict)

    @field_validator("task_url_template")
    @classmethod
    def check_task_url_template(cls, data: str | None) -> str | None:
        if data is not None and (not data.startswith("http://") and not data.startswith("https://")):
            raise ValueError("task_url_template should be http or https")
        # if data is not None and "$GROUP_NAME" not in data and "$TASK_NAME" not in data:
        #     raise ValueError("task_url should contain at least one of $GROUP_NAME and $TASK_NAME vars")
        return data


class ManytaskDeadlinesType(Enum):
    HARD = "hard"
    INTERPOLATE = "interpolate"


class ManytaskTaskConfig(CustomBaseModel):
    task: str

    enabled: bool = True

    score: int
    # Minimum (threshold) score to consider large task completed
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


class ManytaskGroupConfig(CustomBaseModel):
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

    def get_percents_before_deadline(self) -> dict[float, datetime]:
        return {
            percent: date_or_delta if isinstance(date_or_delta, datetime) else self.start + date_or_delta
            for percent, date_or_delta in zip([1.0, *self.steps.keys()], [*self.steps.values(), self.end])
        }

    def get_current_percent_multiplier(self, now: datetime) -> float:
        percents = self.get_percents_before_deadline()
        for percent, date in percents.items():
            if now <= date:
                return percent
        return 0.0

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


class ManytaskDeadlinesConfig(CustomBaseModel):
    timezone: str

    # Note: use Optional/Union[...] instead of ... | None as pydantic does not support | in older python versions
    deadlines: ManytaskDeadlinesType = ManytaskDeadlinesType.HARD
    window: Optional[int] = None  # interpolation window (in days) used for ManytaskDeadlinesType.INTERPOLATE
    max_submissions: Optional[int] = None
    submission_penalty: float = 0

    schedule: list[ManytaskGroupConfig]  # list of groups with tasks

    def get_now_with_timezone(self) -> datetime:
        return datetime.now(tz=ZoneInfo(self.timezone))

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
        except IsADirectoryError as e:
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

    @field_validator("window")
    @classmethod
    def check_valid_window(cls, window: int | None) -> int | None:
        if window is not None and window <= 0:
            raise ValueError("window should be positive")
        return window

    @model_validator(mode="after")
    def set_timezone(self) -> "ManytaskDeadlinesConfig":
        timezone = ZoneInfo(self.timezone)
        for group in self.schedule:
            group.replace_timezone(timezone)
        return self

    @model_validator(mode="after")
    def check_valid_deadline(self) -> "ManytaskDeadlinesConfig":
        if self.window is not None and self.deadlines != ManytaskDeadlinesType.INTERPOLATE:
            raise ValueError("window can be applied only with interpolate deadline type")
        if self.deadlines == ManytaskDeadlinesType.INTERPOLATE:
            for group in self.schedule:
                steps = group.get_percents_before_deadline()
                left_bound = list(steps.values())[:-1]
                right_bound = list(steps.values())[1:]
                for left, right in zip(left_bound, right_bound):
                    if left + timedelta(days=self.window or 0) > right:
                        raise ValueError("window is too large")
        return self

    def find_task(self, task_name: str) -> tuple[ManytaskGroupConfig, ManytaskTaskConfig]:
        for group in self.schedule:
            for task in group.tasks:
                if task.name == task_name:
                    return group, task
        raise KeyError(f"Task {task_name} not found")

    def get_groups(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        *,
        now: datetime | None = None,
    ) -> list[ManytaskGroupConfig]:
        if now is None:
            now = self.get_now_with_timezone()

        groups = [group for group in self.schedule]

        if enabled is not None:
            groups = [group for group in groups if group.enabled == enabled]

        if started is not None:
            if started:
                groups = [group for group in groups if group.start <= now]
            else:
                groups = [group for group in groups if group.start > now]

        return groups

    def get_tasks(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        is_bonus: bool | None = None,
        *,
        now: datetime | None = None,
    ) -> list[ManytaskTaskConfig]:
        # TODO: refactor
        if now is None:
            now = self.get_now_with_timezone()

        groups = self.get_groups(started=started, now=now)

        if enabled is True:
            groups = [group for group in groups if group.enabled]
            extra_tasks = []
        elif enabled is False:
            groups = groups
            extra_tasks = [task for group in groups for task in group.tasks if not group.enabled]
        else:  # None
            groups = groups
            extra_tasks = []

        tasks = [task for group in groups for task in group.tasks]

        if enabled is not None:
            tasks = [task for task in tasks if task.enabled == enabled]

        for extra_task in extra_tasks:
            if extra_task not in tasks:
                tasks.append(extra_task)

        if is_bonus is not None:
            tasks = [task for task in tasks if task.is_bonus == is_bonus]

        return tasks

    def max_score(self, started: bool | None = True, *, now: datetime | None = None) -> int:
        return sum(task.score for task in self.get_tasks(enabled=True, started=started, is_bonus=False, now=now))

    @property
    def max_score_started(self) -> int:
        return self.max_score(started=True, now=self.get_now_with_timezone())


class ManytaskConfig(CustomBaseModel, YamlLoaderMixin["ManytaskConfig"]):
    """Manytask configuration."""

    version: int  # if config exists, version is always present

    settings: ManytaskSettingsConfig
    ui: ManytaskUiConfig
    deadlines: ManytaskDeadlinesConfig
    grades: Optional[Dict[str, Any]] = Field(default=None, exclude=True)

    def get_groups(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        *,
        now: datetime | None = None,
    ) -> list[ManytaskGroupConfig]:
        return self.deadlines.get_groups(enabled=enabled, started=started, now=now)

    def get_tasks(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        *,
        now: datetime | None = None,
    ) -> list[ManytaskTaskConfig]:
        return self.deadlines.get_tasks(enabled=enabled, started=started, now=now)

    @field_validator("version")
    @classmethod
    def check_version(cls, data: int) -> int:
        if data != 1:
            raise ValueError(f"Only version 1 is supported for {cls.__name__}")
        return data

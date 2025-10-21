from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from checker.configs.manytask import ManytaskDeadlinesConfig, ManytaskGroupConfig

# Test score and multiplier constants
SCORE_100_PERCENT = 1.0
SCORE_90_PERCENT = 0.9
SCORE_50_PERCENT = 0.5
SCORE_20_PERCENT = 0.2
SCORE_10_PERCENT = 0.1
SCORE_0_PERCENT = 0.0
NEGATIVE_SCORE_10_PERCENT = -0.1
NEGATIVE_SCORE_20_PERCENT = -0.2

# Test score values
TASK_SCORE_10 = 10

# Test window values
WINDOW_NEGATIVE_5 = -5
WINDOW_0 = 0
WINDOW_7 = 7
WINDOW_100 = 100

# Test submission limits
MAX_SUBMISSIONS_NEGATIVE = -1
MAX_SUBMISSIONS_INVALID_FLOAT = 1.2


class TestManytaskDeadlinesConfigGroup:
    def test_minimal_init(self) -> None:
        ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            end="2021-01-01 00:00",
            tasks=[],
        )
        assert True

    def test_maximal_init(self) -> None:
        ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            steps={
                SCORE_50_PERCENT: "2021-01-02 00:00",
            },
            end="2021-01-03 00:00",
            enabled=False,
            tasks=[
                {
                    "task": "task1",
                    "score": TASK_SCORE_10,
                },
            ],
        )
        assert True

    def test_invalid_start(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskGroupConfig(
                group="group1",
                start="2021-01-99 00:00",
                end="2021-01-01 00:00",
                tasks=[],
            )

    def test_invalid_end(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskGroupConfig(
                group="group1",
                start="2021-01-01 00:00",
                end="2021-01-99 00:00",
                tasks=[],
            )

    def test_invalid_steps(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskGroupConfig(
                group="group1",
                start="2021-01-01 00:00",
                steps={
                    SCORE_50_PERCENT: "2021-01-99 00:00",
                },
                end="2021-01-01 00:00",
                tasks=[],
            )

    def test_end_before_start(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskGroupConfig(
                group="group1",
                start="2021-01-02 00:00",
                end="2021-01-01 00:00",
                tasks=[],
            )

    @pytest.mark.parametrize(
        "end_date",
        [
            "2021-01-01 00:00",
            "2021-01-01 00:00:00",
            "2021-01-01 00:00:00.000000",
            "200d",
            "20d 09:00",
            "20d 09:00:30",
        ],
    )
    def test_valid_end(self, end_date: str) -> None:
        ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            end=end_date,
            tasks=[],
        )

    def test_get_percents_before_deadline(self) -> None:
        group = ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            steps={
                SCORE_90_PERCENT: "2021-01-02 00:00",
                SCORE_50_PERCENT: "2021-01-03 00:00",
                SCORE_20_PERCENT: "2021-01-04 00:00",
            },
            end="2021-01-05 00:00",
            tasks=[],
        )

        percents_before_deadline = group.get_percents_before_deadline()

        assert percents_before_deadline == {
            SCORE_100_PERCENT: datetime(2021, 1, 2, 0, 0),
            SCORE_90_PERCENT: datetime(2021, 1, 3, 0, 0),
            SCORE_50_PERCENT: datetime(2021, 1, 4, 0, 0),
            SCORE_20_PERCENT: datetime(2021, 1, 5, 0, 0),
        }

    def test_get_percents_before_deadline_timedelta(self) -> None:
        group = ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            steps={
                SCORE_90_PERCENT: "1d 09:00:00",
                SCORE_50_PERCENT: "2d 09:00:00",
                SCORE_20_PERCENT: "3d 09:00:00",
            },
            end="4d 09:00:00",
            tasks=[],
        )

        percents_before_deadline = group.get_percents_before_deadline()

        assert percents_before_deadline == {
            SCORE_100_PERCENT: datetime(2021, 1, 2, 9, 0),
            SCORE_90_PERCENT: datetime(2021, 1, 3, 9, 0),
            SCORE_50_PERCENT: datetime(2021, 1, 4, 9, 0),
            SCORE_20_PERCENT: datetime(2021, 1, 5, 9, 0),
        }

    @pytest.mark.parametrize(
        "now, expected_percent",
        [
            (datetime(1000, 1, 1, 0, 0), SCORE_100_PERCENT),
            (datetime(2021, 1, 1, 0, 0), SCORE_100_PERCENT),
            (datetime(2021, 1, 1, 12, 0), SCORE_100_PERCENT),
            (datetime(2021, 1, 2, 1, 0), SCORE_90_PERCENT),
            (datetime(2021, 1, 4, 1, 0), SCORE_20_PERCENT),
            (datetime(2021, 1, 5, 1, 0), SCORE_0_PERCENT),
            (datetime(3000, 1, 5, 1, 0), SCORE_0_PERCENT),
        ],
    )
    def test_get_current_percent_multiplier(self, now: datetime, expected_percent: float) -> None:
        group = ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            steps={
                SCORE_90_PERCENT: "2021-01-02 00:00",
                SCORE_50_PERCENT: "2021-01-03 00:00",
                SCORE_20_PERCENT: "2021-01-04 00:00",
            },
            end="2021-01-05 00:00",
            tasks=[],
        )

        assert group.get_current_percent_multiplier(now=now) == expected_percent

    def test_get_current_percent_multiplier_timedelta(self) -> None:
        group = ManytaskGroupConfig(
            group="group1",
            start="2021-01-01 00:00",
            steps={
                SCORE_50_PERCENT: "1d 09:00:00",
            },
            end="2d 09:00:00",
            tasks=[],
        )

        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 1, 0, 0)) == SCORE_100_PERCENT
        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 2, 0, 0)) == SCORE_100_PERCENT
        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 2, 8, 59)) == SCORE_100_PERCENT
        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 2, 9, 1)) == SCORE_50_PERCENT
        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 3, 8, 59)) == SCORE_50_PERCENT
        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 3, 9, 1)) == SCORE_0_PERCENT
        assert group.get_current_percent_multiplier(now=datetime(2021, 1, 4, 0, 0)) == SCORE_0_PERCENT


class TestManytaskDeadlinesConfig:
    def test_minimal_init(self) -> None:
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            schedule=[],
        )
        assert True

    def test_maximal_init(self) -> None:
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            deadlines="hard",
            max_submissions=TASK_SCORE_10,
            submission_penalty=SCORE_10_PERCENT,
            schedule=[
                {
                    "group": "group1",
                    "start": "2021-01-01 00:00",
                    "end": "2021-01-01 00:00",
                    "tasks": [
                        {
                            "task": "task1",
                            "score": TASK_SCORE_10,
                        },
                    ],
                },
            ],
        )
        assert True

    @pytest.mark.parametrize(
        "timezone",
        [
            "Europe/Moscow1",
            "Asia/Moscow",
            "US",
            "Europe",
            "Europe/Moscow/Moscow",
        ],
    )
    def test_invalid_timezone(self, timezone: str) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone=timezone,
                schedule=[],
            )

    @pytest.mark.parametrize(
        "timezone",
        [
            "CET",
            "UTC",
            "Europe/Moscow",
            "Europe/Kiev",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Europe/Rome",
        ],
    )
    def test_valid_timezone(self, timezone: str) -> None:
        real_timezone = ZoneInfo(timezone)
        real_start = datetime.strptime("2021-01-01 00:00", "%Y-%m-%d %H:%M").replace(tzinfo=real_timezone)
        real_step = real_start + timedelta(days=1)
        real_end = real_start + timedelta(days=2)

        # check all deadlines have timezone set
        deadlines = ManytaskDeadlinesConfig(
            timezone=timezone,
            schedule=[
                {
                    "group": "group1",
                    "start": real_start.strftime("%Y-%m-%d %H:%M"),
                    "steps": {
                        SCORE_50_PERCENT: real_step.strftime("%Y-%m-%d %H:%M"),
                    },
                    "end": real_end.strftime("%Y-%m-%d %H:%M"),
                    "tasks": [
                        {
                            "task": "task1",
                            "score": TASK_SCORE_10,
                        },
                    ],
                },
            ],
        )

        assert deadlines.timezone == timezone

        for group in deadlines.get_groups():
            assert group.start.tzinfo == real_timezone
            assert group.start.time() == real_start.time()
            for _, date in group.steps.items():
                if isinstance(date, datetime):
                    assert date.tzinfo == real_timezone
                    assert date.time() == real_step.time()
            if isinstance(group.end, datetime):
                assert group.end.tzinfo == real_timezone
                assert group.end.time() == real_end.time()

    def test_invalid_deadlines(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                deadlines="hard1",
                schedule=[],
            )

    def test_valid_deadlines(self) -> None:
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            deadlines="hard",
            schedule=[],
        )
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            deadlines="interpolate",
            schedule=[],
        )

    @pytest.mark.parametrize(
        "max_submissions",
        [MAX_SUBMISSIONS_NEGATIVE, WINDOW_0, MAX_SUBMISSIONS_INVALID_FLOAT],
    )
    def test_invalid_max_submissions(self, max_submissions: Any) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                max_submissions=max_submissions,
                schedule=[],
            )

    @pytest.mark.parametrize(
        "submission_penalty",
        [MAX_SUBMISSIONS_NEGATIVE, NEGATIVE_SCORE_20_PERCENT],
    )
    def test_invalid_submission_penalty(self, submission_penalty: Any) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                submission_penalty=submission_penalty,
                schedule=[],
            )

    def test_group_names_not_unique(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                schedule=[
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [],
                    },
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [],
                    },
                ],
            )

    def test_task_names_not_unique(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                schedule=[
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task1",
                                "score": TASK_SCORE_10,
                            },
                            {
                                "task": "task2",
                                "score": TASK_SCORE_10,
                            },
                        ],
                    },
                    {
                        "group": "group2",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task1",
                                "score": TASK_SCORE_10,
                            },
                        ],
                    },
                ],
            )

    @pytest.mark.xfail(reason="TODO: fix this")
    def test_group_name_same_as_task_name(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                schedule=[
                    {
                        "group": "group1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task1",
                                "score": TASK_SCORE_10,
                            },
                        ],
                    },
                    {
                        "group": "task1",
                        "start": "2021-01-01 00:00",
                        "end": "2021-01-01 00:00",
                        "tasks": [
                            {
                                "task": "task2",
                                "score": TASK_SCORE_10,
                            },
                        ],
                    },
                ],
            )

        # The only option when we have single task with name same as group name
        ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            schedule=[
                {
                    "group": "group1",
                    "start": "2021-01-01 00:00",
                    "end": "2021-01-01 00:00",
                    "tasks": [
                        {
                            "task": "group1",
                            "score": TASK_SCORE_10,
                        },
                    ],
                },
            ],
        )

    @pytest.mark.parametrize(
        "enabled, started, now, expected_tasks, expected_groups",
        [
            (None, None, None, ["task1_1", "task1_2", "task2_1", "task2_2", "task3_1"], ["group1", "group2", "group3"]),
            (True, None, None, ["task1_1", "task3_1"], ["group1", "group3"]),
            (False, None, None, ["task1_2", "task2_1", "task2_2"], ["group2"]),
            (None, True, None, ["task1_1", "task1_2", "task2_1", "task2_2"], ["group1", "group2"]),
            (None, False, None, ["task3_1"], ["group3"]),
            (True, True, None, ["task1_1"], ["group1"]),
            (True, False, None, ["task3_1"], ["group3"]),
            (None, True, datetime(2021, 1, 1), ["task1_1", "task1_2"], ["group1"]),
            (None, False, datetime(2021, 1, 1), ["task2_1", "task2_2", "task3_1"], ["group2", "group3"]),
        ],
    )
    def test_get_tasks_groups(
        self,
        enabled: bool | None,
        started: bool | None,
        now: datetime | None,
        expected_tasks: list[str],
        expected_groups: list[str],
    ) -> None:
        timezone = ZoneInfo("Europe/Moscow")
        if now is not None:
            now = now.replace(tzinfo=timezone)

        deadlines = ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            schedule=[
                {
                    "group": "group1",
                    "start": "2020-01-01 00:00",
                    "end": "2020-05-01 00:00",
                    "tasks": [
                        {
                            "task": "task1_1",
                            "score": TASK_SCORE_10,
                        },
                        {
                            "task": "task1_2",
                            "enabled": False,
                            "score": TASK_SCORE_10,
                        },
                    ],
                },
                {
                    "group": "group2",
                    "start": "2022-01-01 00:00",
                    "end": "2022-05-01 00:00",
                    "enabled": False,
                    "tasks": [
                        {
                            "task": "task2_1",
                            "score": TASK_SCORE_10,
                        },
                        {
                            "task": "task2_2",
                            "score": TASK_SCORE_10,
                        },
                    ],
                },
                {
                    "group": "group3",
                    "start": "3000-01-01 00:00",
                    "end": "3000-05-01 00:00",
                    "tasks": [
                        {
                            "task": "task3_1",
                            "score": TASK_SCORE_10,
                        },
                    ],
                },
            ],
        )

        groups = deadlines.get_groups(enabled=enabled, started=started, now=now)
        tasks = deadlines.get_tasks(enabled=enabled, started=started, now=now)

        assert len([i.name for i in groups]) == len(expected_groups), "Number of groups is not correct"
        assert len([i.name for i in tasks]) == len(expected_tasks), "Number of tasks is not correct"

    @pytest.mark.parametrize(
        "window, deadline",
        [
            (WINDOW_7, "hard"),
            (WINDOW_0, "interpolate"),
            (WINDOW_NEGATIVE_5, "interpolate"),
            (WINDOW_NEGATIVE_5, "hard"),
            (WINDOW_100, "interpolate"),  # too large (start + window > step.date)
        ],
    )
    def test_not_valid_window(self, window, deadline) -> None:
        with pytest.raises(ValidationError):
            ManytaskDeadlinesConfig(
                timezone="Europe/Moscow",
                deadlines=deadline,
                window=window,
                schedule=[
                    {
                        "group": "group",
                        "start": "2020-01-01 00:00",
                        "end": "2020-05-01 00:00",
                        "steps": {
                            SCORE_50_PERCENT: "2020-03-01 00:00",
                        },
                    },
                ],
            )

    @pytest.mark.parametrize(
        "window, deadline",
        [
            (None, "hard"),
            (WINDOW_7, "interpolate"),
        ],
    )
    def test_valid_window(self, window, deadline) -> None:
        config = ManytaskDeadlinesConfig(
            timezone="Europe/Moscow",
            deadlines=deadline,
            window=window,
            schedule=[
                {
                    "group": "group",
                    "start": "2020-01-01 00:00",
                    "end": "2020-05-01 00:00",
                    "steps": {
                        SCORE_50_PERCENT: "2020-03-01 00:00",
                    },
                },
            ],
        )
        assert config.deadlines.value == deadline
        assert config.window == window

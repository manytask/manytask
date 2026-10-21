from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from checker.configs import CheckerConfig, CheckerSubConfig
from checker.configs.manytask import ManytaskDeadlinesType
from checker.course import Course, FileSystemTask
from checker.exceptions import TestingError
from checker.pipeline import (
    PipelineContext,
    PipelineResult,
    PipelineRunner,
    PipelineStageResult,
)
from checker.tester import Tester


TIMESTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "failures, report, dry_run, expected_error, expected_events",
    [
        (
            set(),
            True,
            False,
            None,
            ["global", "task:first", "report:first", "task:second", "report:second"],
        ),
        (
            {"task:first"},
            True,
            False,
            "Task pipelines failed",
            ["global", "task:first", "task:second", "report:second"],
        ),
        (
            {"report:first"},
            True,
            False,
            "Reporting score failed",
            ["global", "task:first", "report:first", "task:second", "report:second"],
        ),
        (
            {"report:first"},
            False,
            False,
            None,
            ["global", "task:first", "report:first", "task:second", "report:second"],
        ),
        (
            set(),
            True,
            True,
            None,
            ["global", "task:first", "report:first", "task:second", "report:second"],
        ),
        ({"global"}, True, False, "Global pipeline failed", ["global"]),
    ],
)
def test_pipeline_execution_order_and_reporting(
    mocker: MockerFixture,
    tmp_path: Path,
    failures: set[str],
    report: bool,
    dry_run: bool,
    expected_error: str | None,
    expected_events: list[str],
) -> None:
    tasks = [
        FileSystemTask(name, name, CheckerSubConfig.default())
        for name in ("first", "second")
    ]
    course = mocker.Mock(spec=Course)
    course.repository_root = course.reference_root = tmp_path
    course.manytask_config = mocker.Mock()
    course.get_tasks.return_value = tasks
    course.get_group_for_task.return_value = None
    group = mocker.Mock()
    group.tasks = tasks
    group.get_percents_before_deadline.return_value = {
        1.0: TIMESTAMP + timedelta(days=1)
    }
    course.manytask_config.deadlines.get_groups.return_value = [group]
    course.manytask_config.deadlines.deadlines = ManytaskDeadlinesType.HARD
    course.manytask_config.deadlines.window = 0
    config = CheckerConfig.model_validate(
        {
            "version": 1,
            "structure": {},
            "export": {"destination": "https://example.com/public"},
            "testing": {},
        }
    )
    mocker.patch("checker.tester.load_plugins", return_value={})
    tester = Tester(course, config, dry_run=dry_run)
    events: list[str] = []

    def runner(stage: str, task_name: str = "") -> MagicMock:
        label = f"{stage}:{task_name}" if task_name else stage

        def run(context: PipelineContext, *, dry_run: bool) -> PipelineResult:
            events.append(label)
            assert dry_run == (tester.dry_run or (stage == "report" and not report))
            if stage != "global":
                assert "global" in context["outputs"]
                assert context["task"].task_name == task_name
                assert context["task"].task_score_percent == 1.0
            if stage == "report":
                assert context["outputs"]["task"].name == task_name
            context["outputs"][stage] = PipelineStageResult(task_name, False, False)
            return PipelineResult(label in failures, [])

        pipeline = mocker.MagicMock(spec=PipelineRunner)
        pipeline.__len__.return_value = 1
        pipeline.run.side_effect = run
        return pipeline

    tester.global_pipeline = runner("global")
    mocker.patch.object(
        tester,
        "_get_task_pipeline_runner",
        side_effect=lambda task: runner("task", task.name),
    )
    mocker.patch.object(
        tester,
        "_get_task_report_pipeline_runner",
        side_effect=lambda task: runner("report", task.name),
    )
    if expected_error:
        with pytest.raises(TestingError, match=expected_error):
            tester.run(tmp_path, report=report, timestamp=TIMESTAMP)
    else:
        tester.run(tmp_path, report=report, timestamp=TIMESTAMP)
    assert events == expected_events

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs

import pytest
import requests
from pytest_mock import MockerFixture
from requests_mock import Mocker

from checker.configs import CheckerConfig, CheckerSubConfig
from checker.configs.manytask import ManytaskDeadlinesType
from checker.course import Course, FileSystemTask
from checker.exceptions import TestingError
from checker.plugins.manytask import ManytaskPlugin
from checker.plugins.scripts import RunScriptPlugin
from checker.tester import Tester


REPORT_URL = "https://example.com/report"
TIMESTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _create_tester(
    tmp_path: Path, mocker: MockerFixture, failed_tasks: set[str]
) -> Tester:
    tasks = [
        FileSystemTask(name, name, CheckerSubConfig.default())
        for name in ("first", "second")
    ]
    for task in tasks:
        (tmp_path / task.relative_path).mkdir()
    course = mocker.Mock(spec=Course)
    course.repository_root = course.reference_root = tmp_path
    course.get_tasks.return_value = tasks
    course.get_task_parameters.return_value = {}
    course.get_group_for_task.return_value = None
    course.manytask_config = mocker.Mock()
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
            "testing": {
                "tasks_pipeline": [
                    {
                        "name": "Test task",
                        "run": "run_script",
                        "args": {
                            "origin": "${{ global.temp_dir }}/${{ task.task_sub_path }}",
                            "script": [
                                sys.executable,
                                "-c",
                                "import sys; sys.exit(sys.argv[1] in sys.argv[2:])",
                                "${{ task.task_name }}",
                                *sorted(failed_tasks),
                            ],
                        },
                    }
                ],
                "report_pipeline": [
                    {
                        "name": "Report score",
                        "run": "report_score_manytask",
                        "args": {
                            "username": "student",
                            "task_name": "${{ task.task_name }}",
                            "score": "${{ task.task_score_percent }}",
                            "report_url": REPORT_URL,
                            "report_token": "test-token",
                            "check_deadline": True,
                        },
                    }
                ],
            },
        }
    )
    mocker.patch(
        "checker.tester.load_plugins",
        return_value={
            "run_script": RunScriptPlugin,
            "report_score_manytask": ManytaskPlugin,
        },
    )
    return Tester(course, config)


@pytest.mark.parametrize("failed_tasks", [set(), {"second"}])
def test_report_rejection_names_failed_reports_alongside_task_failures(
    tmp_path: Path,
    mocker: MockerFixture,
    capsys: pytest.CaptureFixture[str],
    failed_tasks: set[str],
) -> None:
    tester = _create_tester(tmp_path, mocker, failed_tasks)
    expected = "Reporting score failed for: ['first']"
    if failed_tasks:
        expected = "Task pipelines failed: ['second']; " + expected

    with Mocker() as reports:
        reports.post(
            REPORT_URL,
            [
                {"status_code": 403, "text": "Invalid course token"},
                {"json": {"score": 1.0}},
            ],
        )
        with pytest.raises(TestingError, match=f"^{re.escape(expected)}$"):
            tester.run(tmp_path, timestamp=TIMESTAMP)

    output = capsys.readouterr().err
    assert "Manytask returned HTTP 403:\nInvalid course token" in output
    if not failed_tasks:
        assert len(reports.request_history) == 2
        assert "Report for task 'second'" in output


def test_network_failure_does_not_prevent_later_task_and_report(
    tmp_path: Path, mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    tester = _create_tester(tmp_path, mocker, set())
    with Mocker() as reports:
        reports.post(
            REPORT_URL,
            [
                {"exc": requests.ConnectionError("connection interrupted")},
                {"json": {"score": 1.0}},
            ],
        )
        with pytest.raises(
            TestingError, match=re.escape("Reporting score failed for: ['first']")
        ):
            tester.run(tmp_path, timestamp=TIMESTAMP)

    assert len(reports.request_history) == 2
    assert reports.request_history[1].text is not None
    assert parse_qs(reports.request_history[1].text)["task"] == ["second"]
    output = capsys.readouterr().err
    assert "Unable to send score to Manytask: connection interrupted" in output
    assert "Run <second> task pipeline:" in output
    assert "Report for task 'second'" in output

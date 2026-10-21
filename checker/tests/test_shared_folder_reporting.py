from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

import git
import pytest
import requests
import yaml
from click.testing import CliRunner, Result
from requests_mock import Mocker

from checker.__main__ import cli


TASK_NAMES = ("seq-read", "seq-write", "rnd-read", "rnd-write")
REPORT_URL = "https://example.com/report"


def _grade_shared_tasks(
    tmp_path: Path, passing: set[str], *, detect_changes: bool = False
) -> Result:
    student = tmp_path / "student"
    reference = tmp_path / "reference"
    for root in (student, reference):
        (root / "disk_measurement").mkdir(parents=True)
        (root / "disk_measurement/common.cpp").write_text("shared code")
        for name in TASK_NAMES:
            content = "passed" if root == student and name in passing else "failed"
            (root / "disk_measurement" / f"{name}.cpp").write_text(content)

    files: dict[str, Any] = {
        ".checker.yml": {
            "version": 1,
            "structure": {"private_patterns": [".*"]},
            "export": {"destination": "https://example.com/public"},
            "testing": {
                "changes_detection": "last_commit_changes",
                "tasks_pipeline": [
                    {
                        "name": "Test selected disk operation",
                        "run": "run_script",
                        "args": {
                            "origin": "${{ global.temp_dir }}/${{ task.task_sub_path }}",
                            "script": [
                                sys.executable,
                                "-c",
                                "import sys; from pathlib import Path; "
                                "assert Path(sys.argv[1] + '.cpp').read_text() == 'passed'",
                                "${{ task.task_name }}",
                            ],
                        },
                    }
                ],
                "report_pipeline": [
                    {
                        "name": "Report successful disk operation",
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
        },
        ".manytask.yml": {
            "version": 1,
            "settings": {
                "course_name": "shared-folder",
                "gitlab_base_url": "https://example.com",
                "public_repo": "public",
                "students_group": "students",
            },
            "ui": {"task_url_template": "https://example.com/$TASK_NAME"},
            "deadlines": {
                "timezone": "Europe/Moscow",
                "schedule": [
                    {
                        "group": "disk",
                        "start": "2020-01-01 00:00:00",
                        "end": "10000d",
                        "tasks": [{"task": name, "score": 10} for name in TASK_NAMES],
                    }
                ],
            },
        },
        "disk_measurement/.tasks.yml": {
            "version": 1,
            "tasks": {
                name: {"parameters": {"allow_change": [f"{name}.cpp", "common.cpp"]}}
                for name in TASK_NAMES
            },
        },
    }
    for path, config in files.items():
        (reference / path).write_text(yaml.safe_dump(config))
    if detect_changes:
        solution = student / "disk_measurement/seq-read.cpp"
        revised_solution = solution.read_text()
        solution.write_text("failed")
        repository = git.Repo.init(student)
        actor = git.Actor("Checker tests", "checker@example.com")
        repository.index.add(["disk_measurement"])
        repository.index.commit("Initial student files", author=actor, committer=actor)
        solution.write_text(revised_solution)
        repository.index.add(["disk_measurement/seq-read.cpp"])
        repository.index.commit("Solve seq-read", author=actor, committer=actor)
        return CliRunner().invoke(cli, ["grade", str(student), str(reference)])
    return CliRunner().invoke(
        cli, ["grade", str(student), str(reference), "--all-tasks", "--submit-score"]
    )


@pytest.mark.parametrize("passing_task", TASK_NAMES)
def test_successful_shared_task_is_reported_despite_other_failures(
    tmp_path: Path, passing_task: str
) -> None:
    with Mocker() as reports:
        reports.post(REPORT_URL, json={"score": 1.0})
        result = _grade_shared_tasks(tmp_path, {passing_task})

    assert result.exit_code == 1, result.output
    assert "Task pipelines failed:" in result.output
    assert "Reporting score failed" not in result.output
    assert len(reports.request_history) == 1
    assert reports.request_history[0].text is not None
    report = parse_qs(reports.request_history[0].text)
    assert report["task"] == [passing_task]
    assert report["score"] == ["1.0"]
    assert f"Report for task '{passing_task}'" in result.output


def test_report_connection_failure_does_not_prevent_later_shared_task_reporting(
    tmp_path: Path,
) -> None:
    with Mocker() as reports:
        reports.post(
            REPORT_URL,
            [
                {"exc": requests.ConnectionError("connection interrupted")},
                {"json": {"score": 1.0}},
            ],
        )
        result = _grade_shared_tasks(tmp_path, {"seq-read", "seq-write"})

    assert result.exit_code == 1, result.output
    assert len(reports.request_history) == 2
    assert "Report for task 'seq-write'" in result.output
    assert "Task pipelines failed: ['rnd-read', 'rnd-write']" in result.output
    assert "Reporting score failed for: ['seq-read']" in result.output
    assert "Unable to send score to Manytask: connection interrupted" in result.output


def test_rejected_successful_shared_task_report_is_listed_with_failed_tasks(
    tmp_path: Path,
) -> None:
    with Mocker() as reports:
        reports.post(REPORT_URL, status_code=403, text="Invalid course token")
        result = _grade_shared_tasks(tmp_path, {"seq-read"})

    assert result.exit_code == 1, result.output
    assert len(reports.request_history) == 1
    assert (
        "Task pipelines failed: ['seq-write', 'rnd-read', 'rnd-write']" in result.output
    )
    assert "Reporting score failed for: ['seq-read']" in result.output
    assert "Manytask returned HTTP 403:\nInvalid course token" in result.output


def test_automatic_grading_reports_only_the_changed_successful_shared_task(
    tmp_path: Path,
) -> None:
    with Mocker() as reports:
        reports.post(REPORT_URL, json={"score": 1.0})
        result = _grade_shared_tasks(tmp_path, {"seq-read"}, detect_changes=True)

    assert result.exit_code == 0, result.output
    assert "Run <seq-read> task pipeline:" in result.output
    for sibling in TASK_NAMES[1:]:
        assert f"Run <{sibling}> task pipeline:" not in result.output
    assert len(reports.request_history) == 1
    assert reports.request_history[0].text is not None
    report = parse_qs(reports.request_history[0].text)
    assert report["task"] == ["seq-read"]
    assert report["score"] == ["1.0"]
    assert "TESTING PASSED" in result.output

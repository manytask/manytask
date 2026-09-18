from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result

from checker.__main__ import cli
from checker.course import FileSystemTask
from checker.tester import Tester

CHECKER_YML_NAME = ".checker.yml"
MANYTASK_YML_NAME = ".manytask.yml"

CHECKER_YML = """
version: 1

structure:
  ignore_patterns: [".git"]
  public_patterns: ["*"]
  private_patterns: [".*"]

export:
  destination: https://example.com/public

testing:
  changes_detection: last_commit_changes
"""

CHECKER_YML_WITH_SKIP = CHECKER_YML + "  skip_unchanged_tasks: allow_change\n"

MANYTASK_YML = """
version: 1

settings:
  course_name: test
  gitlab_base_url: https://example.com
  public_repo: public
  students_group: students

ui:
  task_url_template: https://example.com/$GROUP_NAME/$TASK_NAME

deadlines:
  timezone: Europe/Berlin
  schedule:
    - group: group1
      start: 2020-10-10 00:00:00
      end: 3000d
      enabled: true
      tasks:
        - task: task1_1
          score: 10
        - task: task1_2
          score: 20
        - task: task1_3
          score: 30
          enabled: false
    - group: group2
      start: 2020-10-10 00:00:00
      end: 3000d
      enabled: true
      tasks:
        - task: task2_1
          score: 30
    - group: group3
      start: 2020-10-10 00:00:00
      end: 3000d
      enabled: false
      tasks:
        - task: task3_1
          score: 40
"""

# task3_1 exists on disk but its group is disabled in .manytask.yml,
# task1_3 exists on disk inside an enabled group but is disabled itself,
# task1_4 exists on disk but is not mentioned in .manytask.yml at all
ALL_ENABLED_TASKS = {"task1_1", "task1_2", "task2_1"}

SKIP_UNCHANGED_MANYTASK_YML = """
version: 1

settings:
  course_name: test
  gitlab_base_url: https://example.com
  public_repo: public
  students_group: students

ui:
  task_url_template: https://example.com/$GROUP_NAME/$TASK_NAME

deadlines:
  timezone: Europe/Berlin
  schedule:
    - group: group1
      start: 2020-10-10 00:00:00
      end: 3000d
      enabled: true
      tasks:
        - task: task_unchanged
          score: 10
        - task: task_changed
          score: 10
"""

TEMPLATE_CONTENT = "TODO: stub\n"
SOLVED_CONTENT = "print('real solution')\n"


@pytest.fixture()
def course_root(tmp_path: Path) -> Path:
    """A course checkout with 3 groups; group3 is disabled in the manytask config."""
    root = tmp_path / "course"
    root.mkdir()

    (root / CHECKER_YML_NAME).write_text(CHECKER_YML)
    (root / MANYTASK_YML_NAME).write_text(MANYTASK_YML)

    for group, tasks in (
        ("group1", ("task1_1", "task1_2", "task1_3", "task1_4")),
        ("group2", ("task2_1",)),
        ("group3", ("task3_1",)),
    ):
        group_dir = root / group
        group_dir.mkdir()
        (group_dir / ".group.yml").write_text("")
        for task in tasks:
            task_dir = group_dir / task
            task_dir.mkdir()
            (task_dir / ".task.yml").write_text("")
            (task_dir / "solution.py").write_text("")

    return root


@pytest.fixture()
def skip_unchanged_course_root(tmp_path: Path) -> Path:
    """A course checkout with 2 tasks: `task_unchanged` matches its published template,
    `task_changed` has an actual solution written by the student.

    `root` and `reference_root` are the same directory here (single-repo setup), so
    `solution.py` is compared against its `solution.py.template` sibling.
    """
    root = tmp_path / "course"
    root.mkdir()

    (root / CHECKER_YML_NAME).write_text(CHECKER_YML)
    (root / MANYTASK_YML_NAME).write_text(SKIP_UNCHANGED_MANYTASK_YML)

    group_dir = root / "group1"
    group_dir.mkdir()
    (group_dir / ".group.yml").write_text("")

    for task, solution in (("task_unchanged", TEMPLATE_CONTENT), ("task_changed", SOLVED_CONTENT)):
        task_dir = group_dir / task
        task_dir.mkdir()
        (task_dir / ".task.yml").write_text('version: 1\nparameters:\n  allow_change: ["solution.py"]\n')
        (task_dir / "solution.py").write_text(solution)
        (task_dir / "solution.py.template").write_text(TEMPLATE_CONTENT)

    return root


@pytest.fixture()
def captured_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace Tester.run with a stub recording the tasks and the report flag."""
    captured: dict[str, Any] = {}

    def fake_run(
        self: Tester,
        origin: Path,
        tasks: list[FileSystemTask] | None = None,
        report: bool = True,
        timestamp: Any = None,
    ) -> None:
        captured["tasks"] = sorted(task.name for task in (tasks or []))
        captured["report"] = report

    monkeypatch.setattr(Tester, "run", fake_run)
    return captured


def run_grade(course_root: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["grade", str(course_root), str(course_root), *args])


class TestGradeTaskSelection:
    def test_all_tasks_grades_every_enabled_task(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "--all-tasks")

        assert result.exit_code == 0, result.output
        assert set(captured_run["tasks"]) == ALL_ENABLED_TASKS

    def test_all_tasks_skips_disabled_tasks(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        run_grade(course_root, "--all-tasks")

        assert "task3_1" not in captured_run["tasks"]

    def test_all_tasks_works_without_git_repository(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        # no .git anywhere: changes detection would fail, the override must not even try
        assert not (course_root / ".git").exists()

        result = run_grade(course_root, "--all-tasks")

        assert result.exit_code == 0, result.output
        assert "DETECT CHANGES FAILED" not in result.output
        assert set(captured_run["tasks"]) == ALL_ENABLED_TASKS

    def test_single_task_selection(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-t", "task1_2")

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task1_2"]

    def test_multiple_task_selection(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-t", "task1_1", "-t", "task2_1")

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task1_1", "task2_1"]

    def test_group_selection(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-g", "group1")

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task1_1", "task1_2"]

    def test_group_selection_skips_disabled_task_of_enabled_group(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-g", "group1")

        assert result.exit_code == 0, result.output
        assert "task1_3" not in captured_run["tasks"]

    def test_group_selection_skips_task_missing_from_config(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-g", "group1")

        assert result.exit_code == 0, result.output
        assert "task1_4" not in captured_run["tasks"]

    def test_group_selection_never_grades_more_than_enabled_tasks(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-g", "group1", "-g", "group2")

        assert result.exit_code == 0, result.output
        assert set(captured_run["tasks"]) == ALL_ENABLED_TASKS

    def test_task_and_group_selection_are_combined(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-g", "group1", "-t", "task2_1")

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task1_1", "task1_2", "task2_1"]

    def test_unknown_task_fails(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-t", "no_such_task")

        assert result.exit_code == 1
        assert "Can't find the tasks" in result.output
        assert "tasks" not in captured_run

    def test_unknown_group_fails(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-g", "no_such_group")

        assert result.exit_code == 1
        assert "Can't find the groups" in result.output
        assert "tasks" not in captured_run

    def test_disabled_task_can_not_be_selected(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "-t", "task3_1")

        assert result.exit_code == 1
        assert "Can't find the tasks" in result.output

    def test_all_tasks_conflicts_with_task(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "--all-tasks", "-t", "task1_1")

        assert result.exit_code != 0
        assert "can not be combined" in result.output
        assert "tasks" not in captured_run

    def test_all_tasks_conflicts_with_group(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        result = run_grade(course_root, "--all-tasks", "-g", "group1")

        assert result.exit_code != 0
        assert "can not be combined" in result.output


class TestGradeReporting:
    def test_override_does_not_report_by_default(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        run_grade(course_root, "--all-tasks")

        assert captured_run["report"] is False

    def test_task_override_does_not_report_by_default(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        run_grade(course_root, "-t", "task1_1")

        assert captured_run["report"] is False

    def test_override_reports_with_submit_score(
        self, course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        run_grade(course_root, "--all-tasks", "--submit-score")

        assert captured_run["report"] is True

    def test_detection_path_still_reports(
        self,
        course_root: Path,
        captured_run: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without an override the CI behaviour is unchanged: detect changes and report."""
        detected = [
            FileSystemTask(name="task1_1", relative_path="group1/task1_1", config=None)
        ]  # type: ignore[arg-type]
        monkeypatch.setattr(
            "checker.course.Course.detect_changes",
            lambda self, detection_type: detected,
        )

        result = run_grade(course_root)

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task1_1"]
        assert captured_run["report"] is True

    def test_no_tasks_detected_exits_cleanly(
        self,
        course_root: Path,
        captured_run: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "checker.course.Course.detect_changes", lambda self, detection_type: []
        )

        result = run_grade(course_root)

        assert result.exit_code == 0, result.output
        assert "No tasks to test" in result.output
        assert "tasks" not in captured_run


class TestGradeSkipUnchangedTasks:
    @pytest.fixture(autouse=True)
    def detect_changes_from_filesystem(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """`skip_unchanged_course_root` has no `.git`, so `last_commit_changes` detection
        would fail; use the real, parsed task list (with `.task.yml` parameters) as
        "detected changes" instead.
        """
        monkeypatch.setattr(
            "checker.course.Course.detect_changes",
            lambda self, detection_type: self.get_tasks(enabled=True),
        )

    def test_unchanged_task_is_skipped(
        self, skip_unchanged_course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        (skip_unchanged_course_root / CHECKER_YML_NAME).write_text(CHECKER_YML_WITH_SKIP)

        result = run_grade(skip_unchanged_course_root)

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task_changed"]
        assert "Skipping <task_unchanged>" in result.output

    def test_changed_task_is_still_graded_and_reported(
        self, skip_unchanged_course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        (skip_unchanged_course_root / CHECKER_YML_NAME).write_text(CHECKER_YML_WITH_SKIP)

        result = run_grade(skip_unchanged_course_root)

        assert result.exit_code == 0, result.output
        assert "task_changed" in captured_run["tasks"]
        assert captured_run["report"] is True

    def test_all_tasks_skipped_exits_cleanly(
        self, skip_unchanged_course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        # make the "changed" task unchanged too
        (skip_unchanged_course_root / "group1" / "task_changed" / "solution.py").write_text(TEMPLATE_CONTENT)
        (skip_unchanged_course_root / CHECKER_YML_NAME).write_text(CHECKER_YML_WITH_SKIP)

        result = run_grade(skip_unchanged_course_root)

        assert result.exit_code == 0, result.output
        assert "No tasks to test" in result.output
        assert "tasks" not in captured_run

    def test_without_skip_unchanged_tasks_nothing_is_skipped(
        self, skip_unchanged_course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        # skip_unchanged_course_root already has plain CHECKER_YML (skip_unchanged_tasks unset)
        result = run_grade(skip_unchanged_course_root)

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task_changed", "task_unchanged"]
        assert "Skipping" not in result.output

    def test_task_override_is_not_skipped(
        self, skip_unchanged_course_root: Path, captured_run: dict[str, Any]
    ) -> None:
        (skip_unchanged_course_root / CHECKER_YML_NAME).write_text(CHECKER_YML_WITH_SKIP)

        result = run_grade(skip_unchanged_course_root, "-t", "task_unchanged")

        assert result.exit_code == 0, result.output
        assert captured_run["tasks"] == ["task_unchanged"]
        assert "Skipping" not in result.output

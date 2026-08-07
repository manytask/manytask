from __future__ import annotations

import gc
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from checker.__main__ import cli
from checker.configs import CheckerExportConfig, CheckerStructureConfig, ManytaskConfig
from checker.course import Course
from checker.exceptions import ExportError
from checker.exporter import Exporter

T_GENERATE_FILE_STRUCTURE = Callable[[dict[str, Any], Path | None], Path]

CHECKER_YML = """\
version: 1
structure:
  ignore_patterns: [".git"]
  public_patterns: ["test_public*", ".task.yml", ".group.yml"]
  private_patterns: ["*private*"]
export:
  destination: https://example.com
  templates: search_or_create
testing:
  changes_detection: last_commit_changes
"""

MANYTASK_YML = """\
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
      start: 2021-01-01 00:00:00
      end: 5000d
      tasks:
        - task: task1
          score: 10
"""


class TestPrepareTargetDir:
    """`prepare_target_dir` guards a user-supplied path against accidental data loss."""

    def test_creates_missing_dir_with_parents(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "merged"

        Exporter.prepare_target_dir(target)

        assert target.is_dir()

    def test_existing_empty_dir_is_accepted(self, tmp_path: Path) -> None:
        target = tmp_path / "merged"
        target.mkdir()

        Exporter.prepare_target_dir(target)

        assert target.is_dir()

    def test_non_empty_dir_raises_without_force(self, tmp_path: Path) -> None:
        target = tmp_path / "merged"
        target.mkdir()
        (target / "precious.txt").write_text("do not delete me")

        with pytest.raises(ExportError) as exc_info:
            Exporter.prepare_target_dir(target)

        assert "not empty" in str(exc_info.value)
        # the guard must not have touched anything
        assert (target / "precious.txt").read_text() == "do not delete me"

    def test_non_empty_dir_cleared_with_force(self, tmp_path: Path) -> None:
        target = tmp_path / "merged"
        target.mkdir()
        (target / "stale.txt").write_text("old")
        (target / "stale_dir").mkdir()
        (target / "stale_dir" / "nested.txt").write_text("old")

        Exporter.prepare_target_dir(target, force=True)

        assert list(target.iterdir()) == []

    def test_force_preserves_git_folder(self, tmp_path: Path) -> None:
        target = tmp_path / "merged"
        (target / ".git").mkdir(parents=True)
        (target / ".git" / "HEAD").write_text("ref: refs/heads/main")
        (target / "stale.txt").write_text("old")

        Exporter.prepare_target_dir(target, force=True)

        assert (target / ".git" / "HEAD").read_text() == "ref: refs/heads/main"
        assert not (target / "stale.txt").exists()

    def test_dir_with_only_git_is_treated_as_empty(self, tmp_path: Path) -> None:
        target = tmp_path / "merged"
        (target / ".git").mkdir(parents=True)

        # must not raise even without force - a bare checkout is a valid target
        Exporter.prepare_target_dir(target)

        assert (target / ".git").is_dir()

    def test_file_instead_of_dir_raises(self, tmp_path: Path) -> None:
        target = tmp_path / "merged"
        target.write_text("i am a file")

        with pytest.raises(ExportError) as exc_info:
            Exporter.prepare_target_dir(target)

        assert "not a directory" in str(exc_info.value)


class TestExporterWorkingDir:
    """`working_dir` makes the merged tree persistent instead of a temp dir."""

    @pytest.fixture()
    def deadlines(self) -> ManytaskConfig:
        return ManytaskConfig(
            version=1,
            settings={
                "course_name": "test",
                "gitlab_base_url": "https://google.com",
                "public_repo": "public",
                "students_group": "students",
            },
            ui={"task_url_template": "https://example.com/$GROUP_NAME/$TASK_NAME"},
            deadlines={
                "timezone": "Europe/Berlin",
                "schedule": [
                    {
                        "group": "group",
                        "enabled": True,
                        "start": "2021-01-01 00:00:00",
                        "end": "200d",
                        "tasks": [{"task": "task1", "score": 1}],
                    },
                ],
            },
        )

    @pytest.fixture()
    def structure(self) -> CheckerStructureConfig:
        return CheckerStructureConfig(
            ignore_patterns=[".ignore_me"],
            private_patterns=["*private*"],
            public_patterns=["test_public*", ".task.yml"],
        )

    @pytest.fixture()
    def export_config(self) -> CheckerExportConfig:
        return CheckerExportConfig(
            destination="https://example.com",
            templates="search_or_create",
        )

    @pytest.fixture()
    def private_folder(
        self, tmp_path: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE
    ) -> Path:
        layout = {
            "task1": {
                ".task.yml": "",
                # gold solution, hidden from students by the template strategy
                "solution.py": "def add(a, b):\n    # SOLUTION BEGIN\n    return a + b\n    # SOLUTION END\n",
                "test_public.py": "def test_public():\n    pass\n",
                "test_private.py": "def test_private():\n    pass\n",
            },
        }
        generate_file_structure(layout, tmp_path / "private")
        return tmp_path / "private"

    @pytest.fixture()
    def student_folder(
        self, tmp_path: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE
    ) -> Path:
        layout = {
            "task1": {
                "solution.py": "def add(a, b):\n    return a + b  # student's own work\n",
                # student tampering with the public test must be overwritten
                "test_public.py": "def test_public():\n    assert False\n",
            },
        }
        generate_file_structure(layout, tmp_path / "student")
        return tmp_path / "student"

    @pytest.fixture()
    def course(
        self, private_folder: Path, student_folder: Path, deadlines: ManytaskConfig
    ) -> Course:
        return Course(
            manytask_config=deadlines,
            repository_root=student_folder,
            reference_root=private_folder,
        )

    def test_working_dir_is_used_verbatim(
        self,
        tmp_path: Path,
        course: Course,
        structure: CheckerStructureConfig,
        export_config: CheckerExportConfig,
    ) -> None:
        working_dir = tmp_path / "merged"
        working_dir.mkdir()

        exporter = Exporter(course, structure, export_config, working_dir=working_dir)

        assert exporter.temporary_dir == working_dir

    def test_working_dir_disables_cleanup(
        self,
        tmp_path: Path,
        course: Course,
        structure: CheckerStructureConfig,
        export_config: CheckerExportConfig,
    ) -> None:
        working_dir = tmp_path / "merged"
        working_dir.mkdir()

        # explicitly ask for cleanup - it must still be refused for a user-owned path
        exporter = Exporter(
            course, structure, export_config, cleanup=True, working_dir=working_dir
        )

        assert exporter.cleanup is False

    def test_working_dir_survives_garbage_collection(
        self,
        tmp_path: Path,
        course: Course,
        structure: CheckerStructureConfig,
        export_config: CheckerExportConfig,
    ) -> None:
        """Regression guard: deleting the exporter must never delete a real user directory."""
        working_dir = tmp_path / "merged"
        working_dir.mkdir()

        exporter = Exporter(
            course, structure, export_config, cleanup=True, working_dir=working_dir
        )
        exporter.export_for_testing(working_dir)
        del exporter
        gc.collect()

        assert working_dir.is_dir()
        assert (working_dir / "task1" / "solution.py").exists()

    def test_temporary_dir_still_default(
        self,
        course: Course,
        structure: CheckerStructureConfig,
        export_config: CheckerExportConfig,
    ) -> None:
        """Without working_dir the old temp-dir behaviour is untouched."""
        exporter = Exporter(course, structure, export_config)

        assert exporter.temporary_dir.is_dir()
        assert exporter._temporary_dir_manager is not None

    def test_merged_tree_content(
        self,
        tmp_path: Path,
        course: Course,
        structure: CheckerStructureConfig,
        export_config: CheckerExportConfig,
    ) -> None:
        """The merged tree = student's solution + reference tests, gold solution stripped."""
        working_dir = tmp_path / "merged"
        working_dir.mkdir()

        exporter = Exporter(course, structure, export_config, working_dir=working_dir)
        exporter.export_for_testing(working_dir)

        # student's own solution is kept
        solution = (working_dir / "task1" / "solution.py").read_text()
        assert "student's own work" in solution

        # private tests are pulled in from the reference
        assert (working_dir / "task1" / "test_private.py").exists()

        # student's tampered public test is overwritten by the reference one
        public_test = (working_dir / "task1" / "test_public.py").read_text()
        assert "assert False" not in public_test


class TestMergeCommand:
    """End-to-end tests for the `checker merge` CLI command."""

    @pytest.fixture()
    def reference_root(self, tmp_path: Path) -> Path:
        root = tmp_path / "private"
        (root / "group1" / "task1").mkdir(parents=True)
        (root / ".checker.yml").write_text(CHECKER_YML)
        (root / ".manytask.yml").write_text(MANYTASK_YML)
        (root / "group1" / ".group.yml").write_text("")
        (root / "group1" / "task1" / ".task.yml").write_text("")
        (root / "group1" / "task1" / "solution.py").write_text("GOLD SOLUTION\n")
        (root / "group1" / "task1" / "solution.py.template").write_text("TODO\n")
        (root / "group1" / "task1" / "test_public.py").write_text("public test\n")
        (root / "group1" / "task1" / "test_private.py").write_text("private test\n")
        return root

    @pytest.fixture()
    def student_root(self, tmp_path: Path) -> Path:
        root = tmp_path / "student"
        (root / "group1" / "task1").mkdir(parents=True)
        (root / "group1" / "task1" / "solution.py").write_text("STUDENT SOLUTION\n")
        return root

    def test_merge_happy_path(
        self, tmp_path: Path, reference_root: Path, student_root: Path
    ) -> None:
        output_dir = tmp_path / "merged"

        result = CliRunner().invoke(
            cli,
            ["merge", str(student_root), str(reference_root), str(output_dir), "-s"],
        )

        assert result.exit_code == 0, result.output
        # student's work is in the merged tree, the gold solution is not
        solution = (output_dir / "group1" / "task1" / "solution.py").read_text()
        assert solution == "STUDENT SOLUTION\n"
        # private tests come from the reference
        assert (output_dir / "group1" / "task1" / "test_private.py").exists()

    def test_merge_creates_missing_output_dir(
        self, tmp_path: Path, reference_root: Path, student_root: Path
    ) -> None:
        output_dir = tmp_path / "does" / "not" / "exist"

        result = CliRunner().invoke(
            cli,
            ["merge", str(student_root), str(reference_root), str(output_dir), "-s"],
        )

        assert result.exit_code == 0, result.output
        assert output_dir.is_dir()

    def test_merge_refuses_non_empty_output_dir(
        self, tmp_path: Path, reference_root: Path, student_root: Path
    ) -> None:
        output_dir = tmp_path / "merged"
        output_dir.mkdir()
        (output_dir / "precious.txt").write_text("do not delete me")

        result = CliRunner().invoke(
            cli,
            ["merge", str(student_root), str(reference_root), str(output_dir), "-s"],
        )

        assert result.exit_code == 1
        # nothing was destroyed
        assert (output_dir / "precious.txt").read_text() == "do not delete me"

    def test_merge_force_clears_non_empty_output_dir(
        self, tmp_path: Path, reference_root: Path, student_root: Path
    ) -> None:
        output_dir = tmp_path / "merged"
        output_dir.mkdir()
        (output_dir / "stale.txt").write_text("old")

        result = CliRunner().invoke(
            cli,
            [
                "merge",
                str(student_root),
                str(reference_root),
                str(output_dir),
                "--force",
                "-s",
            ],
        )

        assert result.exit_code == 0, result.output
        assert not (output_dir / "stale.txt").exists()
        assert (output_dir / "group1" / "task1" / "solution.py").exists()

    def test_merge_dry_run_writes_nothing(
        self, tmp_path: Path, reference_root: Path, student_root: Path
    ) -> None:
        output_dir = tmp_path / "merged"

        result = CliRunner().invoke(
            cli,
            [
                "merge",
                str(student_root),
                str(reference_root),
                str(output_dir),
                "--dry-run",
                "-s",
            ],
        )

        assert result.exit_code == 0, result.output
        assert not (output_dir / "group1").exists()

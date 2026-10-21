from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from checker.configs import CheckerExportConfig, CheckerStructureConfig, ManytaskConfig
from checker.course import Course
from checker.exceptions import BadStructure
from checker.exporter import Exporter
from checker.tester import Tester

T_GENERATE_FILE_STRUCTURE = Callable[[dict[str, Any], Path | None], Path]


class TestExporterTaskPreparation:
    @pytest.fixture()
    def task_exporter(
        self, tmp_path: Path, generate_file_structure: T_GENERATE_FILE_STRUCTURE
    ) -> Exporter:
        reference = tmp_path / "reference"
        student = tmp_path / "student"
        generate_file_structure(
            {
                "group": {
                    ".group.yml": "version: 1\nstructure:\n  ignore_patterns: [ignored*, cache]\n",
                    "shared": {
                        ".task.yml": "",
                        "alpha.py": "reference alpha",
                        "alpha.py.template": "published alpha",
                        "beta.py": "reference beta",
                        "test_public.py": "reference tests",
                        ".private": "reference private",
                        "ignored.txt": "reference ignored",
                        "src": {
                            "extra.py": "reference extra",
                            "ignored.py": "reference ignored",
                        },
                        "cache": {"result.py": "reference cached"},
                    },
                }
            },
            reference,
        )
        generate_file_structure(
            {
                "group": {
                    "shared": {
                        "alpha.py": "student alpha",
                        "beta.py": "student beta",
                        "test_public.py": "student tests",
                        ".private": "student private",
                        "ignored.txt": "student ignored",
                        "extra.txt": "student extra",
                        "src": {
                            "extra.py": "student extra",
                            "ignored.py": "student ignored",
                        },
                        "cache": {"result.py": "student cached"},
                    }
                }
            },
            student,
        )
        deadlines = ManytaskConfig(
            version=1,
            settings={
                "course_name": "test",
                "gitlab_base_url": "https://example.com",
                "public_repo": "public",
                "students_group": "students",
            },
            ui={"task_url_template": "https://example.com/$GROUP_NAME/$TASK_NAME"},
            deadlines={
                "timezone": "Europe/Moscow",
                "schedule": [
                    {
                        "group": "group",
                        "start": "2021-01-01 00:00:00",
                        "end": "200d",
                        "tasks": [
                            {"task": "shared", "score": 1},
                        ],
                    }
                ],
            },
        )
        return Exporter(
            Course(deadlines, student, reference),
            CheckerStructureConfig(
                ignore_patterns=["global_ignore"],
                public_patterns=[".task.yml", "test_public.py"],
                private_patterns=[".*"],
            ),
            CheckerExportConfig(destination="https://example.com", templates="search"),
        )

    def test_prepare_task_limits_student_files_and_resets_between_preparations(
        self, task_exporter: Exporter
    ) -> None:
        target = task_exporter.temporary_dir
        tasks = task_exporter.course.potential_tasks
        folder = target / "group/shared"
        task_exporter.export_for_testing(target)

        task_exporter.prepare_task_for_testing(
            target, tasks["shared"], ["alpha.py", "src"]
        )

        assert (folder / "alpha.py").read_text() == "student alpha"
        assert (folder / "beta.py").read_text() == "reference beta"
        assert (folder / "test_public.py").read_text() == "reference tests"
        assert (folder / ".private").read_text() == "reference private"
        assert (folder / "src/extra.py").read_text() == "student extra"
        assert not (folder / "ignored.txt").exists()
        assert not (folder / "src/ignored.py").exists()
        assert not (folder / "cache").exists()
        assert not (folder / "extra.txt").exists()

        (folder / "generated.txt").write_text("artifact from alpha")
        task_exporter.prepare_task_for_testing(target, tasks["shared"], ["beta.py"])

        assert (folder / "alpha.py").read_text() == "reference alpha"
        assert (folder / "beta.py").read_text() == "student beta"
        assert (folder / "src/extra.py").read_text() == "reference extra"
        assert not (folder / "generated.txt").exists()

    def test_prepare_task_empty_patterns_uses_reference_verbatim(
        self, task_exporter: Exporter
    ) -> None:
        task = task_exporter.course.potential_tasks["shared"]
        reference_file = task_exporter.reference_root / task.relative_path / "alpha.py"
        reference_file.write_text("SOLUTION BEGIN\nreference alpha\nSOLUTION END")

        task_exporter.prepare_task_for_testing(task_exporter.temporary_dir, task, [])

        assert (
            task_exporter.temporary_dir / task.relative_path / "alpha.py"
        ).read_text() == reference_file.read_text()

    @pytest.mark.parametrize("dry_run, patterns", [(False, None), (True, ["alpha.py"])])
    def test_prepare_task_preserves_legacy_or_dry_run(
        self, task_exporter: Exporter, dry_run: bool, patterns: list[str] | None
    ) -> None:
        task = task_exporter.course.potential_tasks["shared"]
        task_exporter.dry_run = dry_run
        folder = task_exporter.temporary_dir / task.relative_path
        folder.mkdir(parents=True)
        (folder / "existing.txt").write_text("existing")

        task_exporter.prepare_task_for_testing(
            task_exporter.temporary_dir, task, patterns
        )

        assert sorted(path.name for path in folder.iterdir()) == ["existing.txt"]

    @pytest.mark.parametrize("which_root", ["reference_root", "repository_root"])
    @pytest.mark.parametrize("use_ancestor", [True, False])
    def test_prepare_task_refuses_to_overwrite_source(
        self, task_exporter: Exporter, which_root: str, use_ancestor: bool
    ) -> None:
        task = task_exporter.course.potential_tasks["shared"]
        source = getattr(task_exporter, which_root)
        before = (source / task.relative_path / "alpha.py").read_bytes()

        with pytest.raises(BadStructure, match="must not overlap"):
            task_exporter.prepare_task_for_testing(
                source.parent if use_ancestor else source, task, ["alpha.py"]
            )

        assert (source / task.relative_path / "alpha.py").read_bytes() == before

    def test_prepare_task_ignores_external_student_symlinks(
        self, task_exporter: Exporter, tmp_path: Path
    ) -> None:
        task = task_exporter.course.potential_tasks["shared"]
        student_file = task_exporter.repository_root / task.relative_path / "alpha.py"
        external_file = tmp_path / "outside.py"
        external_file.write_text("external content")
        student_file.unlink()
        student_file.symlink_to(external_file)

        task_exporter.prepare_task_for_testing(
            task_exporter.temporary_dir, task, ["alpha.py", "src"]
        )

        assert not (
            task_exporter.temporary_dir / task.relative_path / "alpha.py"
        ).exists()

    def test_prepare_task_preserves_deleted_allowed_files(
        self, task_exporter: Exporter
    ) -> None:
        task = task_exporter.course.potential_tasks["shared"]
        student_folder = task_exporter.repository_root / task.relative_path
        (student_folder / "alpha.py").unlink()
        (student_folder / "src/extra.py").unlink()

        task_exporter.prepare_task_for_testing(
            task_exporter.temporary_dir, task, ["alpha.py", "src"]
        )

        folder = task_exporter.temporary_dir / task.relative_path
        assert not (folder / "alpha.py").exists()
        assert not (folder / "src/extra.py").exists()
        assert (folder / "beta.py").read_text() == "reference beta"

    @pytest.mark.parametrize("restrict_to_task", [False, True])
    def test_file_collection_keeps_legacy_link_behavior_unless_restricted(
        self, task_exporter: Exporter, tmp_path: Path, restrict_to_task: bool
    ) -> None:
        folder = task_exporter.repository_root / "group/shared"
        outside = tmp_path / "external"
        outside.mkdir()
        (outside / "linked.py").write_text("external")
        (folder / "link.py").symlink_to(outside / "linked.py")
        (folder / "src/link.py").symlink_to(outside / "linked.py")
        (folder / "linked_dir").symlink_to(outside, target_is_directory=True)
        patterns = ["link.py", "src", "linked_dir"]

        files = task_exporter._collect_student_files(
            folder, patterns, restrict_to_task=restrict_to_task
        )

        expected = {Path("src/extra.py"), Path("src/ignored.py")}
        if not restrict_to_task:
            expected.update(
                map(Path, ["link.py", "src/link.py", "linked_dir/linked.py"])
            )
        assert set(files) == expected
        if not restrict_to_task:
            assert task_exporter._collect_student_files(folder, patterns) == files


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("replacement", ["directory", "file", "symlink"])
def test_folder_snapshots_restore_contents_and_absence(
    tmp_path: Path, dry_run: bool, replacement: str
) -> None:
    origin = tmp_path / "workspace"
    folder = origin / "present"
    folder.mkdir(parents=True)
    (folder / "original.txt").write_text("original")
    (folder / "link.txt").symlink_to("original.txt")

    with Tester._snapshot_task_folders(
        origin, {"present", "missing"}, dry_run=dry_run
    ) as snapshots:
        if dry_run:
            assert snapshots == {}
            assert (folder / "original.txt").read_text() == "original"
            return
        backup = snapshots["present"]
        assert backup is not None
        (folder / "original.txt").write_text("changed")
        (folder / "generated.txt").write_text("artifact")
        if replacement != "directory":
            for entry in folder.iterdir():
                entry.unlink()
            folder.rmdir()
            if replacement == "file":
                folder.write_text("replaced by pipeline")
            else:
                folder.symlink_to(backup, target_is_directory=True)
        missing = origin / "missing"
        missing.mkdir()
        (missing / "generated.txt").write_text("artifact")

        Tester._restore_task_folder(folder, backup)
        Tester._restore_task_folder(missing, snapshots["missing"])

        assert (folder / "original.txt").read_text() == "original"
        assert (folder / "link.txt").is_symlink()
        assert not (folder / "generated.txt").exists()
        assert not missing.exists()
    assert not backup.exists()


def test_folder_snapshots_cleanup_after_pipeline_error(tmp_path: Path) -> None:
    (tmp_path / "task").mkdir()
    with pytest.raises(RuntimeError, match="pipeline failed"):
        with Tester._snapshot_task_folders(tmp_path, {"task"}) as snapshots:
            backup = snapshots["task"]
            assert backup is not None and backup.exists()
            raise RuntimeError("pipeline failed")
    assert not backup.exists()

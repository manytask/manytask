from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from checker.configs import CheckerExportConfig, CheckerStructureConfig, ManytaskConfig
from checker.course import Course
from checker.exceptions import BadStructure
from checker.exporter import Exporter

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

    @pytest.mark.parametrize(
        "selected", [("alpha",), ("beta",), ("alpha", "beta"), ("beta", "alpha")]
    )
    def test_prepare_selected_tasks_combines_patterns_in_a_shared_folder(
        self, task_exporter: Exporter, selected: tuple[str, ...]
    ) -> None:
        target = task_exporter.temporary_dir
        task = task_exporter.course.potential_tasks["shared"]
        tasks = [replace(task, name=name) for name in selected]
        task_exporter.export_for_testing(target)

        task_exporter.prepare_tasks_for_testing(
            target, tasks, {name: [f"{name}.py", "src"] for name in selected}
        )

        folder = target / task.relative_path
        for name in ("alpha", "beta"):
            expected = "student" if name in selected else "reference"
            assert (folder / f"{name}.py").read_text() == f"{expected} {name}"
        assert (folder / "test_public.py").read_text() == "reference tests"
        assert (folder / ".private").read_text() == "reference private"
        assert (folder / "src/extra.py").read_text() == "student extra"
        assert not (folder / "ignored.txt").exists()
        assert not (folder / "src/ignored.py").exists()
        assert not (folder / "cache").exists()
        assert not (folder / "extra.txt").exists()

    @pytest.mark.parametrize("order", [("alpha", "beta"), ("beta", "alpha")])
    def test_unrestricted_task_preserves_the_shared_legacy_export(
        self, task_exporter: Exporter, order: tuple[str, str]
    ) -> None:
        target = task_exporter.temporary_dir
        task = task_exporter.course.potential_tasks["shared"]
        task_exporter.export_for_testing(target)
        folder = target / task.relative_path
        (folder / "prepared.txt").write_text("keep existing preparation")

        task_exporter.prepare_tasks_for_testing(
            target,
            [replace(task, name=name) for name in order],
            {"alpha": ["alpha.py"], "beta": None},
        )

        assert (folder / "alpha.py").read_text() == "student alpha"
        assert (folder / "beta.py").read_text() == "student beta"
        assert (folder / "extra.txt").read_text() == "student extra"
        assert (folder / "prepared.txt").read_text() == "keep existing preparation"

    def test_preparation_keeps_patterns_separate_between_folders(
        self, task_exporter: Exporter
    ) -> None:
        task = task_exporter.course.potential_tasks["shared"]
        other = replace(task, name="other", relative_path="group/other")
        for root, content in (
            (task_exporter.reference_root, "reference"),
            (task_exporter.repository_root, "student"),
        ):
            folder = root / other.relative_path
            folder.mkdir()
            for name in ("alpha", "beta"):
                (folder / f"{name}.py").write_text(f"{content} other {name}")
        target = task_exporter.temporary_dir
        task_exporter.export_for_testing(target)

        task_exporter.prepare_tasks_for_testing(
            target, [task, other], {task.name: ["alpha.py"], other.name: ["beta.py"]}
        )

        assert (target / task.relative_path / "alpha.py").read_text() == "student alpha"
        assert (target / task.relative_path / "beta.py").read_text() == "reference beta"
        assert (
            target / other.relative_path / "alpha.py"
        ).read_text() == "reference other alpha"
        assert (
            target / other.relative_path / "beta.py"
        ).read_text() == "student other beta"

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

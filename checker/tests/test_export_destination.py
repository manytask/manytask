from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner, Result

from checker.__main__ import cli
from checker.configs import ManytaskConfig
from checker.course import Course


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(value))


def _create_course(tmp_path: Path) -> Path:
    root = tmp_path / "course"
    group = root / "group"
    group.mkdir(parents=True)
    _write_yaml(group / ".group.yml", {"version": 1})
    _write_yaml(
        root / ".checker.yml",
        {
            "version": 1,
            "structure": {
                "ignore_patterns": [".git"],
                "public_patterns": ["*"],
                "private_patterns": [],
            },
            "export": {"destination": "https://example.com/public"},
            "testing": {},
        },
    )
    _write_yaml(
        root / ".manytask.yml",
        {
            "version": 1,
            "settings": {
                "course_name": "export-destination",
                "gitlab_base_url": "https://example.com",
                "public_repo": "public",
                "students_group": "students",
            },
            "ui": {"task_url_template": "https://example.com/$TASK_NAME"},
            "deadlines": {
                "timezone": "Europe/Moscow",
                "schedule": [
                    {
                        "group": "group",
                        "start": "2020-01-01 00:00:00",
                        "end": "10000d",
                        "tasks": [
                            {"task": name, "score": 10}
                            for name in ("seq-read", "seq-write")
                        ],
                    }
                ],
            },
        },
    )
    for name in ("seq-read", "seq-write"):
        folder = group / name
        folder.mkdir()
        _write_yaml(folder / ".task.yml", {"version": 1})
        (folder / "solution.cpp").write_text(f"source for {name}")
    return root


def _seed_export(root: Path, relative_target: str) -> Path:
    source_entries = list((root / "group").iterdir())
    target = root / relative_target
    target.mkdir(parents=True)
    exported_group = target / "group"
    exported_group.mkdir()
    for entry in source_entries:
        if entry.is_dir():
            shutil.copytree(entry, exported_group / entry.name)
        else:
            shutil.copyfile(entry, exported_group / entry.name)
    (target / ".git").mkdir()
    (target / ".git/metadata").write_text("existing repository metadata")
    (target / "stale.txt").write_text("existing export sentinel")
    return target


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _export(command: str, relative_target: str, *, dry_run: bool) -> Result:
    args = [command]
    if relative_target != "export":
        args.extend([".", relative_target])
    if dry_run:
        args.append("--dry-run")
    return CliRunner().invoke(cli, args)


@pytest.mark.parametrize("command", ["export", "export-private"])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize(
    "relative_target", ["export", "artifacts/output", "group.template"]
)
def test_existing_nested_export_is_excluded_from_discovery_and_copying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    dry_run: bool,
    relative_target: str,
) -> None:
    root = _create_course(tmp_path)
    target = _seed_export(root, relative_target)
    before = _files(target)
    before_paths = {path.relative_to(target) for path in target.rglob("*")}
    source_files = _files(root / "group")
    monkeypatch.chdir(root)

    for _ in range(2):
        result = _export(command, relative_target, dry_run=dry_run)
        assert result.exit_code == 0, (result.output, result.exception)
        if dry_run:
            assert _files(target) == before
            assert {
                path.relative_to(target) for path in target.rglob("*")
            } == before_paths
            continue
        assert _files(target / "group") == source_files
        assert (target / ".git/metadata").read_text() == "existing repository metadata"
        if command == "export":
            assert not (target / "stale.txt").exists()
        else:
            assert (target / "stale.txt").read_text() == "existing export sentinel"
        assert not (target / relative_target).exists()
        assert {
            path.relative_to(target).as_posix() for path in target.rglob(".task.yml")
        } == {f"group/{name}" for name in source_files if name.endswith(".task.yml")}


@pytest.mark.parametrize("command", ["export", "export-private"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_invalid_metadata_in_nested_output_is_not_loaded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    dry_run: bool,
) -> None:
    root = _create_course(tmp_path)
    relative_target = "group/generated/output"
    target = _seed_export(root, relative_target)
    for marker in (".group.yml", ".task.yml"):
        (target / marker).write_text("invalid: [yaml")
    before = _files(target)
    monkeypatch.chdir(root)

    result = _export(command, relative_target, dry_run=dry_run)

    assert result.exit_code == 0, (result.output, result.exception)
    if dry_run:
        assert _files(target) == before
    else:
        for name in ("seq-read", "seq-write"):
            assert (
                target / "group" / name / "solution.cpp"
            ).read_text() == f"source for {name}"
        assert not (target / relative_target).exists()


def test_excluded_output_does_not_replace_real_task_and_group_paths(
    tmp_path: Path,
) -> None:
    root = _create_course(tmp_path)
    target = _seed_export(root, "group/generated/output")
    for marker in (".group.yml", ".task.yml"):
        (target / marker).write_text("invalid: [yaml")
    manytask_config = ManytaskConfig.from_yaml(root / ".manytask.yml")

    course = Course(manytask_config, root, excluded_paths=[target / ".." / "output"])

    assert {task.relative_path for task in course.potential_tasks.values()} == {
        "group/seq-read",
        "group/seq-write",
    }
    assert set(course.potential_groups) == {"group"}
    group = course.get_groups(enabled=True)[0]
    assert group.relative_path == "group"
    assert {task.relative_path for task in group.tasks} == {
        "group/seq-read",
        "group/seq-write",
    }
    for name in ("seq-read", "seq-write"):
        assert course.get_group_for_task(name) is group


@pytest.mark.parametrize("command", ["export", "export-private"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_existing_nested_export_with_shared_tasks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    dry_run: bool,
) -> None:
    root = _create_course(tmp_path)
    for name in ("seq-read", "seq-write"):
        shutil.rmtree(root / "group" / name)
    shared = root / "group" / "shared"
    shared.mkdir()
    _write_yaml(
        shared / ".tasks.yml",
        {"version": 1, "tasks": {"seq-read": {}, "seq-write": {}}},
    )
    (shared / "solution.cpp").write_text("shared source")
    target = _seed_export(root, "export")
    source_files = _files(root / "group")
    before = _files(target)
    monkeypatch.chdir(root)

    for _ in range(2):
        result = _export(command, "export", dry_run=dry_run)
        assert result.exit_code == 0, (result.output, result.exception)
        if dry_run:
            assert _files(target) == before
        else:
            assert _files(target / "group") == source_files
            assert not (target / "export").exists()

    course = Course(
        ManytaskConfig.from_yaml(root / ".manytask.yml"),
        root,
        excluded_paths=[target],
    )
    assert set(course.potential_tasks) == {"seq-read", "seq-write"}
    for task in course.potential_tasks.values():
        assert task.relative_path == "group/shared"
        assert course.get_group_for_task(task.name) is course.potential_groups["group"]

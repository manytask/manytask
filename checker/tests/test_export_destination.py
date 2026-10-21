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
from checker.exceptions import BadConfig


def _write_yaml(path: Path, value: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(value))


def _create_course(tmp_path: Path, *, shared: bool) -> Path:
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
    if shared:
        folder = group / "disk_measurement"
        folder.mkdir()
        _write_yaml(
            folder / ".tasks.yml",
            {"version": 1, "tasks": {"seq-read": {}, "seq-write": {}}},
        )
        for name in ("seq-read", "seq-write"):
            (folder / f"{name}.cpp").write_text(f"source for {name}")
    else:
        for name in ("seq-read", "seq-write"):
            folder = group / name
            folder.mkdir()
            _write_yaml(folder / ".task.yml", {"version": 1})
            (folder / "solution.cpp").write_text(f"source for {name}")
    return root


def _seed_export(root: Path, relative_target: str) -> Path:
    target = root / relative_target
    target.mkdir(parents=True)
    shutil.copytree(root / "group", target / "group")
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
@pytest.mark.parametrize("shared", [False, True], ids=["legacy-task", "shared-tasks"])
def test_existing_nested_export_is_excluded_from_discovery_and_copying(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    dry_run: bool,
    relative_target: str,
    shared: bool,
) -> None:
    root = _create_course(tmp_path, shared=shared)
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
        config_name = ".tasks.yml" if shared else ".task.yml"
        expected = {
            f"group/{name}" for name in source_files if name.endswith(config_name)
        }
        assert {
            path.relative_to(target).as_posix() for path in target.rglob(config_name)
        } == expected


@pytest.mark.parametrize("command", ["export", "export-private"])
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("shared", [False, True], ids=["legacy-task", "shared-tasks"])
def test_genuine_duplicate_outside_export_is_rejected_before_destination_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    dry_run: bool,
    shared: bool,
) -> None:
    root = _create_course(tmp_path, shared=shared)
    target = _seed_export(root, "artifacts/output")
    if shared:
        duplicate = root / "duplicate"
        duplicate.mkdir()
        shutil.copyfile(
            root / "group/disk_measurement/.tasks.yml", duplicate / ".tasks.yml"
        )
    else:
        duplicate = root / "duplicate/seq-read"
        duplicate.mkdir(parents=True)
        shutil.copyfile(root / "group/seq-read/.task.yml", duplicate / ".task.yml")
    before = _files(target)
    monkeypatch.chdir(root)

    result = _export(command, "artifacts/output", dry_run=dry_run)

    assert result.exit_code != 0
    assert isinstance(result.exception, BadConfig)
    assert "Duplicate task name 'seq-read'" in str(result.exception)
    assert "duplicate" in str(result.exception)
    assert _files(target) == before


def test_excluded_metadata_inside_real_group_is_not_parsed_or_discovered(
    tmp_path: Path,
) -> None:
    root = _create_course(tmp_path, shared=True)
    target = root / "group/generated/output"
    target.mkdir(parents=True)
    for marker in (".group.yml", ".task.yml", ".tasks.yml"):
        (target / marker).write_text("invalid: [yaml")
    nested_group = target / "group"
    nested_group.mkdir()
    shutil.copyfile(root / "group/.group.yml", nested_group / ".group.yml")
    shutil.copytree(root / "group/disk_measurement", nested_group / "disk_measurement")
    manytask_config = ManytaskConfig.from_yaml(root / ".manytask.yml")

    course = Course(manytask_config, root, excluded_paths=[target])

    assert set(course.potential_tasks) == {"seq-read", "seq-write"}
    assert set(course.potential_groups) == {"group"}
    group = course.get_groups(enabled=True)[0]
    assert group.relative_path == "group"
    assert {task.name for task in group.tasks} == {"seq-read", "seq-write"}
    assert {task.relative_path for task in group.tasks} == {"group/disk_measurement"}

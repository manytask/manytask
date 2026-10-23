from __future__ import annotations

from pathlib import Path
from typing import Any

import git
import pytest
import yaml

from checker.configs import CheckerTestingConfig, ManytaskConfig
from checker.course import Course


TASK_NAMES = ("seq-read", "seq-write", "rnd-read", "rnd-write")


def _make_course(
    tmp_path: Path, *, root_folder: bool = False
) -> tuple[Course, git.Repo, Path]:
    folder = tmp_path if root_folder else tmp_path / "disk_measurement"
    folder.mkdir(exist_ok=True)
    (folder / ".tasks.yml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "tasks": {
                    name: {
                        "parameters": {"allow_change": [f"{name}.cpp", "common.cpp"]}
                    }
                    for name in TASK_NAMES
                },
            }
        )
    )
    for name in TASK_NAMES:
        (folder / f"{name}.cpp").write_text(f"previous solution for {name}")
    (folder / "common.cpp").write_text("previous shared solution")
    repository = git.Repo.init(tmp_path)
    repository.config_writer().set_value("user", "name", "Checker tests").release()
    repository.config_writer().set_value(
        "user", "email", "checker@example.com"
    ).release()
    _commit(repository, "Previous solutions")
    config = ManytaskConfig.model_validate(
        {
            "version": 1,
            "settings": {
                "course_name": "shared",
                "gitlab_base_url": "https://example.com",
                "public_repo": "public",
                "students_group": "students",
            },
            "ui": {"task_url_template": "https://example.com/$TASK_NAME"},
            "deadlines": {
                "timezone": "Europe/Moscow",
                "schedule": [
                    {
                        "group": "disk_measurement",
                        "start": "2020-01-01 00:00:00",
                        "end": "10000d",
                        "tasks": [{"task": name, "score": 3} for name in TASK_NAMES],
                    }
                ],
            },
        }
    )
    return Course(config, tmp_path), repository, folder


def _commit(repository: git.Repo, message: str = "Change files") -> None:
    repository.git.add("--all")
    repository.index.commit(message)


def _detect(course: Course, defaults: dict[str, Any] | None = None) -> list[str]:
    return [
        task.name
        for task in course.detect_changes(
            CheckerTestingConfig.ChangesDetectionType.LAST_COMMIT_CHANGES,
            default_parameters=defaults,
        )
    ]


@pytest.mark.parametrize("root_folder", [False, True])
@pytest.mark.parametrize(
    "changed_file, expected",
    [
        ("seq-read.cpp", ["seq-read"]),
        ("common.cpp", list(TASK_NAMES)),
        ("readme.md", []),
        ("nested/seq-read.cpp", []),
    ],
)
def test_shared_folder_selection_uses_only_files_in_commit(
    tmp_path: Path, root_folder: bool, changed_file: str, expected: list[str]
) -> None:
    course, repository, folder = _make_course(tmp_path, root_folder=root_folder)
    path = folder / changed_file
    path.parent.mkdir(exist_ok=True)
    path.write_text("new submission")
    _commit(repository)

    assert _detect(course) == expected


def test_deleted_solution_selects_its_task(tmp_path: Path) -> None:
    course, repository, folder = _make_course(tmp_path)
    (folder / "seq-read.cpp").unlink()
    _commit(repository)

    assert _detect(course) == ["seq-read"]


@pytest.mark.parametrize(
    "pattern, changed_file, expected",
    [
        ("**/solution.cpp", "solution.cpp", ["seq-read"]),
        ("**/solution.cpp", "src/nested/solution.cpp", ["seq-read"]),
        ("src/*.cpp", "src/solution.cpp", ["seq-read"]),
        ("src/*.cpp", "src/nested/solution.cpp", []),
        ("src", "src/nested/solution.cpp", ["seq-read"]),
        ("src/", "src/nested/solution.cpp", ["seq-read"]),
        ("src/", "src", []),
        ("src/**", "src/nested/solution.cpp", ["seq-read"]),
    ],
)
def test_shared_folder_globs_match_from_task_root(
    tmp_path: Path, pattern: str, changed_file: str, expected: list[str]
) -> None:
    course, repository, folder = _make_course(tmp_path)
    course.potential_tasks["seq-read"].config.parameters.root["allow_change"] = [
        pattern
    ]
    path = folder / changed_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("new submission")
    _commit(repository)

    assert _detect(course) == expected


@pytest.mark.parametrize("scope", ["default", "group", "file"])
def test_shared_folder_detection_inherits_editable_patterns(
    tmp_path: Path, scope: str
) -> None:
    course, repository, folder = _make_course(tmp_path)
    path = folder / ".tasks.yml"
    config = yaml.safe_load(path.read_text())
    config["tasks"]["seq-read"]["parameters"].pop("allow_change")
    parameters = {"allow_change": ["inherited.cpp"]}
    defaults = None
    if scope == "default":
        defaults = parameters
    elif scope == "group":
        (folder / ".group.yml").write_text(
            yaml.safe_dump({"version": 1, "parameters": parameters})
        )
    else:
        config["parameters"] = parameters
    path.write_text(yaml.safe_dump(config))
    # Establish config before the submission; it is not part of the detected diff.
    _commit(repository, "Configure inherited patterns")
    course = Course(course.manytask_config, tmp_path)
    (folder / "inherited.cpp").write_text("new submission")
    _commit(repository)

    assert _detect(course, defaults) == ["seq-read"]


@pytest.mark.parametrize("patterns", [None, []])
def test_shared_task_without_patterns_keeps_folder_detection(
    tmp_path: Path, patterns: list[str] | None
) -> None:
    course, repository, folder = _make_course(tmp_path)
    course.potential_tasks["seq-write"].config.parameters.root["allow_change"] = (
        patterns
    )
    (folder / "seq-read.cpp").write_text("new submission")
    _commit(repository)

    assert _detect(course) == ["seq-read", "seq-write"]


def test_shared_folder_detection_includes_all_commits_since_base(
    tmp_path: Path,
) -> None:
    course, repository, folder = _make_course(tmp_path)
    course.base_ref = repository.head.commit.hexsha
    for name in ("seq-read", "rnd-write"):
        (folder / f"{name}.cpp").write_text("new submission")
        _commit(repository)

    assert _detect(course) == ["seq-read", "rnd-write"]


def test_single_task_folder_keeps_folder_detection(tmp_path: Path) -> None:
    course, repository, folder = _make_course(tmp_path)
    course.potential_tasks = {"seq-read": course.potential_tasks["seq-read"]}
    (folder / "readme.md").write_text("updated statement")
    _commit(repository)

    assert _detect(course) == ["seq-read"]

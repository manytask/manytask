from __future__ import annotations

from pathlib import Path

import git
import pytest

from checker.configs import CheckerSubConfig, CheckerTestingConfig, ManytaskConfig
from checker.course import Course, FileSystemTask


def _make_course(tmp_path: Path) -> tuple[Course, git.Repo, Path]:
    folder = tmp_path / "shared"
    folder.mkdir()
    for name in ("one", "two", "common"):
        (folder / f"{name}.cpp").write_text(f"previous {name}")
    repository = git.Repo.init(tmp_path)
    repository.config_writer().set_value("user", "name", "Checker tests").release()
    repository.config_writer().set_value(
        "user", "email", "checker@example.com"
    ).release()
    _commit(repository)
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
                        "group": "shared",
                        "start": "2020-01-01 00:00:00",
                        "end": "10000d",
                        "tasks": [
                            {"task": name, "score": 3} for name in ("one", "two")
                        ],
                    }
                ],
            },
        }
    )
    course = Course(config, tmp_path)
    # The core accepts resolved records from either multi-task config adapter.
    course.potential_tasks = {
        name: FileSystemTask(name, "shared", CheckerSubConfig.default())
        for name in ("one", "two")
    }
    return course, repository, folder


def _commit(repository: git.Repo) -> None:
    repository.git.add("--all")
    repository.index.commit("Change files")


def _detect(course: Course, patterns: dict[str, list[str] | None] | None) -> list[str]:
    return [
        task.name
        for task in course.detect_changes(
            CheckerTestingConfig.ChangesDetectionType.LAST_COMMIT_CHANGES,
            task_patterns=patterns,
        )
    ]


@pytest.mark.parametrize(
    "pattern, changed_file, expected",
    [
        ("one.cpp", "one.cpp", ["one"]),
        ("one.cpp", "two.cpp", ["two"]),
        ("one.cpp", "common.cpp", ["one", "two"]),
        ("one.cpp", "readme.md", []),
        ("one.cpp", "nested/one.cpp", []),
        ("**/one.cpp", "one.cpp", ["one"]),
        ("**/one.cpp", "src/nested/one.cpp", ["one"]),
        ("src/*.cpp", "src/one.cpp", ["one"]),
        ("src/*.cpp", "src/nested/one.cpp", []),
        ("src", "src/nested/one.cpp", ["one"]),
        ("src/", "src", []),
        ("src/", "src/nested/one.cpp", ["one"]),
    ],
)
def test_detection_core_uses_supplied_task_patterns(
    tmp_path: Path, pattern: str, changed_file: str, expected: list[str]
) -> None:
    course, repository, folder = _make_course(tmp_path)
    path = folder / changed_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("new submission")
    _commit(repository)

    assert (
        _detect(
            course, {"one": [pattern, "common.cpp"], "two": ["two.cpp", "common.cpp"]}
        )
        == expected
    )


@pytest.mark.parametrize("patterns", [None, {}, {"one": None}, {"one": []}])
def test_detection_core_without_patterns_keeps_folder_detection(
    tmp_path: Path, patterns: dict[str, list[str] | None] | None
) -> None:
    course, repository, folder = _make_course(tmp_path)
    (folder / "one.cpp").write_text("new submission")
    _commit(repository)

    assert _detect(course, patterns) == ["one", "two"]


def test_detection_core_matches_deleted_student_files(tmp_path: Path) -> None:
    course, repository, folder = _make_course(tmp_path)
    (folder / "one.cpp").unlink()
    _commit(repository)

    assert _detect(course, {"one": ["one.cpp"], "two": ["two.cpp"]}) == ["one"]


def test_detection_core_keeps_single_task_folder_behavior(tmp_path: Path) -> None:
    course, repository, folder = _make_course(tmp_path)
    course.potential_tasks.pop("two")
    (folder / "readme.md").write_text("updated statement")
    _commit(repository)

    assert _detect(course, {"one": ["one.cpp"]}) == ["one"]

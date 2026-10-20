from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent
from typing import Any

import git
import pytest
import yaml
from click.testing import CliRunner, Result

from checker.__main__ import cli


CHECK_TASK = dedent("""\
    import sys
    from pathlib import Path

    name, expected, inherited, repository = sys.argv[1:]
    sibling = 'two' if name == 'one' else 'one'
    assert inherited == 'group value'
    assert Path(name + '.txt').read_text() == expected
    assert Path(sibling + '.txt').read_text() == 'reference ' + sibling
    assert Path('protected.txt').read_text() == 'reference protected'
    assert not Path('injected.txt').exists()
    assert not Path('generated.txt').exists()
    Path('generated.txt').write_text(name)
    Path(sibling + '.txt').write_text('changed by previous pipeline')
    with (Path(repository) / 'executed.txt').open('a') as output:
        output.write(name + '\\n')
""")

REPORT_TASK = dedent("""\
    import sys
    from pathlib import Path

    name, repository = sys.argv[1:]
    assert Path('generated.txt').read_text() == name
    with (Path(repository) / 'reported.txt').open('a') as output:
        output.write(name + '\\n')
""")


def _write_yaml(path: Path, config: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(config))


def _create_course(
    tmp_path: Path,
    order: tuple[str, str] = ("one", "two"),
    *,
    unchanged_one: bool = False,
    skip_unchanged: bool = False,
) -> tuple[Path, Path]:
    student = tmp_path / "student"
    reference = tmp_path / "reference"
    shared_path = Path("group/shared")
    for root in (student, reference):
        (root / shared_path).mkdir(parents=True)

    testing: dict[str, Any] = {"changes_detection": "last_commit_changes"}
    if skip_unchanged:
        testing["skip_unchanged_tasks"] = "allow_change"
    _write_yaml(
        reference / ".checker.yml",
        {
            "version": 1,
            "default_parameters": {"inherited": "default value"},
            "structure": {
                "ignore_patterns": [".git"],
                "public_patterns": [],
                "private_patterns": [".*"],
            },
            "export": {"destination": "https://example.com/public"},
            "testing": testing,
        },
    )
    _write_yaml(
        reference / ".manytask.yml",
        {
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
                        "group": "group",
                        "start": "2020-01-01 00:00:00",
                        "end": "10000d",
                        "tasks": [{"task": name, "score": 10} for name in order],
                    }
                ],
            },
        },
    )
    task_origin = "${{ global.temp_dir }}/${{ task.task_sub_path }}"
    _write_yaml(
        reference / "group/.group.yml",
        {
            "version": 1,
            "parameters": {
                "inherited": "group value",
                "own_content": "group default overridden by task",
            },
            "task_pipeline": [
                {
                    "name": "Check isolated student files",
                    "run": "run_script",
                    "args": {
                        "origin": task_origin,
                        "script": [
                            sys.executable,
                            "-c",
                            CHECK_TASK,
                            "${{ task.task_name }}",
                            "${{ parameters.own_content }}",
                            "${{ parameters.inherited }}",
                            "${{ global.repo_dir }}",
                        ],
                    },
                }
            ],
            "report_pipeline": [
                {
                    "name": "Record the logical task report",
                    "run": "run_script",
                    "args": {
                        "origin": task_origin,
                        "script": [
                            sys.executable,
                            "-c",
                            REPORT_TASK,
                            "${{ task.task_name }}",
                            "${{ global.repo_dir }}",
                        ],
                    },
                }
            ],
        },
    )

    for name in ("one", "two"):
        content = (
            f"reference {name}"
            if unchanged_one and name == "one"
            else f"student {name}"
        )
        _write_yaml(
            reference / shared_path / f".task.{name}.yml",
            {
                "version": 1,
                "editable_patterns": [f"{name}.txt"],
                "parameters": {
                    "allow_change": [f"{name}.txt"],
                    "own_content": content,
                },
            },
        )
        (reference / shared_path / f"{name}.txt").write_text(f"reference {name}")
        (reference / shared_path / f"{name}.txt.template").write_text(
            f"reference {name}"
        )
        (student / shared_path / f"{name}.txt").write_text(content)

    (reference / shared_path / "protected.txt").write_text("reference protected")
    (student / shared_path / "protected.txt").write_text("student tampering")
    (student / shared_path / "injected.txt").write_text("unexpected student file")
    return student, reference


def _grade(student: Path, reference: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["grade", str(student), str(reference), *args])


@pytest.mark.parametrize("order", [("one", "two"), ("two", "one")])
def test_grade_shared_folder_tasks_are_isolated_in_either_order(
    tmp_path: Path, order: tuple[str, str]
) -> None:
    student, reference = _create_course(tmp_path, order)

    result = _grade(student, reference, "--all-tasks", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == list(order)
    assert (student / "reported.txt").read_text().splitlines() == list(order)
    assert (student / "group/shared/one.txt").read_text() == "student one"
    assert (student / "group/shared/two.txt").read_text() == "student two"
    assert (student / "group/shared/protected.txt").read_text() == "student tampering"


def test_grade_selects_one_logical_task_from_a_shared_folder(tmp_path: Path) -> None:
    student, reference = _create_course(tmp_path)

    result = _grade(student, reference, "--task", "two", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == ["two"]
    assert (student / "reported.txt").read_text().splitlines() == ["two"]


@pytest.mark.parametrize("order", [("one", "two"), ("two", "one")])
def test_mixed_shared_tasks_preserve_legacy_student_files_and_global_preparation(
    tmp_path: Path, order: tuple[str, str]
) -> None:
    student, reference = _create_course(tmp_path, order)
    checker_path = reference / ".checker.yml"
    checker_config = yaml.safe_load(checker_path.read_text())
    checker_config["testing"]["global_pipeline"] = [
        {
            "name": "Prepare the merged task folder",
            "run": "run_script",
            "args": {
                "origin": "${{ global.temp_dir }}/group/shared",
                "script": [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; "
                    "Path('global.txt').write_text('global preparation')",
                ],
            },
        }
    ]
    _write_yaml(checker_path, checker_config)
    task_path = reference / "group/shared/.task.two.yml"
    task_config = yaml.safe_load(task_path.read_text())
    task_config.pop("editable_patterns")
    task_config["task_pipeline"] = [
        {
            "name": "Check the original merged student folder",
            "run": "run_script",
            "args": {
                "origin": "${{ global.temp_dir }}/${{ task.task_sub_path }}",
                "script": [
                    sys.executable,
                    "-c",
                    dedent("""\
                        import sys
                        from pathlib import Path

                        assert Path('one.txt').read_text() == 'student one'
                        assert Path('two.txt').read_text() == 'student two'
                        assert Path('protected.txt').read_text() == 'student tampering'
                        assert Path('injected.txt').read_text() == 'unexpected student file'
                        assert Path('global.txt').read_text() == 'global preparation'
                        assert not Path('generated.txt').exists()
                        Path('generated.txt').write_text('two')
                        with (Path(sys.argv[1]) / 'executed.txt').open('a') as output:
                            output.write('two\\n')
                    """),
                    "${{ global.repo_dir }}",
                ],
            },
        }
    ]
    _write_yaml(task_path, task_config)

    result = _grade(student, reference, "--all-tasks", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == list(order)
    assert (student / "reported.txt").read_text().splitlines() == list(order)


@pytest.mark.parametrize("skip_unchanged", [False, True])
def test_skip_unchanged_checks_each_shared_task_editable_files(
    tmp_path: Path, skip_unchanged: bool
) -> None:
    student, reference = _create_course(
        tmp_path, unchanged_one=True, skip_unchanged=skip_unchanged
    )
    repository = git.Repo.init(student)
    actor = git.Actor("Checker tests", "checker@example.com")
    repository.index.add(["group/shared"])
    repository.index.commit("Initial student files", author=actor, committer=actor)
    (student / "group/shared/two.txt").write_text("student two revised")
    repository.index.add(["group/shared/two.txt"])
    repository.index.commit("Revise two", author=actor, committer=actor)
    task_config = reference / "group/shared/.task.two.yml"
    config = yaml.safe_load(task_config.read_text())
    config["parameters"]["own_content"] = "student two revised"
    _write_yaml(task_config, config)

    result = _grade(student, reference)

    assert result.exit_code == 0, result.output
    expected = ["two"] if skip_unchanged else ["one", "two"]
    assert (student / "executed.txt").read_text().splitlines() == expected
    assert (student / "reported.txt").read_text().splitlines() == expected
    assert ("Skipping <one>" in result.output) is skip_unchanged

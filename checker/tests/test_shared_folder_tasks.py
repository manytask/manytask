from __future__ import annotations

import base64
import json
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
    import json
    import sys
    from pathlib import Path

    name, expected, inherited, shared, repository = sys.argv[1:]
    assert inherited == 'group value'
    assert shared == 'file value'
    assert Path(name + '.txt').read_text() == expected
    for filename, content in json.loads(Path('expected_workspace.json').read_text()).items():
        assert Path(filename).read_text() == content
    assert Path('global.txt').read_text() == 'global preparation'
    executed = Path(repository) / 'executed.txt'
    previous = executed.read_text().splitlines() if executed.exists() else []
    if previous:
        assert Path('generated.txt').read_text() == previous[-1]
    else:
        assert not Path('generated.txt').exists()
    Path('generated.txt').write_text(name)
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


def _expect_workspace(
    reference: Path, expected: dict[str, str], *, injected: bool = False
) -> None:
    path = reference / ".checker.yml"
    config = yaml.safe_load(path.read_text())
    config["testing"]["global_pipeline"] = [
        {
            "name": "Check all selected files before task pipelines",
            "run": "run_script",
            "args": {
                "origin": "${{ global.temp_dir }}/group/shared",
                "script": [
                    sys.executable,
                    "-c",
                    dedent("""\
                        import base64
                        import json
                        import sys
                        from pathlib import Path

                        expected = json.loads(base64.b64decode(sys.argv[1]))
                        for filename, content in expected.items():
                            assert Path(filename).read_text() == content, filename
                        assert Path('injected.txt').exists() == (sys.argv[2] == 'present')
                        Path('expected_workspace.json').write_text(json.dumps(expected))
                        Path('global.txt').write_text('global preparation')
                    """),
                    # Keep the argument renderer from interpreting JSON as a mapping.
                    base64.b64encode(json.dumps(expected).encode()).decode(),
                    "present" if injected else "absent",
                ],
            },
        }
    ]
    _write_yaml(path, config)


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
                    "name": "Check shared student files",
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
                            "${{ parameters.shared }}",
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

    task_config: dict[str, Any] = {
        "version": 1,
        "parameters": {
            "shared": "file value",
            "own_content": "file default overridden by task",
        },
        "tasks": {},
    }
    for name in ("one", "two"):
        content = (
            f"reference {name}"
            if unchanged_one and name == "one"
            else f"student {name}"
        )
        task_config["tasks"][name] = {
            "parameters": {
                "allow_change": [f"{name}.txt"],
                "own_content": content,
            },
        }
        (reference / shared_path / f"{name}.txt").write_text(f"reference {name}")
        (reference / shared_path / f"{name}.txt.template").write_text(
            f"reference {name}"
        )
        (student / shared_path / f"{name}.txt").write_text(content)

    _write_yaml(reference / shared_path / ".tasks.yml", task_config)
    (reference / shared_path / "protected.txt").write_text("reference protected")
    (student / shared_path / "protected.txt").write_text("student tampering")
    (student / shared_path / "injected.txt").write_text("unexpected student file")
    _expect_workspace(
        reference,
        {
            "one.txt": "reference one" if unchanged_one else "student one",
            "two.txt": "student two",
            "protected.txt": "reference protected",
        },
    )
    return student, reference


def _grade(student: Path, reference: Path, *args: str) -> Result:
    return CliRunner().invoke(cli, ["grade", str(student), str(reference), *args])


@pytest.mark.parametrize("order", [("one", "two"), ("two", "one")])
def test_grade_shared_folder_tasks_use_one_workspace_in_either_order(
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

    _expect_workspace(
        reference,
        {
            "one.txt": "reference one",
            "two.txt": "student two",
            "protected.txt": "reference protected",
        },
    )

    result = _grade(student, reference, "--task", "two", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == ["two"]
    assert (student / "reported.txt").read_text().splitlines() == ["two"]


@pytest.mark.parametrize("scope", ["global", "group", "file"])
def test_allow_change_is_inherited_before_task_file_preparation(
    tmp_path: Path, scope: str
) -> None:
    student, reference = _create_course(tmp_path)
    task_path = reference / "group/shared/.tasks.yml"
    task_config = yaml.safe_load(task_path.read_text())
    task_config["tasks"]["one"]["parameters"].pop("allow_change")
    if scope == "file":
        task_config["parameters"]["allow_change"] = ["one.txt"]
    else:
        path = reference / (".checker.yml" if scope == "global" else "group/.group.yml")
        config = yaml.safe_load(path.read_text())
        config["default_parameters" if scope == "global" else "parameters"][
            "allow_change"
        ] = ["one.txt"]
        _write_yaml(path, config)
    _write_yaml(task_path, task_config)

    result = _grade(student, reference, "--all-tasks", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == ["one", "two"]
    assert (student / "reported.txt").read_text().splitlines() == ["one", "two"]


@pytest.mark.parametrize("order", [("one", "two"), ("two", "one")])
def test_mixed_shared_tasks_preserve_legacy_student_files_and_global_preparation(
    tmp_path: Path, order: tuple[str, str]
) -> None:
    student, reference = _create_course(tmp_path, order)
    task_path = reference / "group/shared/.tasks.yml"
    config = yaml.safe_load(task_path.read_text())
    config["tasks"]["two"]["parameters"].pop("allow_change")
    _write_yaml(task_path, config)
    _expect_workspace(
        reference,
        {
            "one.txt": "student one",
            "two.txt": "student two",
            "protected.txt": "student tampering",
        },
        injected=True,
    )

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
    task_config = reference / "group/shared/.tasks.yml"
    config = yaml.safe_load(task_config.read_text())
    config["tasks"]["two"]["parameters"]["own_content"] = "student two revised"
    _write_yaml(task_config, config)

    _expect_workspace(
        reference,
        {
            "one.txt": "reference one",
            "two.txt": "student two revised",
            "protected.txt": "reference protected",
        },
    )

    result = _grade(student, reference)

    assert result.exit_code == 0, result.output
    expected = ["two"] if skip_unchanged else ["one", "two"]
    assert (student / "executed.txt").read_text().splitlines() == expected
    assert (student / "reported.txt").read_text().splitlines() == expected
    assert ("Skipping <one>" in result.output) is skip_unchanged


def test_grade_inherits_file_defaults_and_uses_entry_pipeline(tmp_path: Path) -> None:
    student, reference = _create_course(tmp_path)
    group_path = reference / "group/.group.yml"
    group_config = yaml.safe_load(group_path.read_text())
    task_path = reference / "group/shared/.tasks.yml"
    task_config = yaml.safe_load(task_path.read_text())
    task_config["task_pipeline"] = group_config.pop("task_pipeline")
    task_config["report_pipeline"] = group_config.pop("report_pipeline")
    task_config["tasks"]["two"]["task_pipeline"] = [
        {
            "name": "Check the entry-specific pipeline and merged parameters",
            "run": "run_script",
            "args": {
                "origin": "${{ global.temp_dir }}/${{ task.task_sub_path }}",
                "script": [
                    sys.executable,
                    "-c",
                    dedent("""\
                        import sys
                        from pathlib import Path

                        shared, own, inherited, repository = sys.argv[1:]
                        assert shared == 'file value'
                        assert own == 'student two'
                        assert inherited == 'group value'
                        assert Path('two.txt').read_text() == own
                        assert Path('one.txt').read_text() == 'student one'
                        assert Path('generated.txt').read_text() == 'one'
                        assert Path('global.txt').read_text() == 'global preparation'
                        Path('generated.txt').write_text('two')
                        repository = Path(repository)
                        (repository / 'custom_pipeline.txt').write_text(shared + '|' + own)
                        with (repository / 'executed.txt').open('a') as output:
                            output.write('two\\n')
                    """),
                    "${{ parameters.shared }}",
                    "${{ parameters.own_content }}",
                    "${{ parameters.inherited }}",
                    "${{ global.repo_dir }}",
                ],
            },
        }
    ]
    _write_yaml(group_path, group_config)
    _write_yaml(task_path, task_config)

    result = _grade(student, reference, "--all-tasks", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == ["one", "two"]
    assert (student / "reported.txt").read_text().splitlines() == ["one", "two"]
    assert (student / "custom_pipeline.txt").read_text() == "file value|student two"


@pytest.mark.parametrize("order", [("one", "two"), ("two", "one")])
def test_empty_patterns_task_uses_the_same_selected_file_union(
    tmp_path: Path, order: tuple[str, str]
) -> None:
    student, reference = _create_course(tmp_path, order)
    path = reference / "group/shared/.tasks.yml"
    config = yaml.safe_load(path.read_text())
    config["tasks"]["one"]["parameters"].update(
        allow_change=[], own_content="reference one"
    )
    _write_yaml(path, config)
    _expect_workspace(
        reference,
        {
            "one.txt": "reference one",
            "two.txt": "student two",
            "protected.txt": "reference protected",
        },
    )

    result = _grade(student, reference, "--all-tasks", "--submit-score")

    assert result.exit_code == 0, result.output
    assert (student / "executed.txt").read_text().splitlines() == list(order)
    assert (student / "reported.txt").read_text().splitlines() == list(order)


def test_shared_workspace_dry_run_does_not_execute_pipelines(tmp_path: Path) -> None:
    student, reference = _create_course(tmp_path)

    result = _grade(student, reference, "--all-tasks", "--dry-run")

    assert result.exit_code == 0, result.output
    assert not (student / "executed.txt").exists()
    assert not (student / "reported.txt").exists()
    assert (student / "group/shared/protected.txt").read_text() == "student tampering"

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from checker.configs import (
    CheckerExportConfig,
    CheckerSubConfig,
    CheckerTaskFileConfig,
    CheckerTasksFileConfig,
)
from checker.exceptions import BadConfig


@pytest.mark.parametrize(
    "patterns",
    [["../solution.py"], ["/tmp/solution.py"], ["src/../../solution.py"], [""]],
)
def test_editable_patterns_stay_in_task_folder(patterns: list[str]) -> None:
    with pytest.raises(ValidationError, match="must stay inside the task folder"):
        CheckerSubConfig(version=1, editable_patterns=patterns)


def test_task_file_merges_common_defaults_with_entry_overrides() -> None:
    config = CheckerTasksFileConfig.model_validate(
        {
            "version": 1,
            "structure": {"private_patterns": [".*"]},
            "editable_patterns": ["shared.py"],
            "parameters": {"timeout": 10, "shared": "common"},
            "task_pipeline": [{"name": "shared", "run": "run_script"}],
            "tasks": {
                "parse": {
                    "editable_patterns": ["parser.py"],
                    "parameters": {"timeout": 20, "nullable": None},
                },
                "render": {},
            },
        }
    )

    tasks = config.resolve_tasks("folder")

    assert list(tasks) == ["parse", "render"]
    assert tasks["parse"].version == 1
    assert tasks["parse"].editable_patterns == ["parser.py"]
    assert tasks["render"].editable_patterns == ["shared.py"]
    assert tasks["parse"].parameters.root == {
        "timeout": 20,
        "shared": "common",
        "nullable": None,
    }
    assert tasks["render"].parameters.root == {"timeout": 10, "shared": "common"}
    assert tasks["parse"].task_pipeline == tasks["render"].task_pipeline
    assert tasks["parse"].structure == tasks["render"].structure == config.structure


@pytest.mark.parametrize("override", [None, []])
def test_task_file_preserves_explicit_null_and_empty_lists(
    override: list[str] | None,
) -> None:
    config = CheckerTasksFileConfig.model_validate(
        {
            "version": 1,
            "editable_patterns": ["common.py"],
            "task_pipeline": [{"name": "shared", "run": "run_script"}],
            "report_pipeline": [{"name": "shared report", "run": "run_script"}],
            "parameters": {"shared": "common"},
            "tasks": {
                "parse": {
                    "editable_patterns": override,
                    "task_pipeline": override,
                    "report_pipeline": override,
                    "parameters": None,
                }
            },
        }
    )

    task = config.resolve_tasks("folder")["parse"]

    assert (
        task.editable_patterns == task.task_pipeline == task.report_pipeline == override
    )
    assert task.parameters is None


@pytest.mark.parametrize(
    "tasks",
    [
        {},
        None,
        [],
        {"": {}},
        {" ": {}},
        {" parse ": {}},
        {1: {}},
        {"parse": None},
        {"parse": {"structure": {}}},
        {"parse": {"version": 1}},
        {"parse": {"tasks": {"nested": {}}}},
        {"parse": {"editable_patterns": ["../solution.py"]}},
    ],
)
def test_task_file_rejects_invalid_task_definitions(tasks: object) -> None:
    with pytest.raises(ValidationError):
        CheckerTasksFileConfig.model_validate({"version": 1, "tasks": tasks})


@pytest.mark.parametrize("tasks", [None, {}, {"parse": {}}])
def test_single_task_file_rejects_tasks_mapping(tasks: object) -> None:
    with pytest.raises(ValidationError, match="Use .tasks.yml"):
        CheckerTaskFileConfig.model_validate({"version": 1, "tasks": tasks})


def test_task_file_rejects_duplicate_yaml_task_names(tmp_path: Path) -> None:
    path = tmp_path / ".tasks.yml"
    path.write_text("version: 1\ntasks:\n  parse: {}\n  parse: {}\n")
    with pytest.raises(BadConfig, match="Duplicate YAML key 'parse'"):
        CheckerTasksFileConfig.from_yaml(path)


def test_task_file_supports_yaml_merge_defaults(tmp_path: Path) -> None:
    path = tmp_path / ".tasks.yml"
    path.write_text(
        "version: 1\nparameters: &common\n  timeout: 10\n  shared: common\n"
        "tasks:\n  parse:\n    parameters:\n      <<: *common\n      timeout: 20\n"
    )

    task = CheckerTasksFileConfig.from_yaml(path).resolve_tasks("folder")["parse"]

    assert task.parameters.root == {"timeout": 20, "shared": "common"}


def test_task_file_schema_describes_named_entries() -> None:
    schema = CheckerTasksFileConfig.get_json_schema()
    tasks = schema["properties"]["tasks"]
    assert tasks["minProperties"] == 1
    assert "tasks" in schema["required"]
    assert "tasks" not in CheckerTaskFileConfig.get_json_schema()["properties"]
    assert CheckerTaskFileConfig.get_json_schema()["not"] == {"required": ["tasks"]}
    entry = schema["$defs"]["CheckerTaskOverrides"]
    assert entry["additionalProperties"] is False
    assert "editable_patterns" in entry["properties"]
    assert "version" not in entry["properties"]
    assert "structure" not in entry["properties"]


@pytest.mark.parametrize("named", [False, True])
def test_task_file_yaml_roundtrip_preserves_inheritance(
    tmp_path: Path, named: bool
) -> None:
    data: dict[str, object] = {
        "version": 1,
        "parameters": {"timeout": 10},
        "report_pipeline": [{"name": "report", "run": "run_script", "fail": "never"}],
    }
    if named:
        data["tasks"] = {
            "parse": {},
            "render": {"parameters": None, "task_pipeline": []},
        }
    model = CheckerTasksFileConfig if named else CheckerTaskFileConfig
    original = model.model_validate(data)
    path = tmp_path / (".tasks.yml" if named else ".task.yml")

    original.to_yaml(path)
    restored = model.from_yaml(path)

    assert original.resolve_tasks("folder") == restored.resolve_tasks("folder")


class TestCheckerExportConfig:
    def test_push_options_default(self) -> None:
        """By default `push_options` is `["ci.skip"]` to preserve backward-compatible
        GitLab behavior (skip pipelines on the auto-export commit)."""
        config = CheckerExportConfig(destination="https://example.com")
        assert config.push_options == ["ci.skip"]

    def test_push_options_default_is_not_shared(self) -> None:
        """Distinct instances must not share the same default list object."""
        a = CheckerExportConfig(destination="https://example.com")
        b = CheckerExportConfig(destination="https://example.com")
        a.push_options.append("mutated")
        assert b.push_options == ["ci.skip"]

    @pytest.mark.parametrize(
        "push_options",
        [
            [],
            ["ci.skip"],
            ["ci.skip", "merge_request.create"],
            ["custom-option"],
        ],
    )
    def test_push_options_override(self, push_options: list[str]) -> None:
        """`push_options` can be set to any list of strings, including an empty list
        (used for git servers that reject push options, e.g. SourceCraft)."""
        config = CheckerExportConfig(
            destination="https://example.com", push_options=push_options
        )
        assert config.push_options == push_options

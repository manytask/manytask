"""Unit tests for course config Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.course_config import (
    CURRENT_SCHEMA_VERSION,
    ChecklistStepUnion,
    CourseConfig,
    FolderStructureStep,
    ForbiddenFilesStep,
    PipelinePassedStep,
    RunStep,
    TaskConfig,
    load_course_config,
)


def _validate_step(payload: dict[str, object]) -> ChecklistStepUnion:
    """Helper: validate a step dict via the discriminated union adapter."""
    from app.models.course_config import ChecklistStepAdapter

    return ChecklistStepAdapter.validate_python(payload)


class TestPipelinePassedStep:
    def test_minimal_payload_validates(self) -> None:
        step = _validate_step({"type": "pipeline_passed"})
        assert isinstance(step, PipelinePassedStep)
        assert step.type == "pipeline_passed"


class TestForbiddenFilesStep:
    def test_with_extensions(self) -> None:
        step = _validate_step({"type": "forbidden_files", "extensions": [".env", ".pyc"]})
        assert isinstance(step, ForbiddenFilesStep)
        assert step.extensions == [".env", ".pyc"]

    def test_missing_extensions_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _validate_step({"type": "forbidden_files"})
        assert "extensions" in str(exc_info.value)


class TestFolderStructureStep:
    def test_with_required_path(self) -> None:
        step = _validate_step({"type": "folder_structure", "required_path": "tasks/{task}/solution.py"})
        assert isinstance(step, FolderStructureStep)
        assert step.required_path == "tasks/{task}/solution.py"

    def test_missing_required_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            _validate_step({"type": "folder_structure"})


class TestRunStep:
    def test_with_command(self) -> None:
        step = _validate_step({"type": "run", "command": "pytest -q"})
        assert isinstance(step, RunStep)
        assert step.command == "pytest -q"


class TestUnknownStepType:
    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _validate_step({"type": "totally_made_up"})
        msg = str(exc_info.value)
        assert "type" in msg.lower()


class TestTaskConfig:
    def test_minimal_task_validates(self) -> None:
        task = TaskConfig.model_validate(
            {
                "name": "task-1",
                "checklist": [{"type": "pipeline_passed"}],
            }
        )
        assert task.name == "task-1"
        assert len(task.checklist) == 1
        assert isinstance(task.checklist[0], PipelinePassedStep)

    def test_task_with_multiple_steps(self) -> None:
        task = TaskConfig.model_validate(
            {
                "name": "task-1",
                "checklist": [
                    {"type": "pipeline_passed"},
                    {"type": "forbidden_files", "extensions": [".env"]},
                    {"type": "folder_structure", "required_path": "tasks/task-1/"},
                    {"type": "run", "command": "pytest"},
                ],
            }
        )
        assert len(task.checklist) == 4

    def test_empty_checklist_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskConfig.model_validate({"name": "task-1", "checklist": []})

    def test_missing_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TaskConfig.model_validate({"checklist": [{"type": "pipeline_passed"}]})

    def test_unknown_step_type_in_task(self) -> None:
        with pytest.raises(ValidationError):
            TaskConfig.model_validate({"name": "task-1", "checklist": [{"type": "nope"}]})


VALID_YAML = """
schema_version: 1
tasks:
  - name: task-1
    checklist:
      - type: pipeline_passed
      - type: forbidden_files
        extensions: [".env", ".pyc"]
  - name: task-2
    checklist:
      - type: folder_structure
        required_path: "tasks/task-2/"
      - type: run
        command: "pytest -q"
"""


class TestCourseConfig:
    def test_default_schema_version(self) -> None:
        cfg = CourseConfig.model_validate({"tasks": [{"name": "t", "checklist": [{"type": "pipeline_passed"}]}]})
        assert cfg.schema_version == CURRENT_SCHEMA_VERSION

    def test_explicit_schema_version(self) -> None:
        cfg = CourseConfig.model_validate(
            {
                "schema_version": 1,
                "tasks": [{"name": "t", "checklist": [{"type": "pipeline_passed"}]}],
            }
        )
        assert cfg.schema_version == 1

    def test_empty_tasks_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CourseConfig.model_validate({"tasks": []})

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CourseConfig.model_validate(
                {
                    "tasks": [{"name": "t", "checklist": [{"type": "pipeline_passed"}]}],
                    "unexpected": "field",
                }
            )


class TestLoadCourseConfig:
    def test_valid_yaml_round_trip(self) -> None:
        cfg = load_course_config(VALID_YAML)
        assert cfg.schema_version == 1
        assert len(cfg.tasks) == 2
        assert cfg.tasks[0].name == "task-1"
        assert isinstance(cfg.tasks[1].checklist[1], RunStep)

    def test_invalid_yaml_syntax_raises_value_error(self) -> None:
        bad = "schema_version: 1\ntasks: [\n  - name: oops\n"
        with pytest.raises(ValueError) as exc_info:
            load_course_config(bad)
        assert "yaml" in str(exc_info.value).lower()

    def test_yaml_with_invalid_step_type_raises_validation_error(self) -> None:
        bad = """
schema_version: 1
tasks:
  - name: task-1
    checklist:
      - type: not_a_real_step
"""
        with pytest.raises(ValidationError) as exc_info:
            load_course_config(bad)
        msg = str(exc_info.value)
        assert "type" in msg.lower()

    def test_yaml_missing_required_field_raises_validation_error(self) -> None:
        bad = """
schema_version: 1
tasks:
  - name: task-1
    checklist:
      - type: forbidden_files
"""
        with pytest.raises(ValidationError) as exc_info:
            load_course_config(bad)
        assert "extensions" in str(exc_info.value)

    def test_yaml_top_level_must_be_mapping(self) -> None:
        with pytest.raises(ValueError):
            load_course_config("- just\n- a\n- list\n")

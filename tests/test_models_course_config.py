"""Unit tests for course config Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.course_config import (
    ChecklistStepUnion,
    FolderStructureStep,
    ForbiddenFilesStep,
    PipelinePassedStep,
    RunStep,
    TaskConfig,
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

"""Pydantic schemas for the `mr_review` section of manytask.yml."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

CURRENT_SCHEMA_VERSION: int = 1
"""Bump when course config layout changes incompatibly."""


class _StepBase(BaseModel):
    """Common config for all step variants — forbid extras to surface typos early."""

    model_config = ConfigDict(extra="forbid")


class PipelinePassedStep(_StepBase):
    type: Literal["pipeline_passed"] = "pipeline_passed"


class ForbiddenFilesStep(_StepBase):
    type: Literal["forbidden_files"] = "forbidden_files"
    extensions: list[str] = Field(min_length=1, description="Forbidden file extensions/globs")


class FolderStructureStep(_StepBase):
    type: Literal["folder_structure"] = "folder_structure"
    required_path: str = Field(min_length=1, description="Required path template")


class RunStep(_StepBase):
    type: Literal["run"] = "run"
    command: str = Field(min_length=1, description="Shell command to run")


ChecklistStepUnion = Annotated[
    Union[PipelinePassedStep, ForbiddenFilesStep, FolderStructureStep, RunStep],
    Field(discriminator="type"),
]

ChecklistStepAdapter: TypeAdapter[ChecklistStepUnion] = TypeAdapter(ChecklistStepUnion)


class TaskConfig(BaseModel):
    """Single task within a course — its checklist of steps."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, description="Task identifier matching folder name")
    checklist: list[ChecklistStepUnion] = Field(min_length=1, description="Ordered checklist steps")


class CourseConfig(BaseModel):
    """Stub for now — fleshed out in Task 5."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION)


def load_course_config(yaml_text: str) -> CourseConfig:
    """Stub — implemented in Task 5."""
    raise NotImplementedError

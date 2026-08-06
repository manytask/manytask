"""Pydantic schemas for the `mr_review` section of manytask.yml."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

CURRENT_SCHEMA_VERSION: int = 2
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
    manual_review: bool = Field(
        default=True,
        description="Whether the polling worker scans this task's MRs for review",
    )
    checklist: list[ChecklistStepUnion] = Field(min_length=1, description="Ordered checklist steps")


class CourseConfig(BaseModel):
    """Root model of the `mr_review` section."""

    model_config = ConfigDict(extra="forbid")
    schema_version: int = Field(default=CURRENT_SCHEMA_VERSION, description="Config layout version")
    gitlab_group: str = Field(min_length=1, description="GitLab group path scanned for student MRs")
    score_comment_pattern: str = Field(
        default="Score: {score}",
        description="Reviewer score comment template; '{score}' is the numeric placeholder",
    )
    tasks: list[TaskConfig] = Field(min_length=1, description="Course tasks")

    @field_validator("score_comment_pattern")
    @classmethod
    def _exactly_one_score_placeholder(cls, value: str) -> str:
        # Reject at upload what compile_score_pattern (app.worker.score_pattern)
        # would otherwise raise on every poll cycle for the course.
        if value.count("{score}") != 1:
            raise ValueError("score_comment_pattern must contain exactly one '{score}' placeholder")
        return value


def load_course_config(yaml_text: str) -> CourseConfig:
    """Parse YAML text and validate against CourseConfig.

    Raises:
        ValueError: YAML syntax error or top-level not a mapping.
        pydantic.ValidationError: schema mismatch with readable details.
    """

    import yaml

    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError as err:
        raise ValueError(f"invalid YAML: {err}") from err

    if not isinstance(raw, dict):
        raise ValueError("course config YAML must be a mapping at the top level")

    return CourseConfig.model_validate(raw)


def load_manytask_yaml(yaml_text: str) -> CourseConfig:
    """Parse full ``manytask.yml`` and validate the ``mr_review`` subsection.

    Raises:
        ValueError: YAML syntax error, top-level not a mapping, or no ``mr_review`` key.
        pydantic.ValidationError: ``mr_review`` exists but does not match ``CourseConfig``.
    """

    import yaml

    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError as err:
        raise ValueError(f"invalid YAML: {err}") from err

    if not isinstance(raw, dict):
        raise ValueError("manytask.yml must be a mapping at the top level")

    mr_review = raw.get("mr_review")
    if mr_review is None:
        raise ValueError("manytask.yml has no `mr_review` section")

    return CourseConfig.model_validate(mr_review)

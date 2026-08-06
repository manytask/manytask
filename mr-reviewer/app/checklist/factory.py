"""Build a CheckStep instance from a validated ChecklistStepUnion config."""

from __future__ import annotations

from app.checklist.builtins import (
    FolderStructureStep,
    ForbiddenFilesStep,
    PipelinePassedStep,
    RunStep,
)
from app.checklist.sandbox import RunSandbox
from app.checklist.step import CheckStep
from app.hosting import HostingAdapter
from app.models import (
    ChecklistStepUnion,
)
from app.models import (
    FolderStructureStep as FolderStructureConfig,
)
from app.models import (
    ForbiddenFilesStep as ForbiddenFilesConfig,
)
from app.models import (
    PipelinePassedStep as PipelinePassedConfig,
)
from app.models import (
    RunStep as RunStepConfig,
)


def build_check_step(
    config: ChecklistStepUnion,
    *,
    hosting: HostingAdapter,
    sandbox: RunSandbox | None,
) -> CheckStep:
    if isinstance(config, PipelinePassedConfig):
        return PipelinePassedStep(hosting=hosting)

    if isinstance(config, ForbiddenFilesConfig):
        return ForbiddenFilesStep(hosting=hosting, extensions=list(config.extensions))

    if isinstance(config, FolderStructureConfig):
        return FolderStructureStep(hosting=hosting, required_path=config.required_path)

    if isinstance(config, RunStepConfig):
        if sandbox is None:
            raise ValueError("run: step requires a RunSandbox to be wired in")
        return RunStep(sandbox=sandbox, command=config.command)

    raise TypeError(f"unknown checklist step config: {type(config).__name__}")

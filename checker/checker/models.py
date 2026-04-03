from dataclasses import dataclass
from typing import TypedDict

from .configs.checker import TParamType


@dataclass
class PipelineStageResult:
    """Result of a single pipeline stage.
    :param name: name of the stage
    :param failed: if True, stage failed
    :param skipped: if True, stage was skipped
    :param percentage: optional percentage of points earned
    :param elapsed_time: optional elapsed time in seconds
    :param output: output of the stage
    """

    name: str
    failed: bool
    skipped: bool
    percentage: float | None = None
    elapsed_time: float | None = None
    output: str = ""

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"PipelineStageResult: failed={int(self.failed)}, "
            f"skipped={int(self.skipped)}, percentage={self.percentage or 1.0:.2f}, name='{self.name}'"
        )


@dataclass
class PipelineResult:
    failed: bool
    stage_results: list[PipelineStageResult]

    def __bool__(self) -> bool:
        return not self.failed

    def __str__(self) -> str:  # pragma: no cover
        return f"PipelineResult: failed={int(self.failed)}\n" + "\n".join(
            [f"  {stage_result}" for stage_result in self.stage_results]
        )


@dataclass
class GlobalPipelineVariables:
    """Base variables passed in pipeline stages."""

    ref_dir: str
    repo_dir: str
    temp_dir: str
    task_names: list[str]
    task_sub_paths: list[str]


@dataclass
class TaskPipelineVariables:
    """Variables passed in pipeline stages for each task."""

    task_name: str
    task_sub_path: str
    task_score_percent: float


PipelineContext = TypedDict(
    "PipelineContext",
    {
        "global": GlobalPipelineVariables,
        "task": TaskPipelineVariables | None,
        "outputs": dict[str, PipelineStageResult],
        "parameters": dict[str, TParamType],
        "env": dict[str, str],
    },
)

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .configs.checker import CheckerConfig, CheckerParametersConfig
from .configs.manytask import ManytaskDeadlinesType
from .course import Course, FileSystemTask
from .exceptions import TestingError
from .pipeline import PipelineResult, PipelineRunner, PipelineStageResult
from .plugins import load_plugins
from .utils import print_header_info, print_info, print_separator


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


class Tester:
    """
    Class to encapsulate all testing logic.
    1. Accept directory with files ready for testing
    2. Execute global pipeline once
    3. For each task:
        3.1. Execute task pipeline
        3.2. Execute report pipeline (optional)
    """

    __test__ = False  # do not collect this class for pytest

    def __init__(
        self,
        course: Course,
        checker_config: CheckerConfig,
        *,
        verbose: bool = False,
        dry_run: bool = False,
    ):
        """
        Init tester in specific public and private dirs.

        :param course: Course object for iteration with physical course
        :param checker_config: Full checker config with testing,structure and params folders
        :param verbose: Whatever to print private outputs and debug info
        :param dry_run: Do not execute anything, just print what would be executed
        :raises exception.ValidationError: if config is invalid or repo structure is wrong
        """
        self.course = course

        self.testing_config = checker_config.testing
        self.structure_config = checker_config.structure
        self.default_params = checker_config.default_parameters

        self.plugins = load_plugins(self.testing_config.search_plugins, verbose=verbose)

        self.global_pipeline = PipelineRunner(self.testing_config.global_pipeline, self.plugins, verbose=verbose)
        self.task_pipeline = PipelineRunner(self.testing_config.tasks_pipeline, self.plugins, verbose=verbose)
        self.report_pipeline = PipelineRunner(self.testing_config.report_pipeline, self.plugins, verbose=verbose)

        self.repository_dir = self.course.repository_root
        self.reference_dir = self.course.reference_root

        self.verbose = verbose
        self.dry_run = dry_run

        group_with_percents = [
            (group, group.get_percents_before_deadline()) for group in course.manytask_config.deadlines.get_groups()
        ]
        self.task_to_percents = {task.name: percs for group, percs in group_with_percents for task in group.tasks}
        self.deadlines_type = course.manytask_config.deadlines.deadlines
        self.interpolation_window = (course.manytask_config.deadlines.window or 0) * 3600 * 24  # in seconds

    def _calc_interpolated_percent(
        self, percent: float, timestamp: datetime, prev_percent: float, prev_timestamp: datetime
    ) -> float:
        frac: float = (timestamp - prev_timestamp).total_seconds() / self.interpolation_window
        return percent if frac >= 1 else prev_percent - frac * (prev_percent - percent)

    def _get_task_score_percent(self, task: str, timestamp: datetime | None = None) -> float:
        timestamp = timestamp or datetime.now(tz=ZoneInfo("Europe/Moscow"))
        steps: dict[float, datetime] = self.task_to_percents[task]
        prev_percent: float = 1
        prev_timestamp: datetime = timestamp
        for percent, ts in steps.items():
            if timestamp <= ts:
                if self.deadlines_type == ManytaskDeadlinesType.HARD:
                    return percent
                return self._calc_interpolated_percent(percent, timestamp, prev_percent, prev_timestamp)
            prev_percent, prev_timestamp = percent, ts
        return 0.0

    def _get_global_pipeline_parameters(
        self,
        origin: Path,
        tasks: list[FileSystemTask],
    ) -> GlobalPipelineVariables:
        return GlobalPipelineVariables(
            ref_dir=self.reference_dir.absolute().as_posix(),
            repo_dir=self.repository_dir.absolute().as_posix(),
            temp_dir=origin.absolute().as_posix(),
            task_names=[task.name for task in tasks],
            task_sub_paths=[task.relative_path for task in tasks],
        )

    def _get_task_pipeline_parameters(
        self,
        task: FileSystemTask,
        score_percent: float,
    ) -> TaskPipelineVariables:
        return TaskPipelineVariables(
            task_name=task.name, task_sub_path=task.relative_path, task_score_percent=score_percent
        )

    def _get_context(
        self,
        global_variables: GlobalPipelineVariables,
        task_variables: TaskPipelineVariables | None,
        outputs: dict[str, PipelineStageResult],
        default_parameters: CheckerParametersConfig,
        task_parameters: CheckerParametersConfig | None,
    ) -> dict[str, Any]:
        return {
            "global": global_variables,
            "task": task_variables,
            "outputs": outputs,
            "parameters": default_parameters.__dict__ | (task_parameters.__dict__ if task_parameters else {}),
            "env": os.environ.__dict__,
        }

    def validate(self) -> None:
        # get all tasks
        tasks = self.course.get_tasks(enabled=True)

        # create outputs to pass to pipeline
        outputs: dict[str, PipelineStageResult] = {}

        # validate global pipeline (only default params and variables available)
        print_info("- global pipeline...")
        global_variables = self._get_global_pipeline_parameters(Path(), tasks)
        context = self._get_context(global_variables, None, outputs, self.default_params, None)
        self.global_pipeline.validate(context, validate_placeholders=True)
        print_info("  ok")

        for task in tasks:
            # validate task with global + task-specific params
            print_info(f"- task {task.name} pipeline...")

            # create task context
            task_score = self._get_task_score_percent(task.name)
            task_variables = self._get_task_pipeline_parameters(task, task_score)
            context = self._get_context(
                global_variables,
                task_variables,
                outputs,
                self.default_params,
                task.config.parameters if task.config else None,
            )

            # check task parameter are
            # TODO: read pipeline from task config if any
            self.task_pipeline.validate(context, validate_placeholders=True)
            self.report_pipeline.validate(context, validate_placeholders=True)

            print_info("  ok")

    def run(
        self,
        origin: Path,
        tasks: list[FileSystemTask] | None = None,
        report: bool = True,
        timestamp: datetime | None = None,
    ) -> None:
        # get all tasks
        tasks = tasks or self.course.get_tasks(enabled=True)

        # create outputs to pass to pipeline
        outputs: dict[str, PipelineStageResult] = {}

        # run global pipeline
        global_variables = self._get_global_pipeline_parameters(origin, tasks)
        if len(self.global_pipeline) > 0 or self.verbose:
            print_header_info("Run global pipeline:", color="pink")
            context = self._get_context(
                global_variables,
                None,
                outputs,
                self.default_params,
                None,
            )
            global_pipeline_result: PipelineResult = self.global_pipeline.run(context, dry_run=self.dry_run)
            print_separator("-")
            print_info(str(global_pipeline_result), color="pink")

            if not global_pipeline_result:
                raise TestingError("Global pipeline failed")

        failed_tasks = []
        for task in tasks:
            # run task pipeline
            print_header_info(f"Run <{task.name}> task pipeline:", color="pink")

            # create task context
            task_score = self._get_task_score_percent(task.name, timestamp)
            task_variables = self._get_task_pipeline_parameters(task, task_score)
            context = self._get_context(
                global_variables,
                task_variables,
                outputs,
                self.default_params,
                task.config.parameters if task.config else None,
            )

            # TODO: read pipeline from task config if any
            task_pipeline_result: PipelineResult = self.task_pipeline.run(context, dry_run=self.dry_run)
            print_separator("-")

            print_info(str(task_pipeline_result), color="pink")
            print_separator("-")

            # Report score if task pipeline succeeded
            if task_pipeline_result:
                print_info(f"Reporting <{task.name}> task tests:", color="pink")
                if report:
                    task_report_result: PipelineResult = self.report_pipeline.run(context, dry_run=self.dry_run)
                    if task_report_result:
                        print_info("->Reporting succeeded")
                    else:
                        print_info("->Reporting failed")
                else:
                    _: PipelineResult = self.report_pipeline.run(context, dry_run=True)
                    print_info("->Reporting disabled (dry-run)")
                print_separator("-")
            else:
                failed_tasks.append(task.name)

        if failed_tasks:
            raise TestingError(f"Task pipelines failed: {failed_tasks}")

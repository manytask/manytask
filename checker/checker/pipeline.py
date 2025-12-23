from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jinja2.nativetypes

from .configs import PipelineStageConfig
from .exceptions import BadConfig, PluginExecutionFailed
from .plugins import PluginABC
from .utils import print_info


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


class ParametersResolver:
    def __init__(self) -> None:
        self.template_env = jinja2.nativetypes.NativeEnvironment(
            loader=jinja2.BaseLoader(),
            variable_start_string="${{",
            variable_end_string="}}",
        )

    def resolve(self, template: str | list[str] | Any, context: dict[str, Any]) -> Any:
        """
        Resolve the template with context.
        * If template is a string, resolve it with jinja2
        * If template is a list, resolve each element of the list
        * If template is a dict, resolve each value of the dict
        * Otherwise, return the template as is
        :param template: template string to resolve, following jinja2 syntax.
        :param context: context to use for resolving.
        :return: resolved template of Any type.
        :raises BadConfig: if template is invalid.
        """
        if isinstance(template, str):
            try:
                template_obj = self.template_env.from_string(template.strip())
                return template_obj.render(**context)
            except jinja2.TemplateError as e:
                raise BadConfig(f"Invalid template {template}") from e
        elif isinstance(template, list):
            return [self.resolve(item, context) for item in template]
        elif isinstance(template, dict):
            return {key: self.resolve(value, context) for key, value in template.items()}
        else:
            return template


class PipelineRunner:
    """Class encapsulating the pipeline execution logic."""

    def __init__(
        self,
        pipeline: list[PipelineStageConfig],
        plugins: dict[str, type[PluginABC]],
        *,
        verbose: bool = False,
    ):
        """
        Init pipeline runner with predefined stages/plugins to use, parameters (placeholders) resolved later.
        :param pipeline: list of pipeline stages
        :param plugins: dict of plugins available to use
        :param verbose: if True, print more debug info for teachers
        :raises BadConfig: if plugin does not exist or does not support isolation (no placeholders are checked)
        """
        self.pipeline = pipeline
        self.plugins = plugins

        self.verbose = verbose

        self.parameters_resolver = ParametersResolver()

        self.validate({}, validate_placeholders=False)

    def __len__(self) -> int:
        return len(self.pipeline)

    def validate(
        self,
        context: dict[str, Any],
        validate_placeholders: bool = True,
    ) -> None:
        """
        Validate the pipeline configuration.
        :param context: context to use for resolving placeholders
        :param validate_placeholders: if True, validate placeholders in pipeline stages
        """

        for pipeline_stage in self.pipeline:
            # validate plugin exists
            if pipeline_stage.run not in self.plugins:
                raise BadConfig(f"Unknown plugin {pipeline_stage.run} in pipeline stage {pipeline_stage.name}")
            plugin_class = self.plugins[pipeline_stage.run]

            # validate args of the plugin (first resolve placeholders)
            if validate_placeholders:
                resolved_args = self.parameters_resolver.resolve(pipeline_stage.args, context)
                plugin_class.validate(resolved_args)

            # validate run_if condition
            if validate_placeholders and pipeline_stage.run_if:
                resolved_run_if = self.parameters_resolver.resolve(pipeline_stage.run_if, context)
                if not isinstance(resolved_run_if, bool):
                    raise BadConfig(
                        f"Invalid run_if condition {pipeline_stage.run_if} in pipeline stage {pipeline_stage.name}"
                    )

            # add output to context if set register parameter
            if pipeline_stage.register_output:
                context.setdefault("outputs", {})[pipeline_stage.register_output] = PipelineStageResult(
                    name=pipeline_stage.name,
                    failed=False,
                    skipped=True,
                    percentage=1.0,
                )

    def _print_verbose_stage_info(
        self,
        pipeline_stage: PipelineStageConfig,
        resolved_run_if: bool | None,
        resolved_args: dict[str, Any],
    ) -> None:
        """Print verbose debug information about a pipeline stage."""
        print_info(f"    run_if: {pipeline_stage.run_if}", color="grey")
        print_info(f"    resolved_run_if: {resolved_run_if}", color="grey")
        print_info(f"    fail: {pipeline_stage.fail}", color="grey")
        print_info(f"    run: {pipeline_stage.run}", color="grey")
        print_info(f"    args: {pipeline_stage.args}", color="grey")
        print_info(f"    resolved_args: {resolved_args}", color="grey")

    def _create_skipped_result(self, name: str) -> PipelineStageResult:
        """Create a skipped stage result."""
        return PipelineStageResult(name=name, failed=False, skipped=True)

    def _run_dry(self, pipeline_stage: PipelineStageConfig) -> PipelineStageResult:
        """Handle dry run for a pipeline stage."""
        print_info("[output here]")
        print_info("dry run!", color="blue")
        return PipelineStageResult(
            name=pipeline_stage.name,
            failed=False,
            skipped=False,
            percentage=1.0,
        )

    def _run_plugin_success(
        self,
        pipeline_stage: PipelineStageConfig,
        result: Any,
        elapsed_time: float,
    ) -> PipelineStageResult:
        """Handle successful plugin execution."""
        print_info(result.output or "[empty output]")
        print_info(f"> elapsed time: {elapsed_time:.2f}s", color="grey")
        print_info("ok!", color="green")
        return PipelineStageResult(
            name=pipeline_stage.name,
            failed=False,
            skipped=False,
            output=result.output,
            percentage=result.percentage,
            elapsed_time=elapsed_time,
        )

    def _run_plugin_failure(
        self,
        pipeline_stage: PipelineStageConfig,
        error: PluginExecutionFailed,
        elapsed_time: float,
        resolved_args: dict[str, Any],
    ) -> tuple[PipelineStageResult, bool, bool]:
        """Handle failed plugin execution.

        Returns:
            tuple: (stage_result, skip_the_rest, pipeline_passed)
        """
        print_info(error.output or "[empty output]")
        if self.verbose:
            print_info(error.message)
        print_info(f"> elapsed time: {elapsed_time:.2f}s", color="grey")

        allow_partial = bool(resolved_args.get("partially_scored", False))
        if allow_partial:
            print_info("error! (ignored due to partially_scored)", color="yellow")

        stage_result = PipelineStageResult(
            name=pipeline_stage.name,
            failed=not allow_partial,  # flip the flag based on partial scoring
            skipped=False,
            output=error.output or "",
            percentage=error.percentage,
            elapsed_time=elapsed_time,
        )

        skip_the_rest = False
        pipeline_passed = True

        # only apply failure handling when not partial
        if not allow_partial:
            if pipeline_stage.fail == PipelineStageConfig.FailType.FAST:
                print_info("error! (now as fail=fast)", color="red")
                skip_the_rest = True
                pipeline_passed = False
            elif pipeline_stage.fail == PipelineStageConfig.FailType.AFTER_ALL:
                print_info("error! (later as fail=after_all)", color="red")
                pipeline_passed = False
            elif pipeline_stage.fail == PipelineStageConfig.FailType.NEVER:
                print_info("error! (ignored as fail=never)", color="red")
            else:
                assert False, f"Unknown fail type {pipeline_stage.fail}"

        return stage_result, skip_the_rest, pipeline_passed

    def run(
        self,
        context: dict[str, Any],
        *,
        dry_run: bool = False,
    ) -> PipelineResult:
        pipeline_stage_results: list[PipelineStageResult] = []
        pipeline_passed = True
        skip_the_rest = False

        for pipeline_stage in self.pipeline:
            # resolve placeholders in arguments
            resolved_args = self.parameters_resolver.resolve(pipeline_stage.args, context=context)
            resolved_run_if = (
                self.parameters_resolver.resolve(pipeline_stage.run_if, context=context)
                if pipeline_stage.run_if is not None
                else None
            )

            # if not verbose and skipping (student mode) dont print anything
            if not dry_run and not self.verbose and (skip_the_rest or resolved_run_if is False):
                continue

            print_info(f'--> Running "{pipeline_stage.name}" stage:', color="orange")
            if self.verbose:
                self._print_verbose_stage_info(pipeline_stage, resolved_run_if, resolved_args)

            # skip the rest of stages if failed before
            if skip_the_rest:
                print_info("skipped! (got error above)", color="blue")
                pipeline_stage_results.append(self._create_skipped_result(pipeline_stage.name))
                continue

            # resolve run condition if any; skip if run_if=False
            if pipeline_stage.run_if is not None and not resolved_run_if:
                print_info(f"skipped! (run_if={resolved_run_if})", color="blue")
                pipeline_stage_results.append(self._create_skipped_result(pipeline_stage.name))
                continue

            # skip if dry run
            if dry_run:
                stage_result = self._run_dry(pipeline_stage)
                pipeline_stage_results.append(stage_result)
                if pipeline_stage.register_output:
                    context.setdefault("outputs", {})[pipeline_stage.register_output] = stage_result
                continue

            # select the plugin to run
            plugin_class = self.plugins[pipeline_stage.run]
            plugin = plugin_class()

            # run the plugin with executor
            _start_time = time.perf_counter()
            try:
                result = plugin.run(resolved_args, verbose=self.verbose)
                _end_time = time.perf_counter()
                stage_result = self._run_plugin_success(pipeline_stage, result, _end_time - _start_time)
                pipeline_stage_results.append(stage_result)
            except PluginExecutionFailed as e:
                _end_time = time.perf_counter()
                stage_result, should_skip, stage_passed = self._run_plugin_failure(
                    pipeline_stage, e, _end_time - _start_time, resolved_args
                )
                pipeline_stage_results.append(stage_result)
                if should_skip:
                    skip_the_rest = True
                if not stage_passed:
                    pipeline_passed = False

            # register output if required
            if pipeline_stage.register_output:
                context.setdefault("outputs", {})[pipeline_stage.register_output] = pipeline_stage_results[-1]

        return PipelineResult(
            failed=not pipeline_passed,
            stage_results=pipeline_stage_results,
        )

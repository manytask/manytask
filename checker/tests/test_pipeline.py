from __future__ import annotations

from typing import Type

import pytest

from checker.configs import PipelineStageConfig
from checker.exceptions import BadConfig, PluginExecutionFailed
from checker.pipeline import PipelineRunner
from checker.plugins import PluginABC
from checker.plugins.base import PluginOutput


class _FailPlugin(PluginABC):
    name = "fail"

    def _run(self, args: PluginABC.Args, *, verbose: bool = False) -> PluginOutput:
        raise PluginExecutionFailed("Failed")


class _ScorePlugin(PluginABC):
    name = "score"

    class Args(PluginABC.Args):
        score: float = 0.5

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        if verbose:
            return PluginOutput(
                output=f"Score: {args.score:.2f}\nSome secret verbose line",
                percentage=args.score,
            )
        else:
            return PluginOutput(output=f"Score: {args.score:.2f}", percentage=args.score)


class _EchoPlugin(PluginABC):
    name = "echo"

    class Args(PluginABC.Args):
        message: str

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:
        return PluginOutput(output=args.message)


@pytest.fixture
def sample_plugins() -> dict[str, Type[PluginABC]]:
    return {
        "fail": _FailPlugin,
        "score": _ScorePlugin,
        "echo": _EchoPlugin,
    }


@pytest.fixture
def sample_correct_pipeline() -> list[PipelineStageConfig]:
    return [
        PipelineStageConfig(
            name="stage1 - echo",
            run="echo",
            args={"message": "${{ message }}"},
        ),
        PipelineStageConfig(
            name="stage2 - score",
            run="score",
            args={"score": 0.5},
            register_output="score_stage",
        ),
        PipelineStageConfig(
            name="stage3 - ignore fail",
            run="fail",
            fail="never",
        ),
        PipelineStageConfig(
            name="stage4 - skip fail if run_if=False",
            run="fail",
            run_if=False,
        ),
        PipelineStageConfig(
            name="stage5 - skip echo if run_if=False",
            run="echo",
            args={"message": "skipped message"},
            run_if=False,
        ),
        PipelineStageConfig(
            name="stage6 - skip fail if registered output",
            run="fail",
            run_if="${{ outputs.score_stage.percentage > 0.7 }}",
        ),
        PipelineStageConfig(
            name="stage7 - second echo",
            run="echo",
            args={"message": "second message"},
        ),
    ]


class TestSampleFixtures:
    def test_plugins(self, sample_plugins: dict[str, Type[PluginABC]]) -> None:
        plugin = sample_plugins["echo"]()
        plugin.validate({"message": "Hello"})
        result = plugin.run({"message": "Hello"}, verbose=True)
        assert result.percentage == 1.0
        assert result.output == "Hello"

        plugin = sample_plugins["score"]()
        plugin.validate({"score": 0.2})
        result = plugin.run({"score": 0.2})
        assert result.percentage == 0.2
        assert result.output == "Score: 0.20"

        plugin = sample_plugins["fail"]()
        plugin.validate({})
        with pytest.raises(PluginExecutionFailed):
            plugin.run({})


class TestPipelineRunnerValidation:
    def test_correct_pipeline_validation(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        pipeline_runner.validate({}, validate_placeholders=False)
        pipeline_runner.validate({"message": "Hello"}, validate_placeholders=True)
        with pytest.raises(BadConfig):
            pipeline_runner.validate({}, validate_placeholders=True)

    def test_unknown_plugin(self, sample_plugins: dict[str, Type[PluginABC]]) -> None:
        with pytest.raises(BadConfig) as exc_info:
            _ = PipelineRunner(
                pipeline=[
                    PipelineStageConfig(
                        name="stage1 - echo",
                        run="unknown",
                        args={"message": "Hello"},
                    ),
                ],
                plugins=sample_plugins,
                verbose=False,
            )
        assert "Unknown plugin" in str(exc_info.value)

    def test_validate_placeholders(self, sample_correct_pipeline: list[PipelineStageConfig]) -> None:
        with pytest.raises(BadConfig) as exc_info:
            _ = PipelineRunner(
                pipeline=sample_correct_pipeline,
                plugins={},
                verbose=False,
            )
        assert "Unknown plugin" in str(exc_info.value)

    def test_unknown_placeholder(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        with pytest.raises(BadConfig):
            pipeline_runner.validate({}, validate_placeholders=True)
        # TODO: fix it, now throwing Validation Error
        # assert "Unknown placeholder" in str(exc_info.value)

    def test_invalid_run_if(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        with pytest.raises(BadConfig):
            pipeline_runner.validate({"score": 0.5}, validate_placeholders=True)

    def test_invalid_register_output(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
    ) -> None:
        sample_correct_pipeline[1].register_output = "unknown"
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        with pytest.raises(BadConfig) as exc_info:
            pipeline_runner.validate({"message": "some valid message"}, validate_placeholders=True)
        assert "Invalid template" in str(exc_info.value)

    def test_run_correct_pipeline_verbose(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=True,
        )
        result = pipeline_runner.run({"message": "Hello"})
        assert not result.failed
        captured = capsys.readouterr().err
        assert "Hello" in captured
        assert "Score: 0.50" in captured
        assert "second message" in captured
        # in args print, so in the verbose output
        # assert "skipped message" not in captured.out and "skipped message" not in captured.err
        # verbose output
        assert "Some secret verbose line" in captured
        # stages names are printed
        for stage_name in ["stage1", "stage2", "stage3", "stage4", "stage5", "stage6"]:
            assert stage_name in captured

    def test_not_print_stage_if_not_verbose(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        result = pipeline_runner.run({"message": "Hello"})
        assert not result.failed
        captured = capsys.readouterr().err
        assert "stage4" not in captured
        assert "stage5" not in captured

    def test_run_correct_pipeline_not_verbose(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        result = pipeline_runner.run({"message": "Hello"})
        assert not result.failed
        captured = capsys.readouterr().err
        assert "Hello" in captured
        assert "Score: 0.50" in captured
        assert "second message" in captured
        # in args print, so not in the non-verbose output
        assert "skipped message" not in captured
        # verbose output
        assert "Some secret verbose line" not in captured
        # stages names are printed
        for stage_name in ["stage1", "stage2", "stage3"]:
            assert stage_name in captured

    def test_dry_run(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        result = pipeline_runner.run({"message": "Hello"}, dry_run=True)
        assert not result.failed
        captured = capsys.readouterr().err
        # no "error!" msg as all is skipped
        assert "error!" not in captured
        assert "[output here]" in captured
        assert "dry run!" in captured
        # stages names are printed
        for stage_name in ["stage1", "stage2", "stage3", "stage4", "stage5", "stage6"]:
            assert stage_name in captured

    def test_fail_fast(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sample_correct_pipeline[2].fail = PipelineStageConfig.FailType.FAST
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        result = pipeline_runner.run({"message": "Hello"})
        assert result.failed
        captured = capsys.readouterr().err
        # no "error!" msg as all is skipped
        assert "error!" in captured
        # fist echo works, second not
        assert "Hello" in captured
        assert "second message" not in captured
        # stages names are printed
        for stage_name in ["stage1", "stage2", "stage3"]:
            assert stage_name in captured

    def test_fail_after_all(
        self,
        sample_correct_pipeline: list[PipelineStageConfig],
        sample_plugins: dict[str, Type[PluginABC]],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sample_correct_pipeline[2].fail = PipelineStageConfig.FailType.AFTER_ALL
        pipeline_runner = PipelineRunner(
            pipeline=sample_correct_pipeline,
            plugins=sample_plugins,
            verbose=False,
        )
        result = pipeline_runner.run({"message": "Hello"})
        assert result.failed
        captured = capsys.readouterr().err
        # no "error!" msg as all is skipped
        assert "error!" in captured
        # fist echo works, second not
        assert "Hello" in captured
        assert "second message" in captured
        # stages names are printed
        for stage_name in ["stage1", "stage2", "stage3"]:
            assert stage_name in captured

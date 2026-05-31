"""Unit tests for ChecklistRunner."""

from __future__ import annotations

from app.checklist import ChecklistRunner
from app.checklist.result import CheckResult
from app.checklist.step import CheckContext
from app.hosting import MergeRequest
from app.models import (
    FolderStructureStep as FolderStructureConfig,
)
from app.models import (
    PipelinePassedStep as PipelinePassedConfig,
)
from app.models import (
    TaskConfig,
)
from app.observability import Metrics
from tests._fakes import FakeHostingAdapter


class _RecordingStep:
    """In-test CheckStep that returns a preset result and records the call."""

    def __init__(self, name: str, result: CheckResult) -> None:
        self.name = name
        self._result = result
        self.calls: list[tuple[MergeRequest, CheckContext]] = []

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        self.calls.append((mr, ctx))
        return self._result


class _RaisingStep:
    name = "boom"

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        raise RuntimeError("backend exploded")


class TestChecklistRunner:
    async def test_runs_all_steps_in_order(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        s1 = _RecordingStep("a", CheckResult("a", True, "ok"))
        s2 = _RecordingStep("b", CheckResult("b", True, "ok"))

        runner = ChecklistRunner(
            hosting=fake_hosting_adapter,
            sandbox=None,
            steps_builder=lambda task: [s1, s2],
        )

        task = TaskConfig(
            name="task-1",
            checklist=[PipelinePassedConfig(), FolderStructureConfig(required_path="tasks/x")],
        )
        results = await runner.run(task, sample_mr, sample_ctx)

        assert [r.name for r in results] == ["a", "b"]
        assert len(s1.calls) == 1
        assert len(s2.calls) == 1

    async def test_step_exception_becomes_failed_result(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        s_ok = _RecordingStep("ok", CheckResult("ok", True, ""))
        s_bad = _RaisingStep()

        runner = ChecklistRunner(
            hosting=fake_hosting_adapter,
            sandbox=None,
            steps_builder=lambda task: [s_ok, s_bad],
        )

        task = TaskConfig(name="task-1", checklist=[PipelinePassedConfig()])
        results = await runner.run(task, sample_mr, sample_ctx)

        assert len(results) == 2
        assert results[0].passed is True
        assert results[1].name == "boom"
        assert results[1].passed is False
        assert "backend exploded" in results[1].message

    async def test_uses_factory_when_no_explicit_steps(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        runner = ChecklistRunner(hosting=fake_hosting_adapter, sandbox=None)

        task = TaskConfig(
            name="task-1",
            checklist=[
                PipelinePassedConfig(),
                FolderStructureConfig(required_path="tasks/foo"),
            ],
        )
        results = await runner.run(task, sample_mr, sample_ctx)

        assert [r.name for r in results] == ["pipeline passed", "folder structure"]


class _FakeRunStep:
    name = "run"

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        return CheckResult(name="run", passed=True, message="ok")


async def test_run_step_duration_is_observed() -> None:
    metrics = Metrics()
    runner = ChecklistRunner(
        hosting=FakeHostingAdapter(),
        sandbox=None,
        steps_builder=lambda task: [_FakeRunStep()],
        metrics=metrics,
    )
    task = TaskConfig.model_validate({"name": "task-1", "checklist": [{"type": "pipeline_passed"}]})
    mr = MergeRequest(
        project_id=1,
        mr_iid=1,
        sha="x",
        web_url="u",
        source_branch="b",
        target_branch="main",
        author_username="s",
        labels=(),
        title="t",
        project_path_with_namespace="g/p",
    )
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await runner.run(task, mr, ctx)

    assert (
        metrics.registry.get_sample_value("run_step_duration_seconds_count", {"course": "python-101", "task": "task-1"})
        == 1.0
    )

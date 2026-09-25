"""Unit tests for the run: built-in step (over a mocked RunSandbox)."""

from __future__ import annotations

from dataclasses import dataclass

from app.checklist.builtins.run import RunStep
from app.checklist.sandbox import SandboxResult
from app.checklist.step import CheckContext
from app.hosting import MergeRequest


@dataclass
class _StubSandbox:
    result: SandboxResult
    calls: list[tuple[MergeRequest, str, CheckContext]]

    @classmethod
    def with_result(cls, result: SandboxResult) -> "_StubSandbox":
        return cls(result=result, calls=[])

    async def run(
        self,
        *,
        mr: MergeRequest,
        command: str,
        ctx: CheckContext,
    ) -> SandboxResult:
        self.calls.append((mr, command, ctx))
        return self.result


class TestRunStep:
    async def test_passes_on_exit_zero(
        self,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        sandbox = _StubSandbox.with_result(SandboxResult(timed_out=False, exit_code=0, stdout=b"hello\n", stderr=b""))
        step = RunStep(sandbox=sandbox, command="echo hello")  # type: ignore[arg-type]

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is True
        assert "hello" in result.message
        assert sandbox.calls[0][1] == "echo hello"

    async def test_fails_on_non_zero(
        self,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        sandbox = _StubSandbox.with_result(SandboxResult(timed_out=False, exit_code=2, stdout=b"out", stderr=b"err"))
        step = RunStep(sandbox=sandbox, command="false")  # type: ignore[arg-type]

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert "exit code 2" in result.message

    async def test_timeout_reported_as_failure(
        self,
        sample_mr: MergeRequest,
        sample_ctx: CheckContext,
    ) -> None:
        sandbox = _StubSandbox.with_result(SandboxResult(timed_out=True, exit_code=-1, stdout=b"", stderr=b"timeout"))
        step = RunStep(sandbox=sandbox, command="sleep 999")  # type: ignore[arg-type]

        result = await step.run(sample_mr, sample_ctx)

        assert result.passed is False
        assert "timeout" in result.message.lower() or "timed out" in result.message.lower()

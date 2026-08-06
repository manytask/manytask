"""Built-in step: run a sandboxed shell command, pass on exit 0."""

from __future__ import annotations

from app.checklist.result import CheckResult
from app.checklist.sandbox import RunSandbox
from app.checklist.step import CheckContext
from app.hosting import MergeRequest


class RunStep:
    name = "run"

    def __init__(self, *, sandbox: RunSandbox, command: str) -> None:
        self._sandbox = sandbox
        self._command = command

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        result = await self._sandbox.run(mr=mr, command=self._command, ctx=ctx)
        if result.timed_out:
            return CheckResult(
                name=self.name,
                passed=False,
                message=f"command timed out: `{self._command}`",
            )
        if result.exit_code == 0:
            stdout = result.stdout.decode(errors="replace").rstrip()
            body = f"```\n{stdout}\n```" if stdout else "(no output)"
            return CheckResult(name=self.name, passed=True, message=body)

        stdout = result.stdout.decode(errors="replace").rstrip()
        snippet = f"\n```\n{stdout}\n```" if stdout else ""
        return CheckResult(
            name=self.name,
            passed=False,
            message=f"command failed with exit code {result.exit_code}{snippet}",
        )

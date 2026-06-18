"""Built-in step: verify the MR's head pipeline finished successfully."""

from __future__ import annotations

from app.checklist.result import CheckResult
from app.checklist.step import CheckContext
from app.hosting import HostingAdapter, MergeRequest


class PipelinePassedStep:
    name = "pipeline passed"

    def __init__(self, *, hosting: HostingAdapter) -> None:
        self._hosting = hosting

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        status = await self._hosting.get_pipeline_status(mr)
        if status.state == "success":
            return CheckResult(name=self.name, passed=True, message="pipeline succeeded")

        suffix = f" (see {status.web_url})" if status.web_url else ""
        return CheckResult(
            name=self.name,
            passed=False,
            message=f"pipeline state is `{status.state}`, expected `success`{suffix}",
        )

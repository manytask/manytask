"""Executes an ordered list of checklist steps for a single MR."""

from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from app.checklist.factory import build_check_step
from app.checklist.result import CheckResult
from app.checklist.sandbox import RunSandbox
from app.checklist.step import CheckContext, CheckStep
from app.hosting import HostingAdapter, MergeRequest
from app.models import TaskConfig

StepsBuilder = Callable[[TaskConfig], list[CheckStep]]


class ChecklistRunner:
    """Builds and runs checklist steps for one (task, MR) pair.

    Each step's exception is converted to a failed CheckResult so one broken
    step doesn't poison the rest of the checklist for the student.
    """

    def __init__(
        self,
        *,
        hosting: HostingAdapter,
        sandbox: RunSandbox | None,
        steps_builder: StepsBuilder | None = None,
    ) -> None:
        self._hosting = hosting
        self._sandbox = sandbox
        self._steps_builder = steps_builder or self._default_builder

    def _default_builder(self, task: TaskConfig) -> list[CheckStep]:
        return [build_check_step(s, hosting=self._hosting, sandbox=self._sandbox) for s in task.checklist]

    async def run(
        self,
        task: TaskConfig,
        mr: MergeRequest,
        ctx: CheckContext,
    ) -> list[CheckResult]:
        steps = self._steps_builder(task)
        results: list[CheckResult] = []
        for step in steps:
            try:
                results.append(await step.run(mr, ctx))
            except Exception as err:
                logger.exception(
                    "checklist step {} crashed on mr {}!{}",
                    step.name,
                    mr.project_path_with_namespace,
                    mr.mr_iid,
                )
                results.append(
                    CheckResult(
                        name=step.name,
                        passed=False,
                        message=f"step crashed: {err}",
                    )
                )
        return results

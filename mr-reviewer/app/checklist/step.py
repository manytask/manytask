"""Protocol every checklist step implements + per-MR context object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.checklist.result import CheckResult
from app.hosting import MergeRequest


@dataclass(frozen=True, slots=True)
class CheckContext:
    """Per-MR context passed to every CheckStep.

    Fields used by the ``run:`` step (env-whitelist payload) and ignored by
    the built-in checks. Kept opaque so adding new context fields doesn't
    force every step to re-thread arguments.
    """

    course_name: str
    course_token: str


class CheckStep(Protocol):
    """A single named check. Steps are stateless after construction."""

    name: str

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult: ...

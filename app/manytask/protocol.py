"""Narrow protocol of the manytask calls the worker depends on."""

from __future__ import annotations

from typing import Protocol


class ManytaskReporter(Protocol):
    async def is_admin(self, course_name: str, *, token: str, rms_username: str) -> bool: ...

    async def report_score(
        self,
        course_name: str,
        *,
        token: str,
        username: str,
        task: str,
        score: int,
        allow_reduction: bool = ...,
        check_deadline: bool = ...,
    ) -> bool | int: ...

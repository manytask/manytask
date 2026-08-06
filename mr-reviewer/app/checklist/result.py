"""Result of a single checklist step plus an aggregate helper."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    message: str


def all_passed(results: Iterable[CheckResult]) -> bool:
    return all(r.passed for r in results)

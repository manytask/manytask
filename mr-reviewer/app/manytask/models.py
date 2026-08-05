"""Typed responses returned by the manytask client."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class DeadlineEntry:
    task_name: str
    group: str
    deadline: datetime
    score: int
    is_bonus: bool
    is_large: bool


def parse_manytask_datetime(value: str) -> datetime:
    """Parse an ISO 8601 timestamp from manytask, tolerating a trailing ``Z``."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)

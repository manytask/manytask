"""Domain models shared by every hosting adapter.

These are intentionally provider-agnostic: no python-gitlab types leak through.
All dataclasses are frozen so they can be passed across the executor boundary
without aliasing surprises.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

PipelineState = Literal[
    "success",
    "failed",
    "running",
    "canceled",
    "pending",
    "skipped",
    "manual",
    "none",
]


@dataclass(frozen=True, slots=True)
class MergeRequest:
    project_id: int
    mr_iid: int
    sha: str
    web_url: str
    source_branch: str
    target_branch: str
    author_username: str
    labels: tuple[str, ...]
    title: str


@dataclass(frozen=True, slots=True)
class Comment:
    id: int
    author_username: str
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FileChange:
    old_path: str
    new_path: str
    new_file: bool
    renamed_file: bool
    deleted_file: bool
    diff: str


@dataclass(frozen=True, slots=True)
class PipelineStatus:
    id: int | None
    state: PipelineState
    web_url: str | None
    sha: str | None

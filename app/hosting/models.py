"""Domain models shared by every hosting adapter."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MergeRequestRef:
    project_id: int
    mr_iid: int
    sha: str


@dataclass(frozen=True, slots=True)
class HostingComment:
    body: str

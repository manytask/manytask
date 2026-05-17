"""Provider-agnostic protocol every hosting adapter must implement.

Public surface only — concrete adapters live next to this file.
"""

from __future__ import annotations

from typing import Protocol

from app.hosting.models import Comment, FileChange, MergeRequest, PipelineStatus


class HostingAdapter(Protocol):
    """Async-only interface used by the worker and the checklist runner.

    Implementations are free to wrap blocking client libraries — the contract
    only promises async-friendliness from the caller's POV.
    """

    async def list_open_mrs(self, group_path: str, label: str) -> list[MergeRequest]: ...

    async def get_mr(self, project_id: int, mr_iid: int) -> MergeRequest: ...

    async def get_changes(self, mr: MergeRequest) -> list[FileChange]: ...

    async def get_pipeline_status(self, mr: MergeRequest) -> PipelineStatus: ...

    async def get_comments(self, mr: MergeRequest, since_id: int | None = None) -> list[Comment]: ...

    async def post_or_update_comment(self, mr: MergeRequest, anchor_tag: str, body: str) -> Comment: ...

    async def add_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest: ...

    async def remove_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest: ...

    def get_author_username(self, comment: Comment) -> str: ...

"""Manually wired test doubles for the hosting and sandbox layers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.hosting import Comment, FileChange, MergeRequest, PipelineStatus


class FakeHostingAdapter:
    """Conforms structurally to HostingAdapter Protocol for unit tests.

    Records inputs into the public ``posted``/``added_labels``/``removed_labels``
    lists for assertion. ``list_open_mrs``/``get_mr`` raise NotImplementedError —
    the checklist tests don't need those paths.
    """

    def __init__(self) -> None:
        self.pipeline_status: PipelineStatus = PipelineStatus(id=1, state="success", web_url=None, sha="deadbeef")
        self.changes: list[FileChange] = []
        self.notes: list[Comment] = []
        self.posted: list[tuple[str, str, str | None]] = []
        self.added_labels: list[list[str]] = []
        self.removed_labels: list[list[str]] = []

    async def list_open_mrs(self, group_path: str, label: str) -> list[MergeRequest]:
        raise NotImplementedError

    async def get_mr(self, project_id: int, mr_iid: int) -> MergeRequest:
        raise NotImplementedError

    async def get_changes(self, mr: MergeRequest) -> list[FileChange]:
        return list(self.changes)

    async def get_pipeline_status(self, mr: MergeRequest) -> PipelineStatus:
        return self.pipeline_status

    async def get_comments(self, mr: MergeRequest, since_id: int | None = None) -> list[Comment]:
        return list(self.notes)

    async def post_or_update_comment(
        self,
        mr: MergeRequest,
        anchor_tag: str,
        body: str,
        *,
        only_from_author: str | None = None,
    ) -> Comment:
        self.posted.append((anchor_tag, body, only_from_author))
        return Comment(
            id=1000 + len(self.posted),
            author_username=only_from_author or "anyone",
            body=body,
            created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )

    async def add_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest:
        self.added_labels.append(list(labels))
        return mr

    async def remove_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest:
        self.removed_labels.append(list(labels))
        return mr

    def get_author_username(self, comment: Comment) -> str:
        return comment.author_username

"""Manually wired test doubles for the hosting and sandbox layers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.hosting import Comment, FileChange, MergeRequest, PipelineStatus


class FakeHostingAdapter:
    """Conforms structurally to HostingAdapter Protocol for unit tests.

    Records inputs into the public ``posted``/``added_labels``/``removed_labels``
    lists for assertion. ``get_mr`` raises NotImplementedError — checklist tests
    don't need that path.
    """

    def __init__(self) -> None:
        self.pipeline_status: PipelineStatus = PipelineStatus(id=1, state="success", web_url=None, sha="deadbeef")
        self.changes: list[FileChange] = []
        self.notes: list[Comment] = []
        self.posted: list[tuple[str, str, str | None]] = []
        self.added_labels: list[list[str]] = []
        self.removed_labels: list[list[str]] = []
        # (group_path, label) -> list of MRs the worker should discover
        self.open_mrs: dict[tuple[str, str], list[MergeRequest]] = {}

    async def list_open_mrs(self, group_path: str, label: str) -> list[MergeRequest]:
        return list(self.open_mrs.get((group_path, label), []))

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


class FakeManytaskClient:
    """Records report calls and answers is_admin/report from configured maps."""

    def __init__(self) -> None:
        # rms_username -> is admin
        self.admins: set[str] = set()
        # explicit exception to raise from is_admin / report_score (transient simulation)
        self.is_admin_error: Exception | None = None
        self.report_error: Exception | None = None
        self.reported: list[dict[str, object]] = []

    async def is_admin(self, course_name: str, *, token: str, rms_username: str) -> bool:
        if self.is_admin_error is not None:
            raise self.is_admin_error
        return rms_username in self.admins

    async def report_score(
        self,
        course_name: str,
        *,
        token: str,
        username: str,
        task: str,
        score: int,
        allow_reduction: bool = True,
        check_deadline: bool = False,
    ) -> int:
        if self.report_error is not None:
            raise self.report_error
        self.reported.append(
            {
                "course_name": course_name,
                "token": token,
                "username": username,
                "task": task,
                "score": score,
                "allow_reduction": allow_reduction,
                "check_deadline": check_deadline,
            }
        )
        return score

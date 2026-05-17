"""GitLab implementation of HostingAdapter."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

import gitlab
from gitlab.v4.objects import Group, GroupMergeRequest

from app.hosting.models import Comment, FileChange, MergeRequest, PipelineStatus

_T = TypeVar("_T")


class GitLabAdapter:
    """python-gitlab-backed adapter. Sync calls run on a dedicated executor."""

    def __init__(
        self,
        token: str,
        base_url: str,
        executor: ThreadPoolExecutor,
        *,
        batch_size: int = 16,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._executor = executor
        self._batch_size = batch_size
        self._gl = gitlab.Gitlab(url=self._base_url, private_token=self._token)

    async def _run_in_executor(self, func: Callable[..., _T], *args: Any) -> _T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, func, *args)

    async def _gather_in_batches(
        self,
        coros: Iterable[Awaitable[_T]],
    ) -> list[_T]:
        coros_list = list(coros)
        results: list[_T] = []
        for start in range(0, len(coros_list), self._batch_size):
            batch = coros_list[start : start + self._batch_size]
            results.extend(await asyncio.gather(*batch))
        return results

    @staticmethod
    def _summary_to_mr(summary: GroupMergeRequest) -> MergeRequest:
        attrs = summary.attributes
        author = attrs.get("author") or {}
        return MergeRequest(
            project_id=int(attrs["project_id"]),
            mr_iid=int(attrs["iid"]),
            sha=str(attrs.get("sha") or ""),
            web_url=str(attrs.get("web_url", "")),
            source_branch=str(attrs.get("source_branch", "")),
            target_branch=str(attrs.get("target_branch", "")),
            author_username=str(author.get("username", "")),
            labels=tuple(attrs.get("labels") or ()),
            title=str(attrs.get("title", "")),
        )

    def _list_open_mrs_blocking(self, group_path: str, label: str) -> list[GroupMergeRequest]:
        group: Group = self._gl.groups.get(group_path, lazy=True)
        # Manually paginate with explicit page numbers for test compatibility
        mrs: list[GroupMergeRequest] = []
        page = 1
        while True:
            page_mrs = group.mergerequests.list(
                state="opened",
                labels=[label],
                per_page=100,
                page=page,
                get_all=False,
            )
            mrs.extend(page_mrs)
            # If we got fewer items than per_page, there's no next page
            if len(page_mrs) < 100:
                break
            page += 1
        return mrs

    async def list_open_mrs(self, group_path: str, label: str) -> list[MergeRequest]:
        summaries = await self._run_in_executor(self._list_open_mrs_blocking, group_path, label)
        return [self._summary_to_mr(s) for s in summaries]

    async def get_mr(self, project_id: int, mr_iid: int) -> MergeRequest:
        raise NotImplementedError

    async def get_changes(self, mr: MergeRequest) -> list[FileChange]:
        raise NotImplementedError

    async def get_pipeline_status(self, mr: MergeRequest) -> PipelineStatus:
        raise NotImplementedError

    async def get_comments(self, mr: MergeRequest, since_id: int | None = None) -> list[Comment]:
        raise NotImplementedError

    async def post_or_update_comment(self, mr: MergeRequest, anchor_tag: str, body: str) -> Comment:
        raise NotImplementedError

    async def add_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest:
        raise NotImplementedError

    async def remove_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest:
        raise NotImplementedError

    def get_author_username(self, comment: Comment) -> str:
        return comment.author_username

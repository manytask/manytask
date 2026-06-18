"""GitLab implementation of HostingAdapter."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import Any, TypeVar

import gitlab
import requests
from gitlab.v4.objects import Group, GroupMergeRequest
from loguru import logger
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from app.hosting.anchor import has_anchor, make_anchor_marker
from app.hosting.models import (
    Comment,
    FileChange,
    MergeRequest,
    PipelineStatus,
    derive_project_path_from_web_url,
)

_T = TypeVar("_T")


def _is_retryable_gitlab_error(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, gitlab.exceptions.GitlabError):
        code = getattr(exc, "response_code", None)
        return code is not None and code >= 500
    return False


class GitLabAdapter:
    """python-gitlab-backed adapter. Sync calls run on a dedicated executor."""

    _KNOWN_PIPELINE_STATES: frozenset[str] = frozenset(
        {"success", "failed", "running", "canceled", "pending", "skipped", "manual"}
    )

    def __init__(
        self,
        token: str,
        base_url: str,
        executor: ThreadPoolExecutor,
        *,
        batch_size: int = 16,
        retry_attempts: int = 1,
        retry_backoff_sec: float = 0.5,
        retry_max_backoff_sec: float = 10.0,
        rate_limit_threshold: float = 0.1,
        rate_limit_max_sleep_sec: float = 60.0,
        rate_limit_fallback_sleep_sec: float = 5.0,
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._executor = executor
        self._batch_size = batch_size
        self._rate_limit_threshold = rate_limit_threshold
        self._rate_limit_max_sleep_sec = rate_limit_max_sleep_sec
        self._rate_limit_fallback_sleep_sec = rate_limit_fallback_sleep_sec
        self._gl = gitlab.Gitlab(url=self._base_url, private_token=self._token)
        self._gl.session.hooks["response"].append(self._rate_limit_hook)
        self._retrying = Retrying(
            stop=stop_after_attempt(max(1, retry_attempts)),
            wait=wait_exponential(multiplier=retry_backoff_sec, max=retry_max_backoff_sec),
            retry=retry_if_exception(_is_retryable_gitlab_error),
            reraise=True,
        )

    def _rate_limit_hook(self, response: Any, *args: Any, **kwargs: Any) -> Any:
        """requests response hook: sleep (in the executor thread) when the
        GitLab rate-limit budget is nearly exhausted."""
        remaining = response.headers.get("RateLimit-Remaining")
        limit = response.headers.get("RateLimit-Limit")
        if remaining is None or limit is None:
            return response
        try:
            remaining_i = int(remaining)
            limit_i = int(limit)
        except TypeError, ValueError:
            return response
        if limit_i <= 0 or remaining_i / limit_i >= self._rate_limit_threshold:
            return response

        sleep_for = self._rate_limit_fallback_sleep_sec
        reset = response.headers.get("RateLimit-Reset")
        if reset is not None:
            try:
                sleep_for = max(0.0, int(reset) - time.time())
            except TypeError, ValueError:
                pass
        sleep_for = min(sleep_for, self._rate_limit_max_sleep_sec)
        logger.warning(
            "gitlab rate-limit low: {}/{} remaining; sleeping {:.1f}s",
            remaining_i,
            limit_i,
            sleep_for,
        )
        if sleep_for > 0:
            time.sleep(sleep_for)
        return response

    async def _run_in_executor(self, func: Callable[..., _T], *args: Any) -> _T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, partial(self._retrying, func, *args))

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
    def _parse_iso8601(value: str) -> datetime:
        """GitLab returns 2026-05-01T10:00:00.000Z; Python <3.11 didn't accept Z directly."""
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)

    @staticmethod
    def _summary_to_mr(summary: GroupMergeRequest) -> MergeRequest:
        attrs = summary.attributes
        author = attrs.get("author") or {}
        web_url = str(attrs.get("web_url", ""))
        references = attrs.get("references") or {}
        project_path = str(references.get("full", "")).split("!")[0] if references.get("full") else ""
        if not project_path:
            project_path = derive_project_path_from_web_url(web_url)
        return MergeRequest(
            project_id=int(attrs["project_id"]),
            mr_iid=int(attrs["iid"]),
            sha=str(attrs.get("sha") or ""),
            web_url=web_url,
            source_branch=str(attrs.get("source_branch", "")),
            target_branch=str(attrs.get("target_branch", "")),
            author_username=str(author.get("username", "")),
            labels=tuple(attrs.get("labels") or ()),
            title=str(attrs.get("title", "")),
            project_path_with_namespace=project_path,
        )

    @staticmethod
    def _project_mr_to_mr(obj: Any) -> MergeRequest:
        attrs = obj.attributes
        author = attrs.get("author") or {}
        web_url = str(attrs.get("web_url", ""))
        references = attrs.get("references") or {}
        project_path = str(references.get("full", "")).split("!")[0] if references.get("full") else ""
        if not project_path:
            project_path = derive_project_path_from_web_url(web_url)
        return MergeRequest(
            project_id=int(attrs["project_id"]),
            mr_iid=int(attrs["iid"]),
            sha=str(attrs.get("sha") or ""),
            web_url=web_url,
            source_branch=str(attrs.get("source_branch", "")),
            target_branch=str(attrs.get("target_branch", "")),
            author_username=str(author.get("username", "")),
            labels=tuple(attrs.get("labels") or ()),
            title=str(attrs.get("title", "")),
            project_path_with_namespace=project_path,
        )

    @staticmethod
    def _attrs_dict_to_mr(attrs: dict[str, Any]) -> MergeRequest:
        author = attrs.get("author") or {}
        web_url = str(attrs.get("web_url", ""))
        references = attrs.get("references") or {}
        project_path = str(references.get("full", "")).split("!")[0] if references.get("full") else ""
        if not project_path:
            project_path = derive_project_path_from_web_url(web_url)
        return MergeRequest(
            project_id=int(attrs["project_id"]),
            mr_iid=int(attrs["iid"]),
            sha=str(attrs.get("sha") or ""),
            web_url=web_url,
            source_branch=str(attrs.get("source_branch", "")),
            target_branch=str(attrs.get("target_branch", "")),
            author_username=str(author.get("username", "")),
            labels=tuple(attrs.get("labels") or ()),
            title=str(attrs.get("title", "")),
            project_path_with_namespace=project_path,
        )

    def _get_mr_blocking(self, project_id: int, mr_iid: int) -> Any:
        project = self._gl.projects.get(project_id, lazy=True)
        return project.mergerequests.get(mr_iid)

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
        obj = await self._run_in_executor(self._get_mr_blocking, project_id, mr_iid)
        return self._project_mr_to_mr(obj)

    def _get_changes_blocking(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        project = self._gl.projects.get(project_id, lazy=True)
        mr = project.mergerequests.get(mr_iid, lazy=True)
        payload = mr.changes()
        return list(payload.get("changes") or [])

    def _list_pipelines_blocking(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        project = self._gl.projects.get(project_id, lazy=True)
        mr = project.mergerequests.get(mr_iid, lazy=True)
        pipelines = mr.pipelines.list(per_page=1, page=1)
        return [p.attributes for p in pipelines]

    def _list_notes_blocking(self, project_id: int, mr_iid: int) -> list[dict[str, Any]]:
        project = self._gl.projects.get(project_id, lazy=True)
        mr = project.mergerequests.get(mr_iid, lazy=True)
        notes = mr.notes.list(
            sort="asc",
            order_by="created_at",
            per_page=100,
            iterator=True,
        )
        return [n.attributes for n in notes]

    def _update_labels_blocking(
        self,
        project_id: int,
        mr_iid: int,
        *,
        add: list[str] | None,
        remove: list[str] | None,
    ) -> dict[str, Any]:
        project = self._gl.projects.get(project_id, lazy=True)
        mr = project.mergerequests.get(mr_iid, lazy=True)
        payload: dict[str, Any] = {}
        if add:
            payload["add_labels"] = ",".join(add)
        if remove:
            payload["remove_labels"] = ",".join(remove)
        if not payload:
            return dict(mr.attributes)
        for key, value in payload.items():
            setattr(mr, key, value)
        mr.save()
        return dict(mr.attributes)

    async def get_changes(self, mr: MergeRequest) -> list[FileChange]:
        raw = await self._run_in_executor(self._get_changes_blocking, mr.project_id, mr.mr_iid)
        return [
            FileChange(
                old_path=str(item.get("old_path", "")),
                new_path=str(item.get("new_path", "")),
                new_file=bool(item.get("new_file", False)),
                renamed_file=bool(item.get("renamed_file", False)),
                deleted_file=bool(item.get("deleted_file", False)),
                diff=str(item.get("diff", "")),
            )
            for item in raw
        ]

    async def get_pipeline_status(self, mr: MergeRequest) -> PipelineStatus:
        items = await self._run_in_executor(self._list_pipelines_blocking, mr.project_id, mr.mr_iid)
        if not items:
            return PipelineStatus(id=None, state="none", web_url=None, sha=None)

        head = items[0]
        raw_state = str(head.get("status", ""))
        state: Any = raw_state if raw_state in self._KNOWN_PIPELINE_STATES else "none"
        return PipelineStatus(
            id=int(head["id"]) if head.get("id") is not None else None,
            state=state,
            web_url=head.get("web_url"),
            sha=head.get("sha"),
        )

    async def get_comments(self, mr: MergeRequest, since_id: int | None = None) -> list[Comment]:
        raw = await self._run_in_executor(self._list_notes_blocking, mr.project_id, mr.mr_iid)
        out: list[Comment] = []
        for item in raw:
            if item.get("system"):
                continue
            note_id = int(item["id"])
            if since_id is not None and note_id <= since_id:
                continue
            author = item.get("author") or {}
            out.append(
                Comment(
                    id=note_id,
                    author_username=str(author.get("username", "")),
                    body=str(item.get("body", "")),
                    created_at=self._parse_iso8601(str(item["created_at"])),
                )
            )
        return out

    def _create_note_blocking(self, project_id: int, mr_iid: int, body: str) -> dict[str, Any]:
        # Retrying this POST on ambiguous 5xx/timeout may duplicate the note if GitLab persisted it;
        # accepted tradeoff of blanket 5xx retry on blocking GitLab calls.
        project = self._gl.projects.get(project_id, lazy=True)
        mr = project.mergerequests.get(mr_iid, lazy=True)
        note = mr.notes.create({"body": body})
        return dict(note.attributes)

    def _update_note_blocking(self, project_id: int, mr_iid: int, note_id: int, body: str) -> dict[str, Any]:
        project = self._gl.projects.get(project_id, lazy=True)
        mr = project.mergerequests.get(mr_iid, lazy=True)
        result: dict[str, Any] = mr.notes.update(note_id, {"body": body})
        return result

    @staticmethod
    def _build_anchored_body(anchor_tag: str, body: str) -> str:
        marker = make_anchor_marker(anchor_tag)
        if body.lstrip().startswith(marker):
            return body
        return f"{marker}\n{body}"

    def _attrs_to_comment(self, attrs: dict[str, Any]) -> Comment:
        author = attrs.get("author") or {}
        return Comment(
            id=int(attrs["id"]),
            author_username=str(author.get("username", "")),
            body=str(attrs.get("body", "")),
            created_at=self._parse_iso8601(str(attrs["created_at"])),
        )

    async def post_or_update_comment(
        self,
        mr: MergeRequest,
        anchor_tag: str,
        body: str,
        *,
        only_from_author: str | None = None,
    ) -> Comment:
        anchored_body = self._build_anchored_body(anchor_tag, body)
        raw_notes = await self._run_in_executor(self._list_notes_blocking, mr.project_id, mr.mr_iid)
        existing_id: int | None = None
        for item in raw_notes:
            if item.get("system"):
                continue
            if not has_anchor(str(item.get("body", "")), anchor_tag):
                continue
            if only_from_author is not None:
                author = item.get("author") or {}
                if str(author.get("username", "")) != only_from_author:
                    continue
            existing_id = int(item["id"])
            break

        if existing_id is None:
            attrs = await self._run_in_executor(self._create_note_blocking, mr.project_id, mr.mr_iid, anchored_body)
        else:
            attrs = await self._run_in_executor(
                self._update_note_blocking,
                mr.project_id,
                mr.mr_iid,
                existing_id,
                anchored_body,
            )
        return self._attrs_to_comment(attrs)

    async def add_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest:
        attrs = await self._run_in_executor(
            partial(
                self._update_labels_blocking,
                mr.project_id,
                mr.mr_iid,
                add=labels,
                remove=None,
            )
        )
        return self._attrs_dict_to_mr(attrs)

    async def remove_labels(self, mr: MergeRequest, labels: list[str]) -> MergeRequest:
        attrs = await self._run_in_executor(
            partial(
                self._update_labels_blocking,
                mr.project_id,
                mr.mr_iid,
                add=None,
                remove=labels,
            )
        )
        return self._attrs_dict_to_mr(attrs)

    def get_author_username(self, comment: Comment) -> str:
        return comment.author_username

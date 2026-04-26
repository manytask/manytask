"""Abstract hosting protocol — implemented per provider (GitLab, GitHub, ...)."""

from typing import Protocol

from app.hosting.models import HostingComment, MergeRequestRef


class HostingClient(Protocol):
    async def list_open_merge_requests(self) -> list[MergeRequestRef]: ...

    async def post_comment(self, mr: MergeRequestRef, comment: HostingComment) -> None: ...

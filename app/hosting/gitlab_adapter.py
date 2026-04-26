"""GitLab implementation of HostingClient — wiring lands in a future ticket."""

from app.hosting.models import HostingComment, MergeRequestRef


class GitLabHostingClient:
    def __init__(self, token: str, base_url: str) -> None:
        self._token = token
        self._base_url = base_url

    async def list_open_merge_requests(self) -> list[MergeRequestRef]:
        raise NotImplementedError

    async def post_comment(self, mr: MergeRequestRef, comment: HostingComment) -> None:
        raise NotImplementedError

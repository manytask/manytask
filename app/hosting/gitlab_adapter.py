"""GitLab implementation of HostingAdapter (skeleton).

Method bodies are filled in by subsequent tasks. Each method delegates the
blocking python-gitlab call into a dedicated ThreadPoolExecutor.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.hosting.models import Comment, FileChange, MergeRequest, PipelineStatus


class GitLabAdapter:
    """python-gitlab-backed adapter. All sync calls run on a dedicated executor."""

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
        self._gl = self._build_client()

    def _build_client(self) -> object:  # python-gitlab Gitlab type filled in Task 6
        import gitlab

        return gitlab.Gitlab(url=self._base_url, private_token=self._token)

    async def list_open_mrs(self, group_path: str, label: str) -> list[MergeRequest]:
        raise NotImplementedError

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

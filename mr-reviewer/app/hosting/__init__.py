"""Public hosting surface."""

from app.hosting.factory import build_hosting_adapter
from app.hosting.gitlab_adapter import GitLabAdapter
from app.hosting.models import Comment, FileChange, MergeRequest, PipelineState, PipelineStatus
from app.hosting.protocol import HostingAdapter

__all__ = [
    "Comment",
    "FileChange",
    "GitLabAdapter",
    "HostingAdapter",
    "MergeRequest",
    "PipelineState",
    "PipelineStatus",
    "build_hosting_adapter",
]

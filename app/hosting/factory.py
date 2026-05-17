"""Build the right HostingAdapter for the configured provider."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.hosting.gitlab_adapter import GitLabAdapter
from app.hosting.protocol import HostingAdapter


def build_hosting_adapter(
    hosting_type: str,
    *,
    gitlab_token: str,
    gitlab_base_url: str,
    executor: ThreadPoolExecutor,
) -> HostingAdapter:
    if hosting_type == "gitlab":
        return GitLabAdapter(
            token=gitlab_token,
            base_url=gitlab_base_url,
            executor=executor,
        )
    raise ValueError(f"unsupported hosting_type: {hosting_type!r}")

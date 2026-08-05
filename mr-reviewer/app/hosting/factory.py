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
    retry_attempts: int = 1,
    retry_backoff_sec: float = 0.5,
    retry_max_backoff_sec: float = 10.0,
    rate_limit_threshold: float = 0.1,
    rate_limit_max_sleep_sec: float = 60.0,
    rate_limit_fallback_sleep_sec: float = 5.0,
) -> HostingAdapter:
    if hosting_type == "gitlab":
        return GitLabAdapter(
            token=gitlab_token,
            base_url=gitlab_base_url,
            executor=executor,
            retry_attempts=retry_attempts,
            retry_backoff_sec=retry_backoff_sec,
            retry_max_backoff_sec=retry_max_backoff_sec,
            rate_limit_threshold=rate_limit_threshold,
            rate_limit_max_sleep_sec=rate_limit_max_sleep_sec,
            rate_limit_fallback_sleep_sec=rate_limit_fallback_sleep_sec,
        )
    raise ValueError(f"unsupported hosting_type: {hosting_type!r}")

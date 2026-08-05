"""GitLab rate-limit response-hook throttling."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest

from app.hosting.gitlab_adapter import GitLabAdapter


class _FakeResponse:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


@pytest.fixture
def adapter() -> GitLabAdapter:
    executor = ThreadPoolExecutor(max_workers=1)
    return GitLabAdapter(
        token="t",
        base_url="https://gitlab.test",
        executor=executor,
        rate_limit_threshold=0.1,
        rate_limit_max_sleep_sec=60.0,
        rate_limit_fallback_sleep_sec=5.0,
    )


def test_hook_sleeps_until_reset_when_remaining_low(
    adapter: GitLabAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("app.hosting.gitlab_adapter.time.sleep", lambda s: slept.append(s))
    reset = int(time.time()) + 7
    resp: Any = _FakeResponse({"RateLimit-Remaining": "5", "RateLimit-Limit": "100", "RateLimit-Reset": str(reset)})

    adapter._rate_limit_hook(resp)

    assert len(slept) == 1
    assert 0.0 < slept[0] <= 8.0


def test_hook_sleeps_fallback_when_remaining_low_and_no_reset_header(
    adapter: GitLabAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("app.hosting.gitlab_adapter.time.sleep", lambda s: slept.append(s))
    resp: Any = _FakeResponse({"RateLimit-Remaining": "5", "RateLimit-Limit": "100"})

    adapter._rate_limit_hook(resp)

    assert slept == [5.0]


def test_hook_does_not_sleep_when_remaining_high(
    adapter: GitLabAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("app.hosting.gitlab_adapter.time.sleep", lambda s: slept.append(s))
    resp: Any = _FakeResponse({"RateLimit-Remaining": "80", "RateLimit-Limit": "100"})

    adapter._rate_limit_hook(resp)

    assert slept == []


def test_hook_no_headers_is_noop(adapter: GitLabAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("app.hosting.gitlab_adapter.time.sleep", lambda s: slept.append(s))
    resp: Any = _FakeResponse({})

    adapter._rate_limit_hook(resp)

    assert slept == []

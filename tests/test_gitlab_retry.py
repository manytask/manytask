"""GitLab transient-error retries via tenacity."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
import responses

from app.hosting.gitlab_adapter import GitLabAdapter

GITLAB = "https://gitlab.test"


@pytest.fixture
def retrying_adapter() -> GitLabAdapter:
    executor = ThreadPoolExecutor(max_workers=1)
    return GitLabAdapter(
        token="t",
        base_url=GITLAB,
        executor=executor,
        batch_size=4,
        retry_attempts=3,
        retry_backoff_sec=0.0,
        retry_max_backoff_sec=0.0,
    )


async def test_list_open_mrs_retries_on_500_then_succeeds(
    retrying_adapter: GitLabAdapter,
) -> None:
    url = f"{GITLAB}/api/v4/groups/course%2Fstudents/merge_requests"
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        mock.add(responses.GET, url, status=500)
        mock.add(responses.GET, url, json=[], status=200)

        result = await retrying_adapter.list_open_mrs("course/students", "task-1")

        assert result == []
        get_calls = [c for c in mock.calls if c.request.method == "GET"]
        assert len(get_calls) == 2

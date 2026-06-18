"""End-to-end benchmark: 500 MRs through every adapter method.

Marked `benchmark` so it's deselectable: `pytest -m "not benchmark"` skips it
in normal CI runs. The hard limit (300 s) is from the ticket DoD; in practice
it should finish in under 10 s with mocked HTTP.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import responses

from app.hosting.gitlab_adapter import GitLabAdapter

GROUP = "perf-group"
LABEL = "review-needed"
N_MRS = 500


def _mr_summary(idx: int) -> dict[str, object]:
    return {
        "id": 10_000 + idx,
        "iid": idx,
        "project_id": 1000 + (idx % 50),
        "title": f"task-{idx}",
        "sha": f"deadbeef{idx:06x}",
        "web_url": f"https://gitlab.test/group/proj/-/merge_requests/{idx}",
        "source_branch": f"task-{idx}",
        "target_branch": "main",
        "labels": [LABEL],
        "author": {"username": f"user-{idx}"},
        "state": "opened",
    }


@pytest.mark.benchmark
def test_500_mrs_under_300_sec() -> None:
    executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix="bench")
    try:
        adapter = GitLabAdapter(
            token="t",  # noqa: S106
            base_url="https://gitlab.test",
            executor=executor,
            batch_size=16,
        )

        with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
            mock.add(
                responses.GET,
                "https://gitlab.test/api/v4/groups/perf-group/merge_requests",
                json=[_mr_summary(i) for i in range(N_MRS)],
                status=200,
            )
            # Register second response for page=2 to drain pagination loop
            mock.add(
                responses.GET,
                "https://gitlab.test/api/v4/groups/perf-group/merge_requests",
                json=[],
                status=200,
            )
            for i in range(N_MRS):
                pid = 1000 + (i % 50)
                mock.add(
                    responses.GET,
                    f"https://gitlab.test/api/v4/projects/{pid}/merge_requests/{i}/changes",
                    json={**_mr_summary(i), "changes": []},
                    status=200,
                )
                mock.add(
                    responses.GET,
                    f"https://gitlab.test/api/v4/projects/{pid}/merge_requests/{i}/pipelines",
                    json=[
                        {
                            "id": 90_000 + i,
                            "status": "success",
                            "sha": f"deadbeef{i:06x}",
                            "web_url": f"https://gitlab.test/p/{pid}/-/pipelines/{90_000 + i}",
                        }
                    ],
                    status=200,
                )

            async def run() -> None:
                mrs = await adapter.list_open_mrs(GROUP, LABEL)
                assert len(mrs) == N_MRS

                changes = await adapter._gather_in_batches([adapter.get_changes(m) for m in mrs])
                assert len(changes) == N_MRS

                statuses = await adapter._gather_in_batches([adapter.get_pipeline_status(m) for m in mrs])
                assert all(s.state == "success" for s in statuses)

            t0 = time.monotonic()
            asyncio.run(run())
            elapsed = time.monotonic() - t0

        assert elapsed < 300, f"benchmark took {elapsed:.1f}s, exceeds 300s SLA"
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

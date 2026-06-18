"""Retry + error-metric behavior of ManytaskClient."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.manytask.client import ManytaskClient
from app.manytask.errors import ManytaskTokenForbidden, ManytaskUnavailable
from app.observability import Metrics


@respx.mock
async def test_is_admin_retries_on_5xx_then_succeeds() -> None:
    metrics = Metrics()
    client = ManytaskClient(
        base_url="http://manytask.test",
        timeout_sec=1.0,
        metrics=metrics,
        retry_attempts=3,
        retry_backoff_sec=0.0,
        retry_max_backoff_sec=0.0,
    )
    route = respx.get("http://manytask.test/api/c/is_admin").mock(
        side_effect=[
            httpx.Response(500, text="boom"),
            httpx.Response(200, json={"rms_username": "u", "is_admin": True}),
        ]
    )
    try:
        result = await client.is_admin("c", token="t", rms_username="u")
    finally:
        await client.aclose()

    assert result is True
    assert route.call_count == 2
    assert metrics.registry.get_sample_value("manytask_errors_total", {"endpoint": "is_admin"}) == 1.0


@respx.mock
async def test_report_gives_up_after_attempts_and_counts_each_error() -> None:
    metrics = Metrics()
    client = ManytaskClient(
        base_url="http://manytask.test",
        timeout_sec=1.0,
        metrics=metrics,
        retry_attempts=3,
        retry_backoff_sec=0.0,
        retry_max_backoff_sec=0.0,
    )
    respx.post("http://manytask.test/api/c/report").mock(return_value=httpx.Response(503, text="down"))
    try:
        with pytest.raises(ManytaskUnavailable):
            await client.report_score("c", token="t", username="u", task="task-1", score=10)
    finally:
        await client.aclose()

    assert metrics.registry.get_sample_value("manytask_errors_total", {"endpoint": "report"}) == 3.0


@respx.mock
async def test_terminal_403_is_not_retried_and_not_counted() -> None:
    metrics = Metrics()
    client = ManytaskClient(
        base_url="http://manytask.test",
        timeout_sec=1.0,
        metrics=metrics,
        retry_attempts=3,
        retry_backoff_sec=0.0,
        retry_max_backoff_sec=0.0,
    )
    route = respx.get("http://manytask.test/api/c/is_admin").mock(return_value=httpx.Response(403))
    try:
        with pytest.raises(ManytaskTokenForbidden):
            await client.is_admin("c", token="t", rms_username="u")
    finally:
        await client.aclose()

    assert route.call_count == 1
    assert metrics.registry.get_sample_value("manytask_errors_total", {"endpoint": "is_admin"}) is None

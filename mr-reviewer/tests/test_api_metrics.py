"""Tests for the GET /metrics Prometheus endpoint."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_metrics
from app.main import create_app
from app.observability import Metrics


@pytest_asyncio.fixture
async def metrics_client() -> AsyncIterator[tuple[AsyncClient, Metrics]]:
    app: FastAPI = create_app()
    metrics = Metrics()
    app.dependency_overrides[get_metrics] = lambda: metrics
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, metrics
    app.dependency_overrides.clear()


async def test_metrics_endpoint_returns_prometheus_text(
    metrics_client: tuple[AsyncClient, Metrics],
) -> None:
    client, metrics = metrics_client
    metrics.record_cycle(1.0)
    metrics.record_mr_processed("python-101")

    response = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "poll_cycles_total" in body
    assert 'mrs_processed_total{course="python-101"}' in body

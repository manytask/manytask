"""Tests for the /healthz liveness endpoint."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

import pytest_asyncio
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_metrics, get_redis, get_settings_dep
from app.config import Settings
from app.main import create_app
from app.observability import Metrics


class _BrokenRedis:
    async def ping(self) -> bool:
        raise ConnectionError("redis down")


@pytest_asyncio.fixture
async def health_app() -> AsyncIterator[tuple[FastAPI, FakeRedis, Metrics]]:
    app = create_app()
    redis = FakeRedis(decode_responses=True)
    metrics = Metrics()
    settings = Settings(healthz_poll_stale_sec=1800.0)
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_metrics] = lambda: metrics
    app.dependency_overrides[get_settings_dep] = lambda: settings
    try:
        yield app, redis, metrics
    finally:
        app.dependency_overrides.clear()
        await redis.aclose()


async def _get(app: FastAPI) -> tuple[int, dict[str, object]]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/healthz")
    return resp.status_code, resp.json()


async def test_healthz_ok_when_redis_up_and_poll_fresh(
    health_app: tuple[FastAPI, FakeRedis, Metrics],
) -> None:
    app, _, _ = health_app
    status, body = await _get(app)
    assert status == 200
    assert body == {"status": "ok"}


async def test_healthz_503_when_redis_unreachable(
    health_app: tuple[FastAPI, FakeRedis, Metrics],
) -> None:
    app, _, _ = health_app
    app.dependency_overrides[get_redis] = lambda: _BrokenRedis()
    status, _ = await _get(app)
    assert status == 503


async def test_healthz_503_when_poll_stale(
    health_app: tuple[FastAPI, FakeRedis, Metrics],
) -> None:
    app, _, metrics = health_app
    metrics.last_poll_timestamp = time.time() - 3600.0  # 1h > 30m threshold
    status, _ = await _get(app)
    assert status == 503

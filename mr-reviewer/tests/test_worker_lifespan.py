"""The lifespan must start and gracefully stop the worker task."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis

import app.main as main_module
from app.config import Settings
from app.main import create_app


@pytest_asyncio.fixture
async def patched_app(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    # Avoid real Redis / GitLab during lifespan.
    monkeypatch.setattr(
        "app.main.Redis.from_url",
        lambda *a, **k: FakeRedis(decode_responses=True),
    )
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(poll_interval_sec=0.01, per_mr_timeout_sec=120.0),
    )
    yield


async def test_worker_task_created_and_cancelled(patched_app: None) -> None:
    app = create_app()
    async with app.router.lifespan_context(app):
        assert app.state.worker_task is not None
        assert not app.state.worker_task.done()
    # After exiting the context the task must be finished (cancelled).
    assert app.state.worker_task.done()

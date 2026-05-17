"""Shared pytest fixtures."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
import pytest_asyncio
import responses as responses_lib
from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from loguru import logger as _loguru_logger

from app.api.dependencies import (
    get_auth_cache,
    get_course_store,
    get_manytask_client,
    get_settings_dep,
)
from app.config import Settings
from app.hosting.gitlab_adapter import GitLabAdapter
from app.main import create_app
from app.manytask import ManytaskClient, TokenAuthCache
from app.storage import CourseStore


def pytest_sessionstart(session: pytest.Session) -> None:
    """Disable coverage fail-under when running only benchmark tests.

    The 90% gate is meaningful for the full suite.  A ``pytest -m benchmark``
    run intentionally exercises only one heavy test, so its per-file coverage
    numbers are far below 90%.  We disable the gate here instead of forcing
    callers to append ``--no-cov`` every time.
    """
    config = session.config
    markexpr = getattr(config.option, "markexpr", "") or ""
    if markexpr.strip() == "benchmark":
        # Disable the coverage failure threshold for benchmark-only runs.
        # Modify both config.option (used by pytest-cov's hookwrapper) and
        # directly patch the CovPlugin instance (which holds its own reference).
        if hasattr(config.option, "cov_fail_under"):
            config.option.cov_fail_under = 0.0
        cov_plugin = config.pluginmanager.get_plugin("_cov")
        if cov_plugin is not None and hasattr(cov_plugin, "options"):
            cov_plugin.options.cov_fail_under = 0.0


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[FakeRedis]:
    redis = FakeRedis(decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.fixture
def fake_redis_server() -> FakeServer:
    return FakeServer()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        admin_token="admin-token",  # noqa: S106
        redis_url="redis://test/0",
        manytask_base_url="http://manytask.test",
        manytask_request_timeout_sec=1.0,
        ping_cache_ttl_sec=30,
    )


@pytest_asyncio.fixture
async def manytask_client() -> AsyncIterator[ManytaskClient]:
    client = ManytaskClient(base_url="http://manytask.test", timeout_sec=1.0)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def client_with_overrides(
    app: FastAPI,
    fake_redis: FakeRedis,
    manytask_client: ManytaskClient,
    test_settings: Settings,
) -> AsyncIterator[AsyncClient]:
    course_store = CourseStore(fake_redis)
    auth_cache = TokenAuthCache(fake_redis, ttl_sec=test_settings.ping_cache_ttl_sec)

    app.dependency_overrides[get_settings_dep] = lambda: test_settings
    app.dependency_overrides[get_course_store] = lambda: course_store
    app.dependency_overrides[get_manytask_client] = lambda: manytask_client
    app.dependency_overrides[get_auth_cache] = lambda: auth_cache

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class _PropagateHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


@pytest.fixture(autouse=True)
def _loguru_to_caplog(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    handler_id = _loguru_logger.add(_PropagateHandler(), format="{message}", level=0)
    try:
        yield
    finally:
        _loguru_logger.remove(handler_id)


_GITLAB_BASE = "https://gitlab.test"


@pytest.fixture
def gitlab_executor() -> Iterator[ThreadPoolExecutor]:
    """Small thread pool for tests — mocked HTTP doesn't benefit from 32 threads."""
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="gitlab-test")
    try:
        yield executor
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


@pytest.fixture
def gitlab_adapter(gitlab_executor: ThreadPoolExecutor) -> GitLabAdapter:
    return GitLabAdapter(
        token="test-token",  # noqa: S106
        base_url=_GITLAB_BASE,
        executor=gitlab_executor,
        batch_size=4,
    )


@pytest.fixture
def gitlab_base_url() -> str:
    return _GITLAB_BASE


@pytest.fixture
def mock_gitlab() -> Iterator[responses_lib.RequestsMock]:
    """Activated `responses.RequestsMock` for the duration of a test.

    Use ``mock_gitlab.add(...)`` to register stubs. ``assert_all_requests_are_fired=False``
    allows over-mocking (e.g. 500 MR benchmark stubs only some endpoints).
    """
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock

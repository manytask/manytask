"""Shared pytest fixtures."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
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
from app.main import create_app
from app.manytask import ManytaskClient, TokenAuthCache
from app.storage import CourseStore


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

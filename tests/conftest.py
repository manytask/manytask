"""Shared pytest fixtures."""

import logging
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from fakeredis import FakeServer
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient
from loguru import logger as _loguru_logger

from app.main import create_app


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def fake_redis() -> AsyncIterator[FakeRedis]:
    """Async fakeredis client backed by a fresh in-memory server per test."""
    redis = FakeRedis(decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.fixture
def fake_redis_server() -> FakeServer:
    """Standalone FakeServer so two clients can share state across a 'restart'."""
    return FakeServer()


class _PropagateHandler(logging.Handler):
    """Bridge loguru records into the standard logging tree so caplog sees them."""

    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


@pytest.fixture(autouse=True)
def _loguru_to_caplog(caplog: pytest.LogCaptureFixture) -> Iterator[None]:
    handler_id = _loguru_logger.add(_PropagateHandler(), format="{message}", level=0)
    try:
        yield
    finally:
        _loguru_logger.remove(handler_id)

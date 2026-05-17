"""FastAPI application factory and lifespan wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from redis.asyncio import Redis

from app.api import courses, health
from app.config import Settings, get_settings
from app.manytask import ManytaskClient, TokenAuthCache
from app.storage import CourseStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    logger.info("mr-reviewer starting up; manytask={} redis={}", settings.manytask_base_url, settings.redis_url)

    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manytask = ManytaskClient(
        base_url=settings.manytask_base_url,
        timeout_sec=settings.manytask_request_timeout_sec,
    )
    course_store = CourseStore(redis)
    auth_cache = TokenAuthCache(redis, ttl_sec=settings.ping_cache_ttl_sec)

    app.state.settings = settings
    app.state.redis = redis
    app.state.manytask = manytask
    app.state.course_store = course_store
    app.state.auth_cache = auth_cache

    try:
        yield
    finally:
        logger.info("mr-reviewer shutting down")
        await manytask.aclose()
        await redis.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="manytask-mr-reviewer", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(courses.router)
    return app


app = create_app()

"""FastAPI application factory and lifespan wiring."""

from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from redis.asyncio import Redis

from app.api import courses, health
from app.config import Settings, get_settings
from app.hosting import build_hosting_adapter
from app.manytask import ManytaskClient, TokenAuthCache
from app.storage import CourseStore


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    logger.info(
        "mr-reviewer starting up; manytask={} redis={} gitlab={}",
        settings.manytask_base_url,
        settings.redis_url,
        settings.gitlab_base_url,
    )

    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    manytask = ManytaskClient(
        base_url=settings.manytask_base_url,
        timeout_sec=settings.manytask_request_timeout_sec,
    )
    course_store = CourseStore(redis)
    auth_cache = TokenAuthCache(redis, ttl_sec=settings.ping_cache_ttl_sec)

    hosting_executor = ThreadPoolExecutor(
        max_workers=settings.hosting_executor_workers,
        thread_name_prefix="mrr-hosting",
    )
    hosting_adapter = build_hosting_adapter(
        "gitlab",
        gitlab_token=settings.gitlab_token,
        gitlab_base_url=settings.gitlab_base_url,
        executor=hosting_executor,
    )

    app.state.settings = settings
    app.state.redis = redis
    app.state.manytask = manytask
    app.state.course_store = course_store
    app.state.auth_cache = auth_cache
    app.state.hosting_executor = hosting_executor
    app.state.hosting_adapter = hosting_adapter

    try:
        yield
    finally:
        logger.info("mr-reviewer shutting down")
        await manytask.aclose()
        await redis.aclose()
        hosting_executor.shutdown(wait=True, cancel_futures=True)


def create_app() -> FastAPI:
    app = FastAPI(title="manytask-mr-reviewer", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(courses.router)
    return app


app = create_app()

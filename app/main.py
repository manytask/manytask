"""FastAPI application factory and lifespan wiring."""

import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from loguru import logger
from redis.asyncio import Redis

from app.api import courses, health
from app.checklist import ChecklistPublisher, ChecklistRunner, SummaryRenderer
from app.checklist.sandbox import RunSandbox
from app.config import Settings, get_settings
from app.hosting import build_hosting_adapter
from app.manytask import ManytaskClient, TokenAuthCache
from app.storage import CourseStore, ProcessedCommentStore
from app.worker import ScoreProcessor, WorkerLoop, WorkerMetrics


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

    processed_store = ProcessedCommentStore(redis)

    sandbox = RunSandbox(
        hosting=hosting_adapter,
        gitlab_base_url=settings.gitlab_base_url,
        gitlab_token=settings.gitlab_token,
        manytask_base_url=settings.manytask_base_url,
        timeout_sec=settings.run_step_timeout_sec,
    )
    runner = ChecklistRunner(hosting=hosting_adapter, sandbox=sandbox)
    publisher = ChecklistPublisher(
        hosting=hosting_adapter,
        renderer=SummaryRenderer(),
        bot_username=settings.bot_username,
        label_processed=settings.bot_label_processed,
        label_fail=settings.bot_label_fail,
    )
    metrics = WorkerMetrics()
    score_processor = ScoreProcessor(
        hosting=hosting_adapter,
        manytask=manytask,
        processed_store=processed_store,
        bot_username=settings.bot_username,
    )
    worker = WorkerLoop(
        course_store=course_store,
        hosting=hosting_adapter,
        runner=runner,
        publisher=publisher,
        score_processor=score_processor,
        settings=settings,
        metrics=metrics,
    )

    app.state.settings = settings
    app.state.redis = redis
    app.state.manytask = manytask
    app.state.course_store = course_store
    app.state.auth_cache = auth_cache
    app.state.hosting_executor = hosting_executor
    app.state.hosting_adapter = hosting_adapter
    app.state.processed_store = processed_store
    app.state.worker_metrics = metrics
    app.state.worker = worker
    app.state.worker_task = asyncio.create_task(worker.poll_forever())

    try:
        yield
    finally:
        logger.info("mr-reviewer shutting down")
        app.state.worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await app.state.worker_task
        await manytask.aclose()
        await redis.aclose()
        hosting_executor.shutdown(wait=True, cancel_futures=True)


def create_app() -> FastAPI:
    app = FastAPI(title="manytask-mr-reviewer", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(courses.router)
    return app


app = create_app()

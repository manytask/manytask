"""FastAPI application factory and lifespan wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api import courses, health


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info("mr-reviewer starting up")
    yield
    logger.info("mr-reviewer shutting down")


def create_app() -> FastAPI:
    app = FastAPI(title="manytask-mr-reviewer", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(courses.router)
    return app


app = create_app()

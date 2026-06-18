"""FastAPI dependencies that read shared state from `app.state`."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import Request
from redis.asyncio import Redis

from app.config import Settings
from app.hosting import HostingAdapter
from app.manytask import ManytaskClient, TokenAuthCache
from app.observability import Metrics
from app.storage import CourseStore, ProcessedCommentStore


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_course_store(request: Request) -> CourseStore:
    return request.app.state.course_store  # type: ignore[no-any-return]


def get_processed_store(request: Request) -> ProcessedCommentStore:
    return request.app.state.processed_store  # type: ignore[no-any-return]


def get_manytask_client(request: Request) -> ManytaskClient:
    return request.app.state.manytask  # type: ignore[no-any-return]


def get_auth_cache(request: Request) -> TokenAuthCache:
    return request.app.state.auth_cache  # type: ignore[no-any-return]


def get_hosting_executor(request: Request) -> ThreadPoolExecutor:
    return request.app.state.hosting_executor  # type: ignore[no-any-return]


def get_hosting_adapter(request: Request) -> HostingAdapter:
    return request.app.state.hosting_adapter  # type: ignore[no-any-return]


def get_metrics(request: Request) -> Metrics:
    return request.app.state.metrics  # type: ignore[no-any-return]


def get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]

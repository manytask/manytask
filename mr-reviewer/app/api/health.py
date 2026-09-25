"""Liveness/health endpoint: Redis reachability + poll-loop freshness."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from redis.asyncio import Redis

from app.api.dependencies import get_metrics, get_redis, get_settings_dep
from app.config import Settings
from app.observability import Metrics

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get("/healthz", response_model=HealthResponse)
async def healthz(
    redis: Redis = Depends(get_redis),  # noqa: B008
    metrics: Metrics = Depends(get_metrics),  # noqa: B008
    settings: Settings = Depends(get_settings_dep),  # noqa: B008
) -> HealthResponse:
    try:
        await redis.ping()  # type: ignore[misc]
    except Exception as err:
        logger.warning("healthz: redis unreachable: {}", err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="redis unreachable",
        ) from err

    poll_age = time.time() - metrics.last_poll_timestamp
    if poll_age > settings.healthz_poll_stale_sec:
        logger.warning("healthz: poll loop stale ({:.0f}s)", poll_age)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"poll loop stale ({poll_age:.0f}s)",
        )

    return HealthResponse(status="ok")

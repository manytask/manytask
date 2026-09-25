"""Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.api.dependencies import get_metrics
from app.observability import Metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics_endpoint(metrics: Metrics = Depends(get_metrics)) -> Response:  # noqa: B008
    return Response(content=metrics.render(), media_type=CONTENT_TYPE_LATEST)

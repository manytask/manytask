"""Audit persistence and HTTP outcomes without storing tokens or payloads."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from typing import Any, ParamSpec, TypeVar
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from loguru import logger
from starlette.middleware.base import RequestResponseEndpoint

P = ParamSpec("P")
R = TypeVar("R")
_context: ContextVar[dict[str, Any] | None] = ContextVar("audit_context", default=None)
_TARGET_FIELDS = {"name", "course", "course_name", "mr_id", "comment_id", "username", "task", "score"}


def set_audit_actor(auth_method: str) -> None:
    if context := _context.get():
        context.update(actor=auth_method, auth_method=auth_method)


def audit_event(event: str, outcome: str, **fields: Any) -> None:
    payload = {
        **(_context.get() or {"actor": "system", "auth_method": "system"}),
        "event": event,
        "outcome": outcome,
        **fields,
    }
    level = "ERROR" if outcome == "failed" else "WARNING" if outcome == "rejected" else "INFO"
    logger.log(level, "{}", json.dumps(payload, sort_keys=True))


def audit_write(function: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    parameters = signature(function)

    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments = parameters.bind(*args, **kwargs).arguments
        fields = {
            "operation": function.__name__,
            "operation_id": uuid4().hex,
            "target": {key: value for key, value in arguments.items() if key in _TARGET_FIELDS},
        }
        audit_event("storage.write", "attempted", **fields)
        try:
            result = await function(*args, **kwargs)
        except asyncio.CancelledError:
            # The server may already have applied the write when cancellation arrives.
            audit_event("storage.write", "unknown", **fields, reason="cancelled")
            raise
        except Exception as error:
            audit_event("storage.write", "failed", **fields, error_type=type(error).__name__)
            raise
        audit_event("storage.write", "completed", **fields)
        return result

    return wrapped


def install_request_audit(app: FastAPI) -> None:
    @app.middleware("http")
    async def audit_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
        context: dict[str, Any] = {
            "request_id": uuid4().hex,
            "actor": "anonymous",
            "auth_method": "unauthenticated",
            "method": request.method,
        }
        token = _context.set(context)
        try:
            audit_event("http.request", "attempted")
            response = await call_next(request)
            status = response.status_code
            outcome = "failed" if status >= 500 else "rejected" if status >= 400 else "returned"
            audit_event(
                "http.request",
                outcome,
                status=status,
                route=getattr(request.scope.get("route"), "path", None),
                target=request.path_params,
            )
            return response
        except Exception as error:
            audit_event("http.request", "failed", error_type=type(error).__name__)
            raise
        finally:
            _context.reset(token)

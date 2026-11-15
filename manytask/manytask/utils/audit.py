"""Value-free audit records for requests, storage calls and transactions.

An operation completing is not proof of a commit. Transaction records explicitly
distinguish committed writes from explicit or implicit rollbacks.
"""

import json
import logging
from contextvars import ContextVar
from functools import wraps
from http import HTTPStatus
from inspect import signature
from typing import Any, Callable, ParamSpec, TypeVar
from uuid import uuid4

from flask import Flask, Response, g, has_request_context, request
from sqlalchemy.exc import NoResultFound

logger = logging.getLogger("manytask.audit")
P = ParamSpec("P")
R = TypeVar("R")
_operation: ContextVar[dict[str, Any] | None] = ContextVar("audit_operation", default=None)
_origin: ContextVar[dict[str, Any] | None] = ContextVar("audit_origin", default=None)
_TARGET_FIELDS = {
    "course_name",
    "course_id",
    "namespace_id",
    "username",
    "user_id",
    "task_name",
    "created_by_username",
    "assigned_by_username",
    "slug",
    "role",
    "new_role",
    "is_admin",
    "new_grade",
    "is_solved",
}


def audit_context() -> dict[str, Any]:
    context: dict[str, Any] = dict(_origin.get() or {"actor": "system", "auth_method": "system"})
    if has_request_context():
        context = {
            "actor": g.get("audit_actor", "anonymous"),
            "auth_method": g.get("audit_auth_method", "unauthenticated"),
            "request_id": g.get("audit_request_id"),
            "endpoint": request.endpoint,
            "method": request.method,
            "route": request.url_rule.rule if request.url_rule else None,
            "target": request.view_args or {},
        }
    if operation := _operation.get():
        context.update({key: value for key, value in operation.items() if key != "rejection"})
    return context


def run_with_audit_context(context: dict[str, Any], callback: Callable[[], None]) -> None:
    """Pass identifiers to a worker without retaining a Flask request/session."""
    token = _origin.set(context)
    try:
        callback()
    finally:
        _origin.reset(token)


def audit_event(event: str, outcome: str, *, context: dict[str, Any] | None = None, **fields: Any) -> None:
    payload = {**(audit_context() if context is None else context), "event": event, "outcome": outcome, **fields}
    level = logging.ERROR if outcome == "failed" else logging.WARNING if outcome == "rejected" else logging.INFO
    logger.log(level, "%s", json.dumps(payload, default=str, sort_keys=True))


def audit_rejection(reason: str) -> None:
    """Mark a legacy storage method that returns normally after rejecting a write."""
    if operation := _operation.get():
        operation["rejection"] = reason


def audit_operation(function: Callable[P, R]) -> Callable[P, R]:
    parameters = signature(function)

    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments = parameters.bind(*args, **kwargs).arguments
        target = {key: value for key, value in arguments.items() if key in _TARGET_FIELDS}
        if settings := arguments.get("settings_config"):
            target["course_name"] = settings.course_name
        if function.__name__ == "__init__" and (config := arguments.get("config")):
            target["username"] = config.instance_admin_username
        operation: dict[str, Any] = {"operation": function.__name__, "operation_id": uuid4().hex, "target": target}
        token = _operation.set(operation)
        try:
            audit_event("storage.operation", "attempted")
            result = function(*args, **kwargs)
            reason = operation.get("rejection")
            if result is False and function.__name__ in {"create_course", "edit_course", "delete_course"}:
                reason = "not_created_or_not_found"
            audit_event("storage.operation", "rejected" if reason else "completed", reason=reason)
            return result
        except Exception as error:
            # Exception text can contain SQL parameters, tokens or submitted text.
            rejected = operation.get("rejection") or isinstance(error, (ValueError, PermissionError, NoResultFound))
            audit_event("storage.operation", "rejected" if rejected else "failed", error_type=type(error).__name__)
            raise
        finally:
            _operation.reset(token)

    return wrapped


def install_request_audit(app: Flask) -> None:
    # Some GET routes also write (OAuth signup/admin binding and membership sync).
    # Cover every request so future routes cannot silently bypass the audit hook.
    @app.before_request
    def audit_request_start() -> None:
        g.audit_request_id = uuid4().hex
        g.audit_request_finished = False
        audit_event("http.request", "attempted")

    @app.after_request
    def audit_request_end(response: Response) -> Response:
        status = response.status_code
        outcome = (
            "failed"
            if status >= HTTPStatus.INTERNAL_SERVER_ERROR
            else "rejected"
            if status >= HTTPStatus.BAD_REQUEST
            else "returned"
        )
        audit_event("http.request", outcome, status=status)
        g.audit_request_finished = True
        return response

    @app.teardown_request
    def audit_request_error(error: BaseException | None) -> None:
        # In testing/propagating mode Flask may skip after_request on exceptions.
        if error is not None and not g.get("audit_request_finished", False):
            audit_event("http.request", "failed", error_type=type(error).__name__)
            g.audit_request_finished = True

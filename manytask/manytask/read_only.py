"""Shared read-only policy for requests, storage and background work."""

from http import HTTPStatus
from typing import Any

from flask import Flask, jsonify, make_response, render_template, request
from flask.typing import ResponseReturnValue

READ_ONLY_MESSAGE = "This instance of Manytask is read-only. Scores and settings cannot be changed."


class ReadOnlyModeError(Exception):
    def __init__(self) -> None:
        super().__init__(READ_ONLY_MESSAGE)


def require_writable(read_only: bool) -> None:
    if read_only:
        raise ReadOnlyModeError()


def is_read_only(app: Flask) -> bool:
    return bool(app.config.get("MANYTASK_READ_ONLY", False))


def install_read_only_mode(app: Flask) -> None:
    # Register before CSRF so every rejected mutation has the same response,
    # including submissions from pages opened before the mode was enabled.
    @app.before_request
    def reject_mutations() -> None:
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.endpoint != "root.login":
            require_writable(is_read_only(app))

    @app.errorhandler(ReadOnlyModeError)
    def read_only_error(error: ReadOnlyModeError) -> ResponseReturnValue:
        if request.path.startswith("/api/"):
            response = jsonify(error=str(error), code="read_only")
            response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        else:
            response = make_response(render_template("read_only.html"), HTTPStatus.SERVICE_UNAVAILABLE)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def read_only_context() -> dict[str, Any]:
        return {"read_only": is_read_only(app), "read_only_message": READ_ONLY_MESSAGE}

"""loguru configuration: JSON to stdout with per-module level overrides."""

from __future__ import annotations

import os
import sys
from typing import cast

from loguru import logger

from app.config import Settings

_VALID_LEVELS = {"TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"}


def parse_module_levels(spec: str) -> dict[str, str]:
    """Parse ``'app.worker=DEBUG,app.manytask=WARNING'`` into ``{module: LEVEL}``.

    Malformed or unknown-level entries are skipped so a bad env var never
    crashes startup.
    """

    out: dict[str, str] = {}
    for entry in spec.split(","):
        entry = entry.strip()
        if not entry or "=" not in entry:
            continue
        module, _, level = entry.partition("=")
        module = module.strip()
        level = level.strip().upper()
        if module and level in _VALID_LEVELS:
            out[module] = level
    return out


def configure_logging(settings: Settings) -> None:
    """Install a single stdout sink. No-op under pytest to preserve caplog.

    pytest installs a loguru->stdlib bridge (``tests/conftest.py``); calling
    ``logger.remove()`` here would delete it, so we skip configuration when
    running under pytest and exercise this function directly in unit tests.
    """

    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    logger.remove()
    default_level = settings.log_level.upper()
    if default_level not in _VALID_LEVELS:
        default_level = "INFO"
    levels: dict[str, str] = {"": default_level}
    levels.update(parse_module_levels(settings.log_module_levels))
    logger.add(
        sys.stdout,
        level=0,
        serialize=settings.log_json,
        filter=cast("dict[str | None, str | int | bool]", levels),
        backtrace=False,
        diagnose=False,
        enqueue=True,
    )

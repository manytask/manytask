"""Tests for logging configuration parsing and setup."""

from __future__ import annotations

import sys

import pytest

from app.config import Settings
from app.observability.logging import configure_logging, parse_module_levels


def test_parse_module_levels_basic() -> None:
    assert parse_module_levels("app.worker=DEBUG,app.manytask=WARNING") == {
        "app.worker": "DEBUG",
        "app.manytask": "WARNING",
    }


def test_parse_module_levels_empty() -> None:
    assert parse_module_levels("") == {}
    assert parse_module_levels("   ") == {}


def test_parse_module_levels_tolerates_whitespace_and_trailing_comma() -> None:
    assert parse_module_levels(" app.worker = debug , ") == {"app.worker": "DEBUG"}


def test_parse_module_levels_ignores_malformed_entries() -> None:
    assert parse_module_levels("garbage,app.worker=INFO") == {"app.worker": "INFO"}


def test_configure_logging_noops_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    # PYTEST_CURRENT_TEST is set by pytest during tests; configure_logging must
    # not touch loguru handlers (it would remove the caplog bridge).
    from loguru import logger

    removed: list[object] = []
    monkeypatch.setattr(logger, "remove", lambda *a, **k: removed.append(object()))
    configure_logging(Settings())
    assert removed == []


def test_configure_logging_installs_stdout_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    from loguru import logger

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    added: list[dict[str, object]] = []
    monkeypatch.setattr(logger, "remove", lambda *a, **k: None)

    def _fake_add(sink: object, **kwargs: object) -> int:
        added.append({"sink": sink, **kwargs})
        return 1

    monkeypatch.setattr(logger, "add", _fake_add)

    configure_logging(Settings(log_module_levels="app.worker=DEBUG"))

    assert len(added) == 1
    call = added[0]
    assert call["sink"] is sys.stdout
    assert call["serialize"] is True
    assert call["level"] == 0
    assert call["backtrace"] is False
    assert call["diagnose"] is False
    assert call["enqueue"] is True
    assert call["filter"] == {"": "INFO", "app.worker": "DEBUG"}


def test_configure_logging_falls_back_on_unknown_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    from loguru import logger

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    added: list[dict[str, object]] = []
    monkeypatch.setattr(logger, "remove", lambda *a, **k: None)

    def _fake_add(sink: object, **kwargs: object) -> int:
        added.append({"sink": sink, **kwargs})
        return 1

    monkeypatch.setattr(logger, "add", _fake_add)

    configure_logging(Settings(log_level="NOPE"))

    assert len(added) == 1
    call = added[0]
    assert call["filter"] == {"": "INFO"}

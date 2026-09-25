"""Worker-related settings defaults."""

from __future__ import annotations

from app.config import Settings


def test_poll_interval_default_is_900() -> None:
    settings = Settings()
    assert settings.poll_interval_sec == 900.0


def test_per_mr_timeout_default_is_120() -> None:
    settings = Settings()
    assert settings.per_mr_timeout_sec == 120.0


def test_per_mr_timeout_overridable_via_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PER_MR_TIMEOUT_SEC", "5")
    settings = Settings()
    assert settings.per_mr_timeout_sec == 5.0

"""Unit tests for CheckResult and its aggregate helper."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.checklist.result import CheckResult, all_passed


class TestCheckResult:
    def test_required_fields(self) -> None:
        r = CheckResult(name="pipeline passed", passed=True, message="ok")
        assert r.name == "pipeline passed"
        assert r.passed is True
        assert r.message == "ok"

    def test_is_frozen(self) -> None:
        r = CheckResult(name="x", passed=False, message="y")
        with pytest.raises(FrozenInstanceError):
            r.passed = True  # type: ignore[misc]


class TestAllPassed:
    def test_empty_is_true(self) -> None:
        assert all_passed([]) is True

    def test_single_pass(self) -> None:
        assert all_passed([CheckResult("a", True, "")]) is True

    def test_single_fail(self) -> None:
        assert all_passed([CheckResult("a", False, "")]) is False

    def test_mixed(self) -> None:
        items = [
            CheckResult("a", True, ""),
            CheckResult("b", False, "x"),
            CheckResult("c", True, ""),
        ]
        assert all_passed(items) is False

"""Unit tests for the comment anchor marker helpers."""

from __future__ import annotations

from app.hosting.anchor import extract_anchor, has_anchor, make_anchor_marker


class TestMakeAnchor:
    def test_marker_format(self) -> None:
        assert make_anchor_marker("task-1") == "<!-- mr-reviewer:task-1 -->"

    def test_marker_strips_whitespace(self) -> None:
        assert make_anchor_marker(" task-1 ") == "<!-- mr-reviewer:task-1 -->"


class TestExtractAnchor:
    def test_extract_from_first_line(self) -> None:
        body = "<!-- mr-reviewer:task-1 -->\nhello"
        assert extract_anchor(body) == "task-1"

    def test_extract_from_anywhere(self) -> None:
        body = "score 100\n<!-- mr-reviewer:task-2 -->\nbye"
        assert extract_anchor(body) == "task-2"

    def test_no_marker_returns_none(self) -> None:
        assert extract_anchor("just text") is None

    def test_multiple_anchors_returns_first(self) -> None:
        body = "<!-- mr-reviewer:a -->\n<!-- mr-reviewer:b -->"
        assert extract_anchor(body) == "a"


class TestHasAnchor:
    def test_yes(self) -> None:
        assert has_anchor("<!-- mr-reviewer:x -->\nbody", "x") is True

    def test_wrong_anchor(self) -> None:
        assert has_anchor("<!-- mr-reviewer:x -->\nbody", "y") is False

    def test_no_marker(self) -> None:
        assert has_anchor("plain", "x") is False

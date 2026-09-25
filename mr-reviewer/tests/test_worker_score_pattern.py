"""Unit tests for score-comment pattern compilation and parsing."""

from __future__ import annotations

import pytest

from app.worker.score_pattern import compile_score_pattern, parse_score


class TestCompile:
    def test_default_pattern_regex_text(self) -> None:
        compiled = compile_score_pattern("Score: {score}")
        assert compiled.pattern == r"^Score:\s+(\d+)\s*$"

    def test_requires_exactly_one_placeholder(self) -> None:
        with pytest.raises(ValueError):
            compile_score_pattern("no placeholder")
        with pytest.raises(ValueError):
            compile_score_pattern("{score} and {score}")


class TestParse:
    def test_matches_default(self) -> None:
        compiled = compile_score_pattern("Score: {score}")
        assert parse_score(compiled, "Score: 350") == 350

    def test_tolerates_surrounding_whitespace(self) -> None:
        compiled = compile_score_pattern("Score: {score}")
        assert parse_score(compiled, "   Score:   42  \n") == 42

    def test_returns_none_on_no_match(self) -> None:
        compiled = compile_score_pattern("Score: {score}")
        assert parse_score(compiled, "lgtm") is None
        assert parse_score(compiled, "350") is None
        assert parse_score(compiled, "Score: 350 great work") is None

    def test_custom_pattern_with_suffix(self) -> None:
        compiled = compile_score_pattern("grade={score} pts")
        assert parse_score(compiled, "grade=10 pts") == 10
        assert parse_score(compiled, "grade=10pts") is None

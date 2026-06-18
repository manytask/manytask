"""Compile a course's score-comment template into a matcher.

A teacher writes a score as a comment matching the course's
``score_comment_pattern`` (e.g. ``"Score: {score}"``). ``{score}`` is the numeric
placeholder; surrounding literals are matched verbatim except that runs of
whitespace become flexible (``\\s+``), tolerating extra spaces typed by humans.
"""

from __future__ import annotations

import re

_PLACEHOLDER = "{score}"


def _loosen_whitespace(literal: str) -> str:
    parts = re.split(r"(\s+)", literal)
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        out.append(r"\s+" if part.isspace() else re.escape(part))
    return "".join(out)


def compile_score_pattern(pattern: str) -> re.Pattern[str]:
    """Compile ``pattern`` (with one ``{score}``) into an anchored regex.

    Raises:
        ValueError: ``{score}`` appears zero times or more than once.
    """

    if pattern.count(_PLACEHOLDER) != 1:
        raise ValueError(f"score_comment_pattern must contain exactly one '{{score}}', got: {pattern!r}")
    before, after = pattern.split(_PLACEHOLDER)
    regex = f"^{_loosen_whitespace(before)}(\\d+){_loosen_whitespace(after)}\\s*$"
    return re.compile(regex)


def parse_score(compiled: re.Pattern[str], body: str) -> int | None:
    """Return the integer score from a stripped comment ``body``, or None."""

    match = compiled.match(body.strip())
    if match is None:
        return None
    return int(match.group(1))

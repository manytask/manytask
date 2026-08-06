"""HTML-comment marker used to identify bot-owned comments inside MR bodies.

Why an HTML comment: GitLab and most other hosting UIs render comment bodies
as Markdown, and HTML comments are invisible to humans but trivial to find
programmatically. Sticking a single marker on the first line keeps update
logic simple — we never have to parse the rest of the body.
"""

from __future__ import annotations

import re

_ANCHOR_PREFIX = "<!-- mr-reviewer:"
_ANCHOR_SUFFIX = " -->"
_ANCHOR_RE = re.compile(r"<!--\s*mr-reviewer:([^\s>]+)\s*-->")


def make_anchor_marker(tag: str) -> str:
    return f"{_ANCHOR_PREFIX}{tag.strip()}{_ANCHOR_SUFFIX}"


def extract_anchor(body: str) -> str | None:
    match = _ANCHOR_RE.search(body)
    return match.group(1) if match else None


def has_anchor(body: str, tag: str) -> bool:
    return extract_anchor(body) == tag

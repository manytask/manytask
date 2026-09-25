"""Renders checklist summaries to Markdown via Jinja2."""

from __future__ import annotations

from collections.abc import Sequence

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.checklist.result import CheckResult


class SummaryRenderer:
    """Wraps a Jinja2 Environment loading templates from the package directory."""

    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(self._templates_dir()),
            autoescape=select_autoescape(disabled_extensions=("j2",)),
            keep_trailing_newline=True,
        )
        self._template = self._env.get_template("summary.md.j2")

    @staticmethod
    def _templates_dir() -> str:
        from pathlib import Path

        return str(Path(__file__).parent / "templates")

    def render(self, *, task_name: str, results: Sequence[CheckResult]) -> str:
        return self._template.render(task_name=task_name, results=list(results))

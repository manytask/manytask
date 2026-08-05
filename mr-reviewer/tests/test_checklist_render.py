"""Unit tests for SummaryRenderer."""

from __future__ import annotations

from app.checklist.render import SummaryRenderer
from app.checklist.result import CheckResult


class TestSummaryRenderer:
    def test_renders_all_passed_block(self) -> None:
        renderer = SummaryRenderer()
        body = renderer.render(
            task_name="task-1",
            results=[
                CheckResult("pipeline passed", True, "pipeline succeeded"),
                CheckResult("folder structure", True, "all changes inside `tasks/task-1`"),
            ],
        )

        assert "task-1" in body
        assert "[x] pipeline passed" in body
        assert "[x] folder structure" in body
        assert "[ ]" not in body

    def test_renders_mixed_results(self) -> None:
        renderer = SummaryRenderer()
        body = renderer.render(
            task_name="task-1",
            results=[
                CheckResult("pipeline passed", True, "ok"),
                CheckResult("forbidden files", False, "forbidden files in MR: `a.pyc`"),
            ],
        )

        assert "[x] pipeline passed" in body
        assert "[ ] forbidden files" in body
        assert "`a.pyc`" in body

    def test_renders_empty_results(self) -> None:
        renderer = SummaryRenderer()
        body = renderer.render(task_name="task-1", results=[])
        assert "task-1" in body
        assert "no checks configured" in body.lower() or "пусто" in body.lower()

    def test_renderer_caches_environment(self) -> None:
        """Two instances share no state — but each instance can render many times."""

        renderer = SummaryRenderer()
        first = renderer.render(task_name="t", results=[CheckResult("a", True, "ok")])
        second = renderer.render(task_name="t", results=[CheckResult("a", True, "ok")])
        assert first == second

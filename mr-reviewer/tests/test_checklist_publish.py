"""Unit tests for ChecklistPublisher."""

from __future__ import annotations

from app.checklist.publish import ChecklistPublisher
from app.checklist.render import SummaryRenderer
from app.checklist.result import CheckResult
from app.hosting import MergeRequest
from tests._fakes import FakeHostingAdapter


class TestChecklistPublisher:
    async def test_publishes_with_correct_anchor_and_author(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        bot_username: str,
    ) -> None:
        publisher = ChecklistPublisher(
            hosting=fake_hosting_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        await publisher.publish(
            mr=sample_mr,
            task_name="task-1",
            results=[CheckResult("pipeline passed", True, "ok")],
        )

        assert len(fake_hosting_adapter.posted) == 1
        anchor, body, only_author = fake_hosting_adapter.posted[0]
        assert anchor == "checklist:task-1"
        assert "pipeline passed" in body
        assert only_author == bot_username

    async def test_all_passed_adds_processed_removes_fail(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        bot_username: str,
    ) -> None:
        publisher = ChecklistPublisher(
            hosting=fake_hosting_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        await publisher.publish(
            mr=sample_mr,
            task_name="task-1",
            results=[CheckResult("a", True, ""), CheckResult("b", True, "")],
        )

        assert fake_hosting_adapter.added_labels == [["checklist"]]
        assert fake_hosting_adapter.removed_labels == [["fix it"]]

    async def test_any_failed_adds_both_labels(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        bot_username: str,
    ) -> None:
        publisher = ChecklistPublisher(
            hosting=fake_hosting_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        await publisher.publish(
            mr=sample_mr,
            task_name="task-1",
            results=[CheckResult("a", True, ""), CheckResult("b", False, "bad")],
        )

        assert fake_hosting_adapter.added_labels == [["checklist", "fix it"]]
        assert fake_hosting_adapter.removed_labels == []

    async def test_empty_results_treated_as_passed(
        self,
        fake_hosting_adapter: "FakeHostingAdapter",
        sample_mr: MergeRequest,
        bot_username: str,
    ) -> None:
        publisher = ChecklistPublisher(
            hosting=fake_hosting_adapter,
            renderer=SummaryRenderer(),
            bot_username=bot_username,
            label_processed="checklist",
            label_fail="fix it",
        )

        await publisher.publish(
            mr=sample_mr,
            task_name="task-1",
            results=[],
        )

        assert fake_hosting_adapter.added_labels == [["checklist"]]
        assert fake_hosting_adapter.removed_labels == [["fix it"]]

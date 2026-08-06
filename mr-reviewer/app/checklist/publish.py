"""Publishes a checklist summary to the MR and updates labels accordingly."""

from __future__ import annotations

from collections.abc import Sequence

from app.checklist.render import SummaryRenderer
from app.checklist.result import CheckResult, all_passed
from app.hosting import HostingAdapter, MergeRequest


class ChecklistPublisher:
    def __init__(
        self,
        *,
        hosting: HostingAdapter,
        renderer: SummaryRenderer,
        bot_username: str,
        label_processed: str,
        label_fail: str,
    ) -> None:
        self._hosting = hosting
        self._renderer = renderer
        self._bot_username = bot_username
        self._label_processed = label_processed
        self._label_fail = label_fail

    @staticmethod
    def anchor_for(task_name: str) -> str:
        return f"checklist:{task_name}"

    async def publish(
        self,
        *,
        mr: MergeRequest,
        task_name: str,
        results: Sequence[CheckResult],
    ) -> None:
        body = self._renderer.render(task_name=task_name, results=results)
        await self._hosting.post_or_update_comment(
            mr,
            anchor_tag=self.anchor_for(task_name),
            body=body,
            only_from_author=self._bot_username,
        )

        if all_passed(results):
            await self._hosting.add_labels(mr, [self._label_processed])
            await self._hosting.remove_labels(mr, [self._label_fail])
        else:
            await self._hosting.add_labels(mr, [self._label_processed, self._label_fail])

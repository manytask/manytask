"""Processes reviewer score comments on a single MR into manytask reports."""

from __future__ import annotations

import re

from loguru import logger

from app.checklist.step import CheckContext
from app.hosting import HostingAdapter, MergeRequest
from app.manytask.errors import ManytaskReportRejected, ManytaskTokenForbidden, ManytaskUnavailable
from app.manytask.protocol import ManytaskReporter
from app.storage import ProcessedCommentStore
from app.worker.score_pattern import parse_score


class ScoreProcessor:
    """Turns admin-authored score comments into manytask ``report`` calls.

    Idempotency: a comment is marked processed only on a terminal outcome
    (reported, manytask rejected it as 4xx, or author is not an admin). Transient
    manytask outages and a forbidden course token (403) leave the comment
    unprocessed so the next cycle retries once manytask/token recovers.
    """

    def __init__(
        self,
        *,
        hosting: HostingAdapter,
        manytask: ManytaskReporter,
        processed_store: ProcessedCommentStore,
        bot_username: str,
    ) -> None:
        self._hosting = hosting
        self._manytask = manytask
        self._processed = processed_store
        self._bot_username = bot_username

    async def process(
        self,
        *,
        ctx: CheckContext,
        mr: MergeRequest,
        task_name: str,
        compiled: re.Pattern[str],
    ) -> None:
        mr_id = str(mr.mr_iid)
        comments = await self._hosting.get_comments(mr)
        for comment in comments:
            if comment.author_username == self._bot_username:
                continue
            comment_id = str(comment.id)
            if await self._processed.is_processed(ctx.course_name, mr_id, comment_id):
                continue

            score = parse_score(compiled, comment.body)
            if score is None:
                continue  # not a score comment — cheap local check, don't burn the id

            try:
                author_is_admin = await self._manytask.is_admin(
                    ctx.course_name,
                    token=ctx.course_token,
                    rms_username=comment.author_username,
                )
            except ManytaskUnavailable:
                logger.warning(
                    "is_admin check failed (transient) for {} on {}!{}; will retry",
                    comment.author_username,
                    mr.project_path_with_namespace,
                    mr.mr_iid,
                )
                continue
            except ManytaskTokenForbidden:
                # Course token misconfigured — operator must fix it. Leave the
                # comment unprocessed so the score is reported once the token works.
                logger.warning(
                    "manytask rejected course token (403) on is_admin for course {}; fix the course token — will retry",
                    ctx.course_name,
                )
                continue

            if not author_is_admin:
                logger.info(
                    "ignoring score comment from non-admin {} on {}!{}",
                    comment.author_username,
                    mr.project_path_with_namespace,
                    mr.mr_iid,
                )
                await self._processed.mark_processed(ctx.course_name, mr_id, comment_id)
                continue

            # If the per-MR timeout fires between a successful report and the
            # mark_processed below, the next cycle re-reports the same score.
            # report_score uses allow_reduction=True, so a duplicate is idempotent
            # (same score, never reduced) — at-least-once is acceptable here.
            try:
                final = await self._manytask.report_score(
                    ctx.course_name,
                    token=ctx.course_token,
                    username=mr.author_username,
                    task=task_name,
                    score=score,
                    allow_reduction=True,
                    check_deadline=False,
                )
            except ManytaskReportRejected as err:
                logger.warning(
                    "manytask rejected score {} for {} task {}: {} (terminal, marking processed)",
                    score,
                    mr.author_username,
                    task_name,
                    err,
                )
                await self._processed.mark_processed(ctx.course_name, mr_id, comment_id)
                continue
            except ManytaskUnavailable:
                logger.warning(
                    "manytask unavailable reporting score {} for {} task {}; will retry",
                    score,
                    mr.author_username,
                    task_name,
                )
                continue
            except ManytaskTokenForbidden:
                # Course token misconfigured — operator must fix it. Leave the
                # comment unprocessed so the score is reported once the token works.
                logger.warning(
                    "manytask rejected course token (403) reporting score for course {}; "
                    "fix the course token — will retry",
                    ctx.course_name,
                )
                continue

            logger.info(
                "reported score {} (final={}) for {} task {} from admin {}",
                score,
                final,
                mr.author_username,
                task_name,
                comment.author_username,
            )
            await self._processed.mark_processed(ctx.course_name, mr_id, comment_id)

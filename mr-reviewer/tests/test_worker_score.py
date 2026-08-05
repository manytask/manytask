"""Unit tests for ScoreProcessor (one MR's score comments)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fakeredis.aioredis import FakeRedis

from app.checklist.step import CheckContext
from app.hosting import Comment, MergeRequest
from app.manytask.errors import ManytaskReportRejected, ManytaskTokenForbidden, ManytaskUnavailable
from app.storage import ProcessedCommentStore
from app.worker.score import ScoreProcessor
from app.worker.score_pattern import compile_score_pattern
from tests._fakes import FakeHostingAdapter, FakeManytaskClient

BOT = "manytask-mr-reviewer-bot"


def _mr() -> MergeRequest:
    return MergeRequest(
        project_id=42,
        mr_iid=7,
        sha="x",
        web_url="https://gitlab.test/g/p/-/merge_requests/7",
        source_branch="task-1",
        target_branch="main",
        author_username="student",
        labels=("task-1",),
        title="t",
        project_path_with_namespace="g/p",
    )


def _comment(cid: int, author: str, body: str) -> Comment:
    return Comment(id=cid, author_username=author, body=body, created_at=datetime(2026, 5, 1, tzinfo=timezone.utc))


@pytest.fixture
async def store() -> ProcessedCommentStore:
    return ProcessedCommentStore(FakeRedis(decode_responses=True))


def _processor(
    hosting: FakeHostingAdapter, manytask: FakeManytaskClient, store: ProcessedCommentStore
) -> ScoreProcessor:
    return ScoreProcessor(hosting=hosting, manytask=manytask, processed_store=store, bot_username=BOT)


async def test_admin_score_is_reported_and_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.admins.add("teacher")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert len(manytask.reported) == 1
    call = manytask.reported[0]
    assert call["username"] == "student"
    assert call["task"] == "task-1"
    assert call["score"] == 350
    assert call["allow_reduction"] is True
    assert call["check_deadline"] is False
    assert await store.is_processed("python-101", "7", "10") is True


async def test_non_admin_score_is_skipped_and_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "student", "Score: 350")]
    manytask = FakeManytaskClient()  # nobody is admin
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert manytask.reported == []
    assert await store.is_processed("python-101", "7", "10") is True


async def test_bot_own_comment_ignored(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, BOT, "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.admins.add(BOT)
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert manytask.reported == []
    assert await store.is_processed("python-101", "7", "10") is False


async def test_already_processed_comment_skipped(store: ProcessedCommentStore) -> None:
    await store.mark_processed("python-101", "7", "10")
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.admins.add("teacher")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert manytask.reported == []


async def test_transient_report_failure_not_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.admins.add("teacher")
    manytask.report_error = ManytaskUnavailable("down")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert await store.is_processed("python-101", "7", "10") is False


async def test_terminal_report_rejection_is_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.admins.add("teacher")
    manytask.report_error = ManytaskReportRejected("no such task")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert await store.is_processed("python-101", "7", "10") is True


async def test_transient_is_admin_failure_not_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.is_admin_error = ManytaskUnavailable("down")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert manytask.reported == []
    assert await store.is_processed("python-101", "7", "10") is False


async def test_forbidden_token_on_is_admin_not_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.is_admin_error = ManytaskTokenForbidden("bad course token")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert manytask.reported == []
    assert await store.is_processed("python-101", "7", "10") is False


async def test_forbidden_token_on_report_not_marked(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "Score: 350")]
    manytask = FakeManytaskClient()
    manytask.admins.add("teacher")
    manytask.report_error = ManytaskTokenForbidden("bad course token")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert await store.is_processed("python-101", "7", "10") is False


async def test_non_score_comment_left_unprocessed(store: ProcessedCommentStore) -> None:
    hosting = FakeHostingAdapter()
    hosting.notes = [_comment(10, "teacher", "lgtm, nice work")]
    manytask = FakeManytaskClient()
    manytask.admins.add("teacher")
    proc = _processor(hosting, manytask, store)
    ctx = CheckContext(course_name="python-101", course_token="tok")

    await proc.process(ctx=ctx, mr=_mr(), task_name="task-1", compiled=compile_score_pattern("Score: {score}"))

    assert manytask.reported == []
    assert await store.is_processed("python-101", "7", "10") is False

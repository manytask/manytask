"""Unit tests for WorkerLoop: cycle orchestration, isolation, timeouts, cancellation."""

from __future__ import annotations

import asyncio

import pytest
from fakeredis.aioredis import FakeRedis

from app.checklist import ChecklistPublisher, ChecklistRunner, SummaryRenderer
from app.config import Settings
from app.hosting import MergeRequest, PipelineStatus
from app.models import CourseConfig
from app.observability import Metrics
from app.storage import CourseStore, ProcessedCommentStore
from app.worker.loop import WorkerLoop
from app.worker.score import ScoreProcessor
from tests._fakes import FakeHostingAdapter, FakeManytaskClient

BOT = "manytask-mr-reviewer-bot"


def _mr(iid: int = 7) -> MergeRequest:
    return MergeRequest(
        project_id=42,
        mr_iid=iid,
        sha="x",
        web_url=f"https://gitlab.test/g/p/-/merge_requests/{iid}",
        source_branch="task-1",
        target_branch="main",
        author_username="student",
        labels=("task-1",),
        title="t",
        project_path_with_namespace="g/p",
    )


def _config(**overrides: object) -> CourseConfig:
    payload: dict[str, object] = {
        "gitlab_group": "course/students",
        "tasks": [{"name": "task-1", "checklist": [{"type": "pipeline_passed"}]}],
    }
    payload.update(overrides)
    return CourseConfig.model_validate(payload)


def _build_loop(
    *,
    course_store: CourseStore,
    hosting: FakeHostingAdapter,
    manytask: FakeManytaskClient,
    processed: ProcessedCommentStore,
    settings: Settings,
    metrics: Metrics | None = None,
) -> WorkerLoop:
    runner = ChecklistRunner(hosting=hosting, sandbox=None)
    publisher = ChecklistPublisher(
        hosting=hosting,
        renderer=SummaryRenderer(),
        bot_username=BOT,
        label_processed="checklist",
        label_fail="fix it",
    )
    score_processor = ScoreProcessor(hosting=hosting, manytask=manytask, processed_store=processed, bot_username=BOT)
    return WorkerLoop(
        course_store=course_store,
        hosting=hosting,
        runner=runner,
        publisher=publisher,
        score_processor=score_processor,
        settings=settings,
        metrics=metrics or Metrics(),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(poll_interval_sec=900.0, per_mr_timeout_sec=120.0)


async def test_cycle_runs_checklist_and_publishes(settings: Settings) -> None:
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    await course_store.upsert_course("python-101", _config(), course_token="tok")
    hosting = FakeHostingAdapter()
    hosting.open_mrs[("course/students", "task-1")] = [_mr()]
    manytask = FakeManytaskClient()
    loop = _build_loop(
        course_store=course_store,
        hosting=hosting,
        manytask=manytask,
        processed=ProcessedCommentStore(redis),
        settings=settings,
    )

    await loop.run_cycle()

    assert len(hosting.posted) == 1  # summary comment published
    assert ["checklist"] in hosting.added_labels  # pipeline_passed -> all green


async def test_manual_review_false_task_skipped(settings: Settings) -> None:
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    cfg = _config(tasks=[{"name": "task-1", "manual_review": False, "checklist": [{"type": "pipeline_passed"}]}])
    await course_store.upsert_course("python-101", cfg, course_token="tok")
    hosting = FakeHostingAdapter()
    hosting.open_mrs[("course/students", "task-1")] = [_mr()]
    loop = _build_loop(
        course_store=course_store,
        hosting=hosting,
        manytask=FakeManytaskClient(),
        processed=ProcessedCommentStore(redis),
        settings=settings,
    )

    await loop.run_cycle()

    assert hosting.posted == []


async def test_course_deleted_midcycle_is_skipped(settings: Settings) -> None:
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    await course_store.upsert_course("ghost", _config(), course_token="tok")
    hosting = FakeHostingAdapter()
    loop = _build_loop(
        course_store=course_store,
        hosting=hosting,
        manytask=FakeManytaskClient(),
        processed=ProcessedCommentStore(redis),
        settings=settings,
    )

    # Simulate DELETE landing after list_courses but before get_course.
    original_get = course_store.get_course

    async def racing_get(name: str):  # type: ignore[no-untyped-def]
        await course_store.delete_course(name)
        return await original_get(name)

    course_store.get_course = racing_get  # type: ignore[method-assign]

    await loop.run_cycle()  # must not raise

    assert hosting.posted == []


async def test_one_course_failure_isolated(settings: Settings) -> None:
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    await course_store.upsert_course("bad", _config(), course_token="tok")
    await course_store.upsert_course("good", _config(), course_token="tok")
    hosting = FakeHostingAdapter()
    hosting.open_mrs[("course/students", "task-1")] = [_mr()]
    manytask = FakeManytaskClient()
    loop = _build_loop(
        course_store=course_store,
        hosting=hosting,
        manytask=manytask,
        processed=ProcessedCommentStore(redis),
        settings=settings,
    )

    # Make list_open_mrs raise only for the "bad" course's first call.
    calls = {"n": 0}
    real_list = hosting.list_open_mrs

    async def flaky_list(group_path: str, label: str):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("gitlab boom")
        return await real_list(group_path, label)

    hosting.list_open_mrs = flaky_list  # type: ignore[method-assign]

    await loop.run_cycle()  # must not raise

    # The healthy course still published its summary.
    assert len(hosting.posted) == 1


async def test_per_mr_timeout_continues_cycle(settings: Settings) -> None:
    settings = Settings(poll_interval_sec=900.0, per_mr_timeout_sec=0.05)
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    await course_store.upsert_course("python-101", _config(), course_token="tok")
    hosting = FakeHostingAdapter()
    hosting.open_mrs[("course/students", "task-1")] = [_mr(7), _mr(8)]
    loop = _build_loop(
        course_store=course_store,
        hosting=hosting,
        manytask=FakeManytaskClient(),
        processed=ProcessedCommentStore(redis),
        settings=settings,
    )

    # Make publish hang on the first MR only.
    real_publish = loop._publisher.publish
    seen = {"n": 0}

    async def slow_publish(**kwargs):  # type: ignore[no-untyped-def]
        seen["n"] += 1
        if seen["n"] == 1:
            await asyncio.sleep(10)
        await real_publish(**kwargs)

    loop._publisher.publish = slow_publish  # type: ignore[method-assign]

    await loop.run_cycle()  # must finish despite first MR timing out

    # Second MR still got published (its publish ran after the first timed out).
    assert seen["n"] == 2


async def test_overlap_recorded_when_cycle_exceeds_interval(settings: Settings) -> None:
    settings = Settings(poll_interval_sec=0.0, per_mr_timeout_sec=120.0)
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    metrics = Metrics()
    loop = _build_loop(
        course_store=course_store,
        hosting=FakeHostingAdapter(),
        manytask=FakeManytaskClient(),
        processed=ProcessedCommentStore(redis),
        settings=settings,
        metrics=metrics,
    )

    await loop.run_cycle()

    assert metrics.registry.get_sample_value("poll_cycles_total") == 1.0
    assert metrics.registry.get_sample_value("poll_cycle_overlapping_total") == 1.0


async def test_poll_forever_cancellation_is_graceful(settings: Settings) -> None:
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    loop = _build_loop(
        course_store=course_store,
        hosting=FakeHostingAdapter(),
        manytask=FakeManytaskClient(),
        processed=ProcessedCommentStore(redis),
        settings=Settings(poll_interval_sec=0.01, per_mr_timeout_sec=120.0),
    )

    task = asyncio.create_task(loop.poll_forever())
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_cycle_records_mr_processed_and_failures(settings: Settings) -> None:
    redis = FakeRedis(decode_responses=True)
    course_store = CourseStore(redis)
    await course_store.upsert_course("python-101", _config(), course_token="tok")
    hosting = FakeHostingAdapter()
    hosting.pipeline_status = PipelineStatus(id=1, state="failed", web_url=None, sha="x")
    hosting.open_mrs[("course/students", "task-1")] = [_mr()]
    metrics = Metrics()
    loop = _build_loop(
        course_store=course_store,
        hosting=hosting,
        manytask=FakeManytaskClient(),
        processed=ProcessedCommentStore(redis),
        settings=settings,
        metrics=metrics,
    )

    await loop.run_cycle()

    assert metrics.registry.get_sample_value("mrs_processed_total", {"course": "python-101"}) == 1.0
    assert (
        metrics.registry.get_sample_value(
            "checklist_failures_total", {"course": "python-101", "type": "pipeline passed"}
        )
        == 1.0
    )

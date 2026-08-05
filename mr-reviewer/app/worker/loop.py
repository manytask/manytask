"""Background poll loop that drives the review pipeline."""

from __future__ import annotations

import asyncio
import re
import time

from loguru import logger

from app.checklist import ChecklistPublisher, ChecklistRunner
from app.checklist.step import CheckContext
from app.config import Settings
from app.hosting import HostingAdapter, MergeRequest
from app.models import CourseConfig, TaskConfig
from app.observability import Metrics
from app.storage import CourseStore
from app.worker.score import ScoreProcessor
from app.worker.score_pattern import compile_score_pattern


class WorkerLoop:
    """Polls courses, runs the checklist, publishes summaries, reports scores.

    One ``run_cycle`` re-reads ``CourseStore`` (list + per-course get) so a
    concurrent ``DELETE /courses`` cannot crash the loop. Course- and MR-level
    failures are isolated; ``asyncio.CancelledError`` propagates for graceful
    shutdown.
    """

    def __init__(
        self,
        *,
        course_store: CourseStore,
        hosting: HostingAdapter,
        runner: ChecklistRunner,
        publisher: ChecklistPublisher,
        score_processor: ScoreProcessor,
        settings: Settings,
        metrics: Metrics,
    ) -> None:
        self._course_store = course_store
        self._hosting = hosting
        self._runner = runner
        self._publisher = publisher
        self._score_processor = score_processor
        self._settings = settings
        self._metrics = metrics

    async def poll_forever(self) -> None:
        logger.info("worker loop started; interval={}s", self._settings.poll_interval_sec)
        try:
            while True:
                try:
                    await self.run_cycle()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("poll cycle crashed; continuing after sleep")
                await asyncio.sleep(self._settings.poll_interval_sec)
        except asyncio.CancelledError:
            logger.info("worker loop cancelled; shutting down")
            raise

    async def run_cycle(self) -> None:
        start = time.monotonic()
        names = await self._course_store.list_courses()
        logger.info("poll cycle start; courses={}", len(names))
        for name in names:
            try:
                await self._process_course(name)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("course {} failed; isolating", name)
        elapsed = time.monotonic() - start
        self._metrics.record_cycle(elapsed)
        if elapsed > self._settings.poll_interval_sec:
            self._metrics.record_overlap()
            logger.warning(
                "poll cycle took {:.1f}s > interval {}s (saturation)",
                elapsed,
                self._settings.poll_interval_sec,
            )
        logger.info("poll cycle done in {:.1f}s", elapsed)

    async def _process_course(self, name: str) -> None:
        loaded = await self._course_store.get_course(name)
        if loaded is None:
            logger.debug("course {} gone or incompatible; skip", name)
            return
        _, config, token = loaded
        ctx = CheckContext(course_name=name, course_token=token)
        compiled = compile_score_pattern(config.score_comment_pattern)

        for task in config.tasks:
            if not task.manual_review:
                continue
            mrs = await self._hosting.list_open_mrs(config.gitlab_group, task.name)
            logger.info("course {} task {}: {} open MRs", name, task.name, len(mrs))
            for mr in mrs:
                try:
                    await asyncio.wait_for(
                        self._process_mr(ctx, config, task, mr, compiled),
                        timeout=self._settings.per_mr_timeout_sec,
                    )
                except asyncio.CancelledError:
                    raise
                except TimeoutError:
                    logger.warning(
                        "per-MR timeout after {}s on {}!{}",
                        self._settings.per_mr_timeout_sec,
                        mr.project_path_with_namespace,
                        mr.mr_iid,
                    )
                except Exception:
                    logger.exception(
                        "MR {}!{} failed; isolating",
                        mr.project_path_with_namespace,
                        mr.mr_iid,
                    )

    async def _process_mr(
        self,
        ctx: CheckContext,
        config: CourseConfig,
        task: TaskConfig,
        mr: MergeRequest,
        compiled: re.Pattern[str],
    ) -> None:
        results = await self._runner.run(task, mr, ctx)
        for result in results:
            if not result.passed:
                self._metrics.record_checklist_failure(ctx.course_name, result.name)
        await self._publisher.publish(mr=mr, task_name=task.name, results=results)
        await self._score_processor.process(ctx=ctx, mr=mr, task_name=task.name, compiled=compiled)
        self._metrics.record_mr_processed(ctx.course_name)

"""Prometheus collectors for the poll loop and external integrations.

Each ``Metrics`` instance owns a private ``CollectorRegistry`` so the FastAPI
app can be re-created in tests without tripping prometheus-client's
duplicate-registration guard. Counter names omit the ``_total`` suffix because
prometheus-client appends it to the exposed sample automatically.
"""

from __future__ import annotations

import time

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

_POLL_DURATION_BUCKETS = (0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 900.0, 1800.0)
_RUN_STEP_BUCKETS = (0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0)


class Metrics:
    def __init__(self, *, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry()

        self._poll_cycles = Counter(
            "poll_cycles",
            "Completed poll cycles",
            registry=self.registry,
        )
        self._poll_cycle_overlapping = Counter(
            "poll_cycle_overlapping",
            "Cycles whose wall-clock duration exceeded the poll interval",
            registry=self.registry,
        )
        self._poll_duration = Histogram(
            "poll_duration_seconds",
            "Wall-clock duration of one poll cycle",
            buckets=_POLL_DURATION_BUCKETS,
            registry=self.registry,
        )
        self._mrs_processed = Counter(
            "mrs_processed",
            "MRs processed by the worker",
            ["course"],
            registry=self.registry,
        )
        self._checklist_failures = Counter(
            "checklist_failures",
            "Failed checklist steps",
            ["course", "type"],
            registry=self.registry,
        )
        self._manytask_errors = Counter(
            "manytask_errors",
            "Manytask availability errors (transport / 5xx)",
            ["endpoint"],
            registry=self.registry,
        )
        self._run_step_duration = Histogram(
            "run_step_duration_seconds",
            "Duration of the run: checklist step",
            ["course", "task"],
            buckets=_RUN_STEP_BUCKETS,
            registry=self.registry,
        )

        # Liveness watermark: wall-clock time the last cycle finished. Seeded
        # with process start so a fresh boot is not reported stale before the
        # first (possibly long) cycle completes.
        self.last_poll_timestamp: float = time.time()

    def record_cycle(self, duration_seconds: float) -> None:
        self._poll_cycles.inc()
        self._poll_duration.observe(duration_seconds)
        self.last_poll_timestamp = time.time()

    def record_overlap(self) -> None:
        self._poll_cycle_overlapping.inc()

    def record_mr_processed(self, course: str) -> None:
        self._mrs_processed.labels(course=course).inc()

    def record_checklist_failure(self, course: str, check_type: str) -> None:
        self._checklist_failures.labels(course=course, type=check_type).inc()

    def record_manytask_error(self, endpoint: str) -> None:
        self._manytask_errors.labels(endpoint=endpoint).inc()

    def observe_run_step(self, course: str, task: str, duration_seconds: float) -> None:
        self._run_step_duration.labels(course=course, task=task).observe(duration_seconds)

    def render(self) -> bytes:
        return generate_latest(self.registry)

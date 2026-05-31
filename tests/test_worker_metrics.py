"""Unit tests for WorkerMetrics counters."""

from __future__ import annotations

from app.worker.metrics import WorkerMetrics


def test_record_cycle_increments_and_stores_duration() -> None:
    metrics = WorkerMetrics()
    metrics.record_cycle(3.5)
    metrics.record_cycle(4.0)
    assert metrics.cycles_total == 2
    assert metrics.last_cycle_duration_seconds == 4.0


def test_record_overlap_increments() -> None:
    metrics = WorkerMetrics()
    assert metrics.overlapping_cycles_total == 0
    metrics.record_overlap()
    metrics.record_overlap()
    assert metrics.overlapping_cycles_total == 2

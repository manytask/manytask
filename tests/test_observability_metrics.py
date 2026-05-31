"""Unit tests for the Metrics facade and its Prometheus collectors."""

from __future__ import annotations

import time

from app.observability import Metrics


def _value(metrics: Metrics, name: str, labels: dict[str, str] | None = None) -> float | None:
    return metrics.registry.get_sample_value(name, labels or {})


def test_record_cycle_increments_counter_and_histogram() -> None:
    metrics = Metrics()
    metrics.record_cycle(3.5)
    metrics.record_cycle(4.0)
    assert _value(metrics, "poll_cycles_total") == 2.0
    assert _value(metrics, "poll_duration_seconds_count") == 2.0


def test_record_cycle_refreshes_last_poll_timestamp() -> None:
    metrics = Metrics()
    before = metrics.last_poll_timestamp
    time.sleep(0.01)
    metrics.record_cycle(1.0)
    assert metrics.last_poll_timestamp > before


def test_last_poll_timestamp_seeded_at_construction() -> None:
    metrics = Metrics()
    assert abs(metrics.last_poll_timestamp - time.time()) < 5.0


def test_record_overlap_increments() -> None:
    metrics = Metrics()
    metrics.record_overlap()
    metrics.record_overlap()
    assert _value(metrics, "poll_cycle_overlapping_total") == 2.0


def test_mr_processed_is_labelled_by_course() -> None:
    metrics = Metrics()
    metrics.record_mr_processed("python-101")
    metrics.record_mr_processed("python-101")
    metrics.record_mr_processed("cpp-201")
    assert _value(metrics, "mrs_processed_total", {"course": "python-101"}) == 2.0
    assert _value(metrics, "mrs_processed_total", {"course": "cpp-201"}) == 1.0


def test_checklist_failure_labelled_by_course_and_type() -> None:
    metrics = Metrics()
    metrics.record_checklist_failure("python-101", "pipeline passed")
    assert _value(metrics, "checklist_failures_total", {"course": "python-101", "type": "pipeline passed"}) == 1.0


def test_manytask_error_labelled_by_endpoint() -> None:
    metrics = Metrics()
    metrics.record_manytask_error("report")
    metrics.record_manytask_error("report")
    assert _value(metrics, "manytask_errors_total", {"endpoint": "report"}) == 2.0


def test_run_step_duration_observed_by_course_and_task() -> None:
    metrics = Metrics()
    metrics.observe_run_step("python-101", "task-1", 2.0)
    assert _value(metrics, "run_step_duration_seconds_count", {"course": "python-101", "task": "task-1"}) == 1.0


def test_render_returns_prometheus_text() -> None:
    metrics = Metrics()
    metrics.record_cycle(1.0)
    body = metrics.render().decode()
    assert "poll_cycles_total" in body
    assert "poll_duration_seconds_bucket" in body


def test_each_instance_has_isolated_registry() -> None:
    # Two instances must not raise "Duplicate timeseries" and must not share counts.
    a = Metrics()
    b = Metrics()
    a.record_cycle(1.0)
    assert _value(a, "poll_cycles_total") == 1.0
    assert _value(b, "poll_cycles_total") == 0.0

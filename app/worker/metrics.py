"""In-process worker metrics.

These counters are the hook the observability ticket (EDUCATION-59067) will wire
to a real exporter (Prometheus). For now they live in memory so the poll loop can
record cycle duration and saturation (a cycle that outran the poll interval).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WorkerMetrics:
    cycles_total: int = 0
    overlapping_cycles_total: int = 0
    last_cycle_duration_seconds: float = 0.0

    def record_cycle(self, duration_seconds: float) -> None:
        self.cycles_total += 1
        self.last_cycle_duration_seconds = duration_seconds

    def record_overlap(self) -> None:
        self.overlapping_cycles_total += 1

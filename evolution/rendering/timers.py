"""Lightweight timing helpers for render instrumentation."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Dict, Iterator


@dataclass
class _TimerStats:
    total_ms: float = 0.0
    count: int = 0


class TimerAggregator:
    """Collects timing samples and emits rolling averages."""

    def __init__(self, logger=None, *, log_interval: float = 2.0) -> None:
        self._stats: Dict[str, _TimerStats] = {}
        self._last_log = time.perf_counter()
        self._log_interval = log_interval
        self._logger = logger

    @contextmanager
    def time(self, name: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            stats = self._stats.setdefault(name, _TimerStats())
            stats.total_ms += duration_ms
            stats.count += 1

    def maybe_log(self) -> None:
        if self._logger is None:
            return
        now = time.perf_counter()
        if now - self._last_log < self._log_interval:
            return
        lines = []
        for name, stats in self._stats.items():
            if stats.count == 0:
                continue
            avg_ms = stats.total_ms / max(1, stats.count)
            lines.append(f"{name}: {avg_ms:.2f} ms ({stats.count} samples)")
        if lines:
            self._logger.info("Perf timers | %s", "; ".join(lines))
        self._stats.clear()
        self._last_log = now

    def reset(self) -> None:
        self._stats.clear()
        self._last_log = time.perf_counter()

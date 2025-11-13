"""Statistics aggregation stubs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SimulationStats:
    """Placeholder for simulation statistics."""

    tick_count: int = 0

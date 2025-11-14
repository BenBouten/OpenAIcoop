"""Core simulation engine abstractions stub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SimulationStep(Protocol):
    """Protocol representing a unit of work for the simulation engine."""

    def execute(self) -> None:
        """Execute a single simulation step."""


@dataclass(slots=True)
class SimulationState:
    """Placeholder for the shared simulation state container."""

    running: bool = False
    world_type: str = "Rift Valley"


def run_engine(step: SimulationStep, state: SimulationState) -> None:
    """Run the simulation engine for a single step."""
    if state.running:
        step.execute()

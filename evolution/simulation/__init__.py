"""Simulation package containing the main loop and bootstrap helpers."""

from __future__ import annotations
from .state import SimulationState
from .loop import run

__all__ = [
    "loop",
    "bootstrap",
    "environment",
    "state",
]

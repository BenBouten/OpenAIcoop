"""Movement helpers for entities."""

from __future__ import annotations

from typing import Tuple


def move(position: Tuple[float, float], velocity: Tuple[float, float]) -> Tuple[float, float]:
    """Return a new position after applying the velocity."""
    return position[0] + velocity[0], position[1] + velocity[1]

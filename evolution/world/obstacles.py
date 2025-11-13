"""Obstacle definitions stub module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class Obstacle:
    """Placeholder obstacle representation."""

    position: Tuple[float, float]
    radius: float

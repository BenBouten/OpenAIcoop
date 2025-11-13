"""Vegetation helpers stub module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class Vegetation:
    """Placeholder vegetation entry."""

    position: Tuple[float, float]
    growth_stage: int

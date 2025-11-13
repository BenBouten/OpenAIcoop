"""Lifeform entity placeholder definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class Lifeform:
    """Placeholder lifeform data container."""

    name: str
    position: Tuple[float, float]

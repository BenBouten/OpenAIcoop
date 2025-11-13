"""Biome definitions stub module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class Biome:
    """Placeholder biome description."""

    name: str
    color: Tuple[int, int, int]

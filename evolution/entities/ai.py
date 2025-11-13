"""AI behavior stubs for entities."""

from __future__ import annotations

from typing import Protocol


class DecisionMaker(Protocol):
    """Protocol describing a decision making component."""

    def decide(self) -> None:
        """Make a decision for the associated entity."""

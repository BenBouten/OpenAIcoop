"""Minimal 2D vector helper used by the lightweight physics tests."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Vector2:
    """Tiny immutable vector replacement for :class:`pygame.math.Vector2`."""

    x: float = 0.0
    y: float = 0.0

    # Basic arithmetic -----------------------------------------------------
    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Vector2":
        return self.__mul__(scalar)

    def rotate_rad(self, angle: float) -> "Vector2":
        """Return a copy rotated ``angle`` radians counter-clockwise."""

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return Vector2(self.x * cos_a - self.y * sin_a, self.x * sin_a + self.y * cos_a)

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def __iter__(self):  # pragma: no cover - convenience
        yield self.x
        yield self.y

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"Vector2(x={self.x:.3f}, y={self.y:.3f})"

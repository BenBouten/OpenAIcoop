"""Mathematical utility functions with performance optimizations.

This module provides optimized mathematical functions that are commonly
used in performance-critical paths of the simulation.
"""

from __future__ import annotations

import math
from functools import lru_cache


@lru_cache(maxsize=1024)
def distance_squared(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate squared distance between two points.

    Faster than distance() when only comparison is needed, as it avoids sqrt.
    Uses LRU cache for repeated queries.

    Args:
        x1, y1: Coordinates of first point
        x2, y2: Coordinates of second point

    Returns:
        Squared Euclidean distance between the points
    """
    dx = x2 - x1
    dy = y2 - y1
    return dx * dx + dy * dy


@lru_cache(maxsize=1024)
def distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate Euclidean distance between two points.

    Uses LRU cache for repeated queries. For comparisons only,
    prefer distance_squared() to avoid the sqrt calculation.

    Args:
        x1, y1: Coordinates of first point
        x2, y2: Coordinates of second point

    Returns:
        Euclidean distance between the points
    """
    return math.sqrt(distance_squared(x1, y1, x2, y2))


def normalize_angle(angle: float) -> float:
    """Normalize angle to range [0, 2π).

    Args:
        angle: Angle in radians

    Returns:
        Normalized angle in range [0, 2π)
    """
    two_pi = 2.0 * math.pi
    return angle % two_pi


@lru_cache(maxsize=256)
def angle_between_points(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate angle from point 1 to point 2.

    Args:
        x1, y1: Coordinates of first point
        x2, y2: Coordinates of second point

    Returns:
        Angle in radians
    """
    return math.atan2(y2 - y1, x2 - x1)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between two values.

    Args:
        a: Start value
        b: End value
        t: Interpolation factor (typically 0-1)

    Returns:
        Interpolated value: a + (b - a) * t
    """
    return a + (b - a) * t


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value to range [min_val, max_val].

    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


@lru_cache(maxsize=512)
def fast_magnitude(x: float, y: float) -> float:
    """Calculate vector magnitude (length).

    Cached version of sqrt(x² + y²).

    Args:
        x, y: Vector components

    Returns:
        Vector magnitude
    """
    return math.sqrt(x * x + y * y)


@lru_cache(maxsize=512)
def fast_normalize(x: float, y: float) -> tuple[float, float]:
    """Normalize a 2D vector to unit length.

    Args:
        x, y: Vector components

    Returns:
        Tuple of (normalized_x, normalized_y), or (0, 0) if zero vector
    """
    mag = fast_magnitude(x, y)
    # Use epsilon for floating-point comparison
    if mag < 1e-10:
        return (0.0, 0.0)
    return (x / mag, y / mag)


def dot_product(x1: float, y1: float, x2: float, y2: float) -> float:
    """Calculate dot product of two 2D vectors.

    Args:
        x1, y1: First vector components
        x2, y2: Second vector components

    Returns:
        Dot product: x1*x2 + y1*y2
    """
    return x1 * x2 + y1 * y2


__all__ = [
    "angle_between_points",
    "clamp",
    "distance",
    "distance_squared",
    "dot_product",
    "fast_magnitude",
    "fast_normalize",
    "lerp",
    "normalize_angle",
]

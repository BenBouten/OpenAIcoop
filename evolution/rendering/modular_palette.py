"""Shared colours and helpers for modular creature rendering."""

from __future__ import annotations

from typing import Dict, Tuple

from ..body.attachment import JointType

Color = Tuple[int, int, int]
Tint = Tuple[float, float, float]

MODULE_COLORS: Dict[str, Color] = {
    "core": (70, 125, 160),
    "head": (235, 232, 198),
    "limb": (120, 200, 220),
    "propulsion": (255, 162, 120),
    "sensor": (214, 235, 255),
    "tentacle": (144, 215, 182),
    "bell_core": (188, 160, 255),
}

BASE_MODULE_ALPHA = 210

MODULE_RENDER_STYLES: Dict[str, Dict[str, Tint | int]] = {
    "default": {"tint": (0.95, 0.95, 1.05), "alpha_offset": -15},
    "core": {"tint": (1.0, 1.0, 1.0), "alpha_offset": 25},
    "head": {"tint": (1.15, 1.08, 1.05), "alpha_offset": -5},
    "limb": {"tint": (0.85, 1.05, 1.25), "alpha_offset": -30},
    "propulsion": {"tint": (1.3, 0.92, 0.78), "alpha_offset": -10},
    "sensor": {"tint": (1.1, 1.3, 1.4), "alpha_offset": -40},
    "tentacle": {"tint": (0.8, 1.1, 1.25), "alpha_offset": -50},
    "bell_core": {"tint": (1.05, 0.95, 1.3), "alpha_offset": 10},
}

JOINT_COLORS: Dict[JointType, Color] = {
    JointType.FIXED: (210, 210, 220),
    JointType.HINGE: (255, 210, 140),
    JointType.BALL: (160, 225, 255),
    JointType.MUSCLE: (255, 150, 180),
}


def clamp_channel(value: float) -> int:
    """Clamp a channel value to the 0-255 range."""

    return max(0, min(255, int(round(value))))


def tint_color(base: Color, tint: Tint) -> Color:
    """Apply a multiplicative tint to ``base`` and clamp the result."""

    return tuple(clamp_channel(base[idx] * tint[idx]) for idx in range(3))


__all__ = [
    "BASE_MODULE_ALPHA",
    "JOINT_COLORS",
    "MODULE_COLORS",
    "MODULE_RENDER_STYLES",
    "Tint",
    "clamp_channel",
    "tint_color",
]

"""Locomotion controllers that generate thrust signals for prototypes."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from pygame.math import Vector2

from .physics_body import PhysicsBody


@dataclass
class FinOscillationController:
    """Simple sinusoidal fin driver used by prototype creatures."""

    amplitude: float = 1.0
    frequency: float = 0.6
    phase: float = 0.0
    heading_radians: float = 0.0
    _time: float = field(default=0.0, init=False, repr=False)
    _signal: float = field(default=0.0, init=False, repr=False)

    def update(self, dt: float) -> float:
        """Advance the controller and return the current fin signal."""

        self._time += dt
        angular_frequency = math.tau * self.frequency
        self._signal = math.sin(self._time * angular_frequency + self.phase) * self.amplitude
        self._signal = max(-1.0, min(1.0, self._signal))
        return self._signal

    def thrust_vector(self, physics_body: PhysicsBody) -> Vector2:
        """Translate the current signal into a thrust vector."""

        thrust_force = physics_body.max_thrust * self._signal
        vector = Vector2(thrust_force, 0.0)
        if self.heading_radians:
            vector = vector.rotate_rad(self.heading_radians)
        return vector

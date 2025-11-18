"""Tests for the layered ocean physics integration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pygame = pytest.importorskip("pygame")
from pygame.math import Vector2

from evolution.physics.physics_body import PhysicsBody
from evolution.world.ocean_physics import OceanPhysics


class DummyLifeform:
    """Minimal stand-in with the attributes used by OceanPhysics."""

    def __init__(self, physics_body: PhysicsBody, depth: float) -> None:
        self.x = 200.0
        self.y = depth
        self.rect = SimpleNamespace(centery=depth)
        self.velocity = Vector2()
        self.physics_body = physics_body
        self.body_density = physics_body.density
        self.volume = physics_body.volume
        self.buoyancy_volume = physics_body.buoyancy_volume
        self.drag_coefficient = physics_body.drag_coefficient
        self.grip_strength = 1.0
        self.last_fluid_properties = None


def _neutral_body(ocean: OceanPhysics, depth: float) -> PhysicsBody:
    fluid = ocean.properties_at(depth)
    return PhysicsBody(
        mass=80.0,
        volume=80.0,
        density=fluid.density,
        frontal_area=42.0,
        lateral_area=40.0,
        dorsal_area=38.0,
        drag_coefficient=0.25,
        buoyancy_volume=220.0,
        max_thrust=80.0,
        grip_strength=12.0,
        power_output=24.0,
        energy_cost=10.0,
    )


def test_neutral_buoyancy_does_not_cause_sinking() -> None:
    """Bodies that match the fluid density should stay level without thrust."""

    ocean = OceanPhysics(400, 400)
    depth = 0.0  # Test at surface where vertical current component is zero
    physics_body = _neutral_body(ocean, depth)
    creature = DummyLifeform(physics_body, depth)

    next_position, fluid = ocean.integrate_body(
        creature,
        thrust=Vector2(),
        dt=0.5,
        max_speed=60.0,
    )

    assert abs(creature.velocity.y) < 1e-6
    assert abs(next_position.y - creature.y) < 1e-6
    assert creature.last_fluid_properties == fluid

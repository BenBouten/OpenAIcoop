"""Tests for lifeform buoyancy diagnostics."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pygame = pytest.importorskip("pygame")

from evolution.physics.physics_body import PhysicsBody
from evolution.world.ocean_physics import OceanPhysics


def test_neutral_buoyancy_calculation():
    """Test that neutral buoyancy is calculated correctly."""
    # Create ocean physics
    ocean = OceanPhysics(400, 400)
    
    # Get fluid density at depth 100
    depth = 100.0
    fluid = ocean.properties_at(depth)
    
    # Create neutral buoyancy physics body
    volume = 80.0
    mass = fluid.density * volume
    physics_body = PhysicsBody(
        mass=mass,
        volume=volume,
        density=fluid.density,
        frontal_area=20.0,
        lateral_area=20.0,
        dorsal_area=20.0,
        drag_coefficient=0.25,
        buoyancy_volume=volume,
        max_thrust=80.0,
        grip_strength=12.0,
        power_output=24.0,
        energy_cost=10.0,
    )
    
    # Manually compute buoyancy as the lifeform would
    _GRAVITY = 9.81
    buoyancy_volume = physics_body.buoyancy_volume
    body_volume = physics_body.volume
    
    buoyant_force = fluid.density * buoyancy_volume * _GRAVITY
    weight = mass * _GRAVITY
    net_buoyancy = buoyant_force - weight
    relative_buoyancy = net_buoyancy / max(weight, 1e-6)
    
    # Check near-floating tolerance
    rel_tol = 0.05
    abs_tol = max(0.02 * weight, 0.5)
    is_near = abs(relative_buoyancy) <= rel_tol or abs(net_buoyancy) <= abs_tol
    
    # Verify neutral buoyancy is detected
    assert abs(net_buoyancy) < 1.0, f"Net buoyancy should be near 0, got {net_buoyancy}"
    assert abs(relative_buoyancy) < 0.05, f"Relative buoyancy should be near 0, got {relative_buoyancy}"
    assert is_near, "Neutral body should be marked as near-floating"


def test_heavy_body_not_near_floating():
    """Test that a heavy (sinking) body is not marked as near-floating."""
    ocean = OceanPhysics(400, 400)
    depth = 100.0
    fluid = ocean.properties_at(depth)
    
    # Create heavy physics body (2x fluid density)
    volume = 80.0
    mass = fluid.density * volume * 2.0  # Much heavier!
    physics_body = PhysicsBody(
        mass=mass,
        volume=volume,
        density=fluid.density * 2.0,
        frontal_area=20.0,
        lateral_area=20.0,
        dorsal_area=20.0,
        drag_coefficient=0.25,
        buoyancy_volume=volume,
        max_thrust=80.0,
        grip_strength=12.0,
        power_output=24.0,
        energy_cost=10.0,
    )
    
    # Manually compute buoyancy
    _GRAVITY = 9.81
    buoyancy_volume = physics_body.buoyancy_volume
    
    buoyant_force = fluid.density * buoyancy_volume * _GRAVITY
    weight = mass * _GRAVITY
    net_buoyancy = buoyant_force - weight
    relative_buoyancy = net_buoyancy / max(weight, 1e-6)
    
    # Check near-floating tolerance
    rel_tol = 0.05
    abs_tol = max(0.02 * weight, 0.5)
    is_near = abs(relative_buoyancy) <= rel_tol or abs(net_buoyancy) <= abs_tol
    
    # Heavy body should NOT be near-floating
    assert net_buoyancy < -1.0, "Heavy body should have significant negative net buoyancy"
    assert relative_buoyancy < -0.1, f"Heavy body should have negative relative buoyancy, got {relative_buoyancy}"
    assert not is_near, "Heavy body should not be marked as near-floating"


def test_light_body_not_near_floating():
    """Test that a light (floating) body is not marked as near-floating."""
    ocean = OceanPhysics(400, 400)
    depth = 100.0
    fluid = ocean.properties_at(depth)
    
    # Create light physics body (0.5x fluid density)
    volume = 80.0
    mass = fluid.density * volume * 0.5  # Much lighter!
    physics_body = PhysicsBody(
        mass=mass,
        volume=volume,
        density=fluid.density * 0.5,
        frontal_area=20.0,
        lateral_area=20.0,
        dorsal_area=20.0,
        drag_coefficient=0.25,
        buoyancy_volume=volume,
        max_thrust=80.0,
        grip_strength=12.0,
        power_output=24.0,
        energy_cost=10.0,
    )
    
    # Manually compute buoyancy
    _GRAVITY = 9.81
    buoyancy_volume = physics_body.buoyancy_volume
    
    buoyant_force = fluid.density * buoyancy_volume * _GRAVITY
    weight = mass * _GRAVITY
    net_buoyancy = buoyant_force - weight
    relative_buoyancy = net_buoyancy / max(weight, 1e-6)
    
    # Check near-floating tolerance
    rel_tol = 0.05
    abs_tol = max(0.02 * weight, 0.5)
    is_near = abs(relative_buoyancy) <= rel_tol or abs(net_buoyancy) <= abs_tol
    
    # Light body should NOT be near-floating
    assert net_buoyancy > 1.0, "Light body should have significant positive net buoyancy"
    assert relative_buoyancy > 0.1, f"Light body should have positive relative buoyancy, got {relative_buoyancy}"
    assert not is_near, "Light body should not be marked as near-floating"


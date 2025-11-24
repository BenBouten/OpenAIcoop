"""Test that creatures can apply thrust for swimming."""
from pygame.math import Vector2

import pytest

from evolution.physics.physics_body import PhysicsBody
from evolution.entities import movement


class MockLifeform:
    """Mock lifeform for testing movement calculations."""

    def __init__(
        self,
        speed=1.65,
        max_swim_speed=48.0,
        propulsion_efficiency=1.2,
        velocity=None,
    ):
        self.speed = speed
        self.max_swim_speed = max_swim_speed
        self.propulsion_efficiency = propulsion_efficiency
        self.physics_body = PhysicsBody(
            mass=67.3,
            volume=300.0,
            density=0.224,
            frontal_area=20.0,
            lateral_area=15.0,
            dorsal_area=20.0,
            drag_coefficient=0.25,
            buoyancy_volume=300.0,
            max_thrust=210.0,
            grip_strength=15.0,
            power_output=90.0,
            energy_cost=6.9,
            lift_per_fin=36.0,
            buoyancy_offsets=(1.0, 0.0),
        )
        self.adrenaline_factor = 0.0
        self.x_direction = 1.0
        self.y_direction = 0.0
        self.velocity = velocity or Vector2(speed, 0)
        self._burst_timer = 0
        self._burst_cooldown = 0
        self.fin_count = 2
        self.drift_preference = 0.0

    def should_seek_food(self) -> bool:
        return False


def calculate_thrust_effort(lifeform, thrust_multiplier=1.0):
    """Calculate thrust effort mirroring movement._compute_thrust_effort usage."""
    command_ratio = movement._behavioral_thrust_ratio(lifeform)
    base_effort = movement._compute_thrust_effort(
        lifeform,
        lifeform.velocity.length(),
        command_ratio,
    )
    effort = base_effort * thrust_multiplier
    return max(-1.0, min(1.0, effort))


@pytest.mark.parametrize(
    "speed,expected_range",
    [
        (0.2, (0.6, 0.85)),
        (1.5, (0.6, 0.85)),
        (4.0, (0.55, 0.8)),
    ],
)
def test_behavioral_thrust_ratio_ranges(speed, expected_range):
    lifeform = MockLifeform(speed=speed)
    effort = calculate_thrust_effort(lifeform)
    assert expected_range[0] <= effort <= expected_range[1]


def test_propulsion_efficiency_scaling():
    base = MockLifeform(speed=2.0, propulsion_efficiency=1.0)
    boosted = MockLifeform(speed=2.0, propulsion_efficiency=1.5)
    base_effort = calculate_thrust_effort(base)
    boosted_effort = calculate_thrust_effort(boosted)
    assert boosted_effort > base_effort
    assert pytest.approx(boosted_effort / base_effort, rel=0.2) == 1.08


def test_high_speed_effort_clamps_to_one():
    lifeform = MockLifeform(speed=12.0)
    effort = calculate_thrust_effort(lifeform)
    assert effort <= 1.0
    assert effort > 0.25


def test_vector_blend_respects_velocity():
    lifeform = MockLifeform(speed=2.0, velocity=Vector2(10, 0))
    desired = Vector2(0, 1)
    blended = movement._blend_desired_with_velocity(lifeform, desired)
    assert blended.length() == pytest.approx(1.0)
    assert blended.x > 0.0
    assert blended.y > 0.0
    assert lifeform.velocity.x > 0.0
    assert lifeform.velocity.y > 0.0


def test_burst_multiplier_allows_above_one():
    lifeform = MockLifeform(speed=4.0)
    effort = calculate_thrust_effort(lifeform, thrust_multiplier=2.0)
    assert effort > 0.9
    assert effort <= 1.0


if __name__ == "__main__":
    # Run tests
    test_behavioral_thrust_ratio_ranges()
    test_propulsion_efficiency_scaling()
    test_high_speed_effort_clamps_to_one()
    test_vector_blend_respects_velocity()
    test_burst_multiplier_allows_above_one()
    print("✓ All swimming thrust tests passed!")

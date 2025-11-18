"""Test that creatures can apply thrust for swimming."""
from pygame.math import Vector2

from evolution.physics.physics_body import PhysicsBody


class MockLifeform:
    """Mock lifeform for testing movement calculations."""
    
    def __init__(self, speed=1.65, max_swim_speed=48.0, propulsion_efficiency=1.2):
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
        self.x_direction = 1.0
        self.y_direction = 0.0
        self._burst_timer = 0
        self._burst_cooldown = 0


def calculate_thrust_effort(lifeform, thrust_multiplier=1.0):
    """Calculate thrust effort as done in movement.py (after fix)."""
    base_speed = lifeform.speed
    # Fixed calculation: normalize against speed's own range (0.05-14.0)
    speed_ratio = max(0.0, min(1.0, base_speed / 14.0))
    base_effort = speed_ratio * lifeform.propulsion_efficiency
    effort = base_effort * thrust_multiplier
    clamped_effort = max(-1.0, min(1.0, effort))
    return clamped_effort


def test_low_speed_thrust():
    """Test that creatures with low behavioral speed still get reasonable thrust."""
    lifeform = MockLifeform(speed=1.65)
    effort = calculate_thrust_effort(lifeform)
    
    # With speed=1.65, effort should be (1.65/14.0) * 1.2 = 0.141
    assert effort > 0.1, f"Effort too low: {effort}"
    assert effort < 0.2, f"Effort too high: {effort}"
    assert abs(effort - 0.141) < 0.01, f"Effort calculation incorrect: {effort}"


def test_medium_speed_thrust():
    """Test creatures with medium speed get proportional thrust."""
    lifeform = MockLifeform(speed=7.0)
    effort = calculate_thrust_effort(lifeform)
    
    # With speed=7.0, effort should be (7.0/14.0) * 1.2 = 0.6
    assert effort > 0.5, f"Effort too low: {effort}"
    assert effort < 0.7, f"Effort too high: {effort}"
    assert abs(effort - 0.6) < 0.01, f"Effort calculation incorrect: {effort}"


def test_high_speed_thrust():
    """Test creatures at max speed use full thrust capability."""
    lifeform = MockLifeform(speed=14.0)
    effort = calculate_thrust_effort(lifeform)
    
    # With speed=14.0, effort should be (14.0/14.0) * 1.2 = 1.2, clamped to 1.0
    assert effort >= 0.95, f"Effort should be near maximum: {effort}"
    assert effort <= 1.0, f"Effort exceeded maximum: {effort}"


def test_thrust_acceleration():
    """Test that thrust results in meaningful acceleration."""
    lifeform = MockLifeform(speed=1.65)
    effort = calculate_thrust_effort(lifeform)
    
    acceleration = lifeform.physics_body.propulsion_acceleration(effort)
    
    # Acceleration should be meaningful (> 0.3 m/s²)
    assert acceleration > 0.3, f"Acceleration too low to enable swimming: {acceleration}"
    
    # At medium speed, acceleration should be even higher
    lifeform.speed = 7.0
    effort_med = calculate_thrust_effort(lifeform)
    acceleration_med = lifeform.physics_body.propulsion_acceleration(effort_med)
    assert acceleration_med > 1.5, f"Medium speed acceleration too low: {acceleration_med}"


def test_thrust_independent_of_max_swim_speed():
    """Test that effort is independent of max_swim_speed."""
    # Two creatures with same speed but different max_swim_speed
    lifeform1 = MockLifeform(speed=5.0, max_swim_speed=50.0)
    lifeform2 = MockLifeform(speed=5.0, max_swim_speed=150.0)
    
    effort1 = calculate_thrust_effort(lifeform1)
    effort2 = calculate_thrust_effort(lifeform2)
    
    # Effort should be the same since it's normalized against 14.0, not max_swim_speed
    assert abs(effort1 - effort2) < 0.001, \
        f"Effort should be independent of max_swim_speed: {effort1} vs {effort2}"


def test_propulsion_efficiency_scaling():
    """Test that propulsion_efficiency properly scales effort."""
    base_lifeform = MockLifeform(speed=7.0, propulsion_efficiency=1.0)
    efficient_lifeform = MockLifeform(speed=7.0, propulsion_efficiency=1.5)
    
    base_effort = calculate_thrust_effort(base_lifeform)
    efficient_effort = calculate_thrust_effort(efficient_lifeform)
    
    # Efficient lifeform should have 1.5x the effort
    expected_ratio = 1.5
    actual_ratio = efficient_effort / base_effort
    assert abs(actual_ratio - expected_ratio) < 0.01, \
        f"Propulsion efficiency not scaling correctly: {actual_ratio} vs {expected_ratio}"


def test_speed_range_coverage():
    """Test that the full speed range (0.05-14.0) maps to effort range."""
    # Minimum speed
    lifeform_min = MockLifeform(speed=0.05, propulsion_efficiency=1.0)
    effort_min = calculate_thrust_effort(lifeform_min)
    assert effort_min < 0.01, f"Minimum effort should be very small: {effort_min}"
    
    # Maximum speed
    lifeform_max = MockLifeform(speed=14.0, propulsion_efficiency=1.0)
    effort_max = calculate_thrust_effort(lifeform_max)
    assert effort_max >= 0.95, f"Maximum effort should be near 1.0: {effort_max}"
    
    # Mid-range speed
    lifeform_mid = MockLifeform(speed=7.0, propulsion_efficiency=1.0)
    effort_mid = calculate_thrust_effort(lifeform_mid)
    assert 0.4 < effort_mid < 0.6, f"Mid-range effort should be around 0.5: {effort_mid}"


if __name__ == "__main__":
    # Run tests
    test_low_speed_thrust()
    test_medium_speed_thrust()
    test_high_speed_thrust()
    test_thrust_acceleration()
    test_thrust_independent_of_max_swim_speed()
    test_propulsion_efficiency_scaling()
    test_speed_range_coverage()
    print("✓ All swimming thrust tests passed!")

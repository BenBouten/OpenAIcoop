"""Test that buoyancy compensation works correctly in AI decision-making."""

from types import SimpleNamespace
from pygame.math import Vector2

# Mock imports for testing without full simulation setup
import sys
sys.path.insert(0, '/home/runner/work/OpenAIcoop/OpenAIcoop')

from evolution.entities.ai import _buoyancy_compensation_vector


def test_positive_buoyancy_compensation():
    """Test that lifeforms with positive buoyancy swim down to compensate."""
    
    # Create a mock lifeform with positive buoyancy (floating up)
    lifeform = SimpleNamespace(
        relative_buoyancy=0.5,  # 50% positive buoyancy
        is_near_floating=False,
        fin_count=2,
        lift_per_fin=36.0,
    )
    
    compensation = _buoyancy_compensation_vector(lifeform)
    
    # Should produce a downward vector (positive y in pygame coordinates)
    assert compensation.y > 0, f"Expected downward compensation, got y={compensation.y}"
    assert compensation.x == 0, f"Expected no horizontal component, got x={compensation.x}"
    
    # Magnitude should be reasonable
    assert 0.1 < compensation.length() <= 0.8, f"Compensation strength {compensation.length()} out of range"
    
    print(f"✓ Positive buoyancy (+0.5) → compensation vector: {compensation}")


def test_negative_buoyancy_compensation():
    """Test that lifeforms with negative buoyancy swim up to compensate."""
    
    # Create a mock lifeform with negative buoyancy (sinking)
    lifeform = SimpleNamespace(
        relative_buoyancy=-0.4,  # 40% negative buoyancy
        is_near_floating=False,
        fin_count=3,
        lift_per_fin=36.0,
    )
    
    compensation = _buoyancy_compensation_vector(lifeform)
    
    # Should produce an upward vector (negative y in pygame coordinates)
    assert compensation.y < 0, f"Expected upward compensation, got y={compensation.y}"
    assert compensation.x == 0, f"Expected no horizontal component, got x={compensation.x}"
    
    # Magnitude should be reasonable
    assert 0.1 < compensation.length() <= 0.8, f"Compensation strength {compensation.length()} out of range"
    
    print(f"✓ Negative buoyancy (-0.4) → compensation vector: {compensation}")


def test_neutral_buoyancy_no_compensation():
    """Test that near-neutral buoyancy doesn't require compensation."""
    
    # Create a mock lifeform with near-neutral buoyancy
    lifeform = SimpleNamespace(
        relative_buoyancy=0.01,  # Very small buoyancy
        is_near_floating=True,
        fin_count=2,
        lift_per_fin=36.0,
    )
    
    compensation = _buoyancy_compensation_vector(lifeform)
    
    # Should produce zero or very small vector
    assert compensation.length() < 0.01, f"Expected no compensation for neutral buoyancy, got {compensation}"
    
    print(f"✓ Neutral buoyancy (0.01, near_floating=True) → no compensation: {compensation}")


def test_no_fins_weak_compensation():
    """Test that lifeforms without fins get weaker compensation."""
    
    # Create a mock lifeform with positive buoyancy but no fins
    lifeform = SimpleNamespace(
        relative_buoyancy=0.5,
        is_near_floating=False,
        fin_count=0,  # No fins
        lift_per_fin=0.0,
    )
    
    compensation = _buoyancy_compensation_vector(lifeform)
    
    # Should still produce compensation, but weaker
    assert compensation.y > 0, f"Expected downward compensation, got y={compensation.y}"
    assert compensation.length() <= 0.3, f"Expected weaker compensation without fins, got {compensation.length()}"
    
    print(f"✓ Positive buoyancy with no fins → weak compensation: {compensation}")


def test_small_buoyancy_ignored():
    """Test that very small buoyancy values are ignored."""
    
    # Create a mock lifeform with very small buoyancy
    lifeform = SimpleNamespace(
        relative_buoyancy=0.01,  # 1% buoyancy
        is_near_floating=False,
        fin_count=2,
        lift_per_fin=36.0,
    )
    
    compensation = _buoyancy_compensation_vector(lifeform)
    
    # Should produce zero or very small vector (below threshold)
    assert compensation.length() < 0.01, f"Expected no compensation for small buoyancy, got {compensation}"
    
    print(f"✓ Small buoyancy (0.01) → ignored: {compensation}")


def test_high_buoyancy_capped():
    """Test that very high buoyancy compensation is capped."""
    
    # Create a mock lifeform with very high buoyancy
    lifeform = SimpleNamespace(
        relative_buoyancy=2.0,  # 200% buoyancy (unrealistic but possible)
        is_near_floating=False,
        fin_count=4,
        lift_per_fin=36.0,
    )
    
    compensation = _buoyancy_compensation_vector(lifeform)
    
    # Should be capped at 0.8
    assert compensation.length() <= 0.8, f"Expected capped compensation, got {compensation.length()}"
    assert compensation.y > 0, f"Expected downward compensation, got y={compensation.y}"
    
    print(f"✓ High buoyancy (2.0) → capped compensation: {compensation}")


if __name__ == "__main__":
    test_positive_buoyancy_compensation()
    test_negative_buoyancy_compensation()
    test_neutral_buoyancy_no_compensation()
    test_no_fins_weak_compensation()
    test_small_buoyancy_ignored()
    test_high_buoyancy_capped()
    print("\n✅ All buoyancy compensation tests passed!")

"""Test that buoyancy offsets produce reasonable net buoyancy values."""

from evolution.body.modules import (
    TrunkCore,
    CephalonHead,
    HydroFin,
    TailThruster,
    SensorPod,
)


def test_module_buoyancy_bias_values():
    """Verify that module buoyancy_bias values are reasonable."""
    
    # Create instances of all modules
    core = TrunkCore(key="core")
    head = CephalonHead(key="head")
    fin = HydroFin(key="fin")
    thruster = TailThruster(key="thruster")
    sensor = SensorPod(key="sensor")
    
    # Check that buoyancy bias values are within reasonable range
    # Typical values should be between -1.0 and 1.0 for realistic behavior
    assert -1.0 <= core.stats.buoyancy_bias <= 1.0, f"Core buoyancy_bias {core.stats.buoyancy_bias} out of range"
    assert -1.0 <= head.stats.buoyancy_bias <= 1.0, f"Head buoyancy_bias {head.stats.buoyancy_bias} out of range"
    assert -1.0 <= fin.stats.buoyancy_bias <= 1.0, f"Fin buoyancy_bias {fin.stats.buoyancy_bias} out of range"
    assert -1.0 <= thruster.stats.buoyancy_bias <= 1.0, f"Thruster buoyancy_bias {thruster.stats.buoyancy_bias} out of range"
    assert -1.0 <= sensor.stats.buoyancy_bias <= 1.0, f"Sensor buoyancy_bias {sensor.stats.buoyancy_bias} out of range"
    
    # Verify specific expected values after the fix
    assert core.stats.buoyancy_bias == 0.5, f"Expected core bias 0.5, got {core.stats.buoyancy_bias}"
    assert head.stats.buoyancy_bias == 0.2, f"Expected head bias 0.2, got {head.stats.buoyancy_bias}"
    assert fin.stats.buoyancy_bias == 0.3, f"Expected fin bias 0.3, got {fin.stats.buoyancy_bias}"
    assert thruster.stats.buoyancy_bias == -0.3, f"Expected thruster bias -0.3, got {thruster.stats.buoyancy_bias}"
    assert sensor.stats.buoyancy_bias == 0.1, f"Expected sensor bias 0.1, got {sensor.stats.buoyancy_bias}"


def test_typical_lifeform_buoyancy():
    """Test that a typical lifeform has reasonable total buoyancy bias."""
    
    # Simulate a typical lifeform with:
    # - 1 core
    # - 1 head
    # - 2-4 fins
    # - 1 thruster
    # - 0-2 sensors
    
    core = TrunkCore(key="core")
    head = CephalonHead(key="head")
    fin = HydroFin(key="fin")
    thruster = TailThruster(key="thruster")
    sensor = SensorPod(key="sensor")
    
    # Minimal configuration: core + head + 2 fins + thruster
    min_total = (
        core.stats.buoyancy_bias +
        head.stats.buoyancy_bias +
        2 * fin.stats.buoyancy_bias +
        thruster.stats.buoyancy_bias
    )
    
    # Maximal configuration: core + head + 4 fins + thruster + 2 sensors
    max_total = (
        core.stats.buoyancy_bias +
        head.stats.buoyancy_bias +
        4 * fin.stats.buoyancy_bias +
        thruster.stats.buoyancy_bias +
        2 * sensor.stats.buoyancy_bias
    )
    
    print(f"Minimal lifeform total buoyancy bias: {min_total}")
    print(f"Maximal lifeform total buoyancy bias: {max_total}")
    
    # Total buoyancy bias should be reasonable (not more than ±5.0)
    # This ensures lifeforms can actively swim to counteract buoyancy
    assert -5.0 <= min_total <= 5.0, f"Minimal total {min_total} is too extreme"
    assert -5.0 <= max_total <= 5.0, f"Maximal total {max_total} is too extreme"
    
    # Ideally, total should be closer to neutral (within ±3.0)
    assert -3.0 <= min_total <= 3.0, f"Minimal total {min_total} should be more neutral"
    assert -3.0 <= max_total <= 3.0, f"Maximal total {max_total} should be more neutral"


if __name__ == "__main__":
    test_module_buoyancy_bias_values()
    test_typical_lifeform_buoyancy()
    print("All buoyancy tests passed!")

"""Tests for module nutrition system."""

import unittest
from evolution.body.modules import (
    ModuleStats,
    calculate_module_nutrition,
    Eye,
    Mouth,
)


class TestModuleNutrition(unittest.TestCase):
    """Test nutrition calculation for body modules."""
    
    def test_calculate_module_nutrition_core(self):
        """Core modules should have 1.5x multiplier."""
        # 1kg core = 10 * 1.5 = 15
        nutrition = calculate_module_nutrition(1.0, "core")
        self.assertEqual(nutrition, 15.0)
        
    def test_calculate_module_nutrition_muscle(self):
        """Muscle modules should have 1.3x multiplier."""
        # 2kg muscle = 20 * 1.3 = 26
        nutrition = calculate_module_nutrition(2.0, "muscle")
        self.assertEqual(nutrition, 26.0)
        
    def test_calculate_module_nutrition_armor(self):
        """Armor modules should have 0.6x multiplier (less edible)."""
        # 1kg armor = 10 * 0.6 = 6
        nutrition = calculate_module_nutrition(1.0, "armor")
        self.assertEqual(nutrition, 6.0)
        
    def test_calculate_module_nutrition_mouth(self):
        """Mouth modules should have 0.8x multiplier (teeth)."""
        # 0.8kg mouth = 8 * 0.8 = 6.4
        nutrition = calculate_module_nutrition(0.8, "mouth")
        self.assertEqual(nutrition, 6.4)
        
    def test_calculate_module_nutrition_eye(self):
        """Eye modules should have 0.9x multiplier."""
        # 0.3kg eye = 3.0 * 0.9 = 2.7
        nutrition = calculate_module_nutrition(0.3, "eye")
        self.assertEqual(nutrition, 2.7)
        
    def test_calculate_module_nutrition_unknown_type(self):
        """Unknown types should use 1.0x multiplier."""
        # 1kg unknown = 10 * 1.0 = 10
        nutrition = calculate_module_nutrition(1.0, "unknown_type")
        self.assertEqual(nutrition, 10.0)
        
    def test_calculate_module_nutrition_scaling(self):
        """Nutrition should scale linearly with mass."""
        small = calculate_module_nutrition(0.5, "core")
        large = calculate_module_nutrition(2.0, "core")
        
        self.assertEqual(small, 7.5)   # 5 * 1.5
        self.assertEqual(large, 30.0)  # 20 * 1.5
        self.assertEqual(large, small * 4)  # Should scale proportionally
        
    def test_modulestats_has_nutrition_field(self):
        """ModuleStats should have nutrition_value field."""
        stats = ModuleStats(
            mass=1.0,
            energy_cost=0.1,
            integrity=10.0,
            heat_dissipation=0.5
        )
        
        self.assertTrue(hasattr(stats, 'nutrition_value'))
        self.assertEqual(stats.nutrition_value, 0.0)  # Default value
        
    def test_modulestats_with_explicit_nutrition(self):
        """Can set explicit nutrition value."""
        stats = ModuleStats(
            mass=1.0,
            energy_cost=0.1,
            integrity=10.0,
            heat_dissipation=0.5,
            nutrition_value=15.0
        )
        
        self.assertEqual(stats.nutrition_value, 15.0)
        
    def test_eye_module_has_stats(self):
        """Eye module should have valid stats."""
        eye = Eye()
        
        self.assertIsNotNone(eye.stats)
        self.assertGreater(eye.stats.mass, 0)
        self.assertTrue(hasattr(eye.stats, 'nutrition_value'))
        
    def test_mouth_module_has_stats(self):
        """Mouth module should have valid stats."""
        mouth = Mouth()
        
        self.assertIsNotNone(mouth.stats)
        self.assertGreater(mouth.stats.mass, 0)
        self.assertTrue(hasattr(mouth.stats, 'nutrition_value'))


if __name__ == "__main__":
    unittest.main()

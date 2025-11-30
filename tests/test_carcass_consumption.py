import unittest
from unittest.mock import MagicMock
from evolution.world.advanced_carcass import DecomposingCarcass
from evolution.body.modules import TrunkCore, HydroFin, ModuleStats

class TestCarcassConsumption(unittest.TestCase):
    def setUp(self):
        # Create modules with specific nutrition
        self.core = TrunkCore()
        self.core.key = "core_1"
        # Replace stats with new object containing nutrition_value
        self.core.stats = ModuleStats(
            mass=self.core.stats.mass,
            energy_cost=self.core.stats.energy_cost,
            integrity=self.core.stats.integrity,
            heat_dissipation=self.core.stats.heat_dissipation,
            nutrition_value=15.0
        )
        
        self.fin = HydroFin()
        self.fin.key = "fin_1"
        self.fin.stats = ModuleStats(
            mass=self.fin.stats.mass,
            energy_cost=self.fin.stats.energy_cost,
            integrity=self.fin.stats.integrity,
            heat_dissipation=self.fin.stats.heat_dissipation,
            nutrition_value=26.0
        )
        
        # Mock BodyGraph
        self.mock_graph = MagicMock()
        self.mock_graph.get_node.side_effect = self.get_node_mock
        
        self.carcass = DecomposingCarcass(
            position=(100, 100),
            size=(50, 50),
            mass=10.0,
            nutrition=100.0,
            color=(255, 0, 0),
            body_graph=self.mock_graph
        )
        
    def get_node_mock(self, node_id):
        mock_node = MagicMock()
        if node_id == "core_1":
            mock_node.module = self.core
            return mock_node
        if node_id == "fin_1":
            mock_node.module = self.fin
            return mock_node
        # Raise KeyError for unknown nodes, as BodyGraph does
        raise KeyError(node_id)

    def test_consume_module_success(self):
        """Test consuming a valid module returns its nutrition."""
        # This method doesn't exist yet, so we expect this to fail if we ran it now
        # But we are writing the test first.
        nutrition = self.carcass.consume_module("core_1")
        self.assertEqual(nutrition, 15.0)
        self.assertIn("core_1", self.carcass.consumed_modules)

    def test_consume_already_eaten_module(self):
        """Test consuming an already eaten module returns 0."""
        self.carcass.consume_module("core_1")
        nutrition = self.carcass.consume_module("core_1")
        self.assertEqual(nutrition, 0.0)

    def test_consume_module_updates_decomposition(self):
        """Eating a module should accelerate decomposition."""
        initial_progress = self.carcass.decomposition_progress
        self.carcass.consume_module("fin_1")
        self.assertGreater(self.carcass.decomposition_progress, initial_progress)

    def test_consume_nonexistent_module(self):
        """Consuming a module not in the body should return 0."""
        nutrition = self.carcass.consume_module("nonexistent")
        self.assertEqual(nutrition, 0.0)

if __name__ == '__main__':
    unittest.main()

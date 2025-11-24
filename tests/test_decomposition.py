"""Test script for decomposition and carcass behavior in simulation."""

import unittest
import pygame
from evolution.simulation.state import SimulationState
from evolution.world.world import World
from evolution.entities.lifeform import Lifeform
from evolution.dna.blueprints import generate_modular_blueprint
from evolution.world.advanced_carcass import DecomposingCarcass as SinkingCarcass


class TestDecompositionSystem(unittest.TestCase):
    """Test carcass decomposition stages and physics."""
    
    def setUp(self):
        """Set up test environment."""
        pygame.init()
        pygame.display.set_mode((100, 100), pygame.HIDDEN)
        
        self.state = SimulationState()
        self.world = World(1000, 1000)  # Only width and height
        self.state.world = self.world
        
    def tearDown(self):
        """Clean up after tests."""
        pygame.quit()
        
    def test_carcass_creation(self):
        """Test that carcasses are created correctly."""
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
        )
        
        self.assertIsNotNone(carcass)
        self.assertEqual(carcass.resource, 100.0)
        self.assertGreater(carcass.width, 0)
        self.assertGreater(carcass.height, 0)

    def test_body_preservation(self):
        """Test that body graph is preserved in carcass."""
        # Create a dummy body graph
        body_graph = {"dummy": "graph"}
        body_geometry = {"dummy": "geometry"}
        
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
            body_graph=body_graph,
            body_geometry=body_geometry
        )
        
        self.assertEqual(carcass.body_graph, body_graph)
        self.assertEqual(carcass.body_geometry, body_geometry)
        
    def test_creature_death_creates_carcass(self):
        """Test that dying creatures create carcasses."""
        # Create a creature
        dna = generate_modular_blueprint("herbivore", base_form="streamliner")
        dna.update({
            "dna_id": 1,
            "base_form": "streamliner",
            "base_form_label": "Streamliner",
            "width": 80, "height": 30,
            "color": (100, 200, 100),
            "health": 50, "maturity": 100,
            "vision": 100, "defence_power": 10, "attack_power": 5,
            "energy": 100, "longevity": 1000,
            "diet": "herbivore",
            "social": 0.5, "boid_tendency": 0.5, 
            "risk_tolerance": 0.5, "restlessness": 0.5,
            "morphology": {}, "development": {},
        })
        
        creature = Lifeform(self.state, 500, 500, dna, 1)
        
        # Kill the creature
        creature.health_now = 0
        
        # Handle death
        initial_carcass_count = len(self.state.carcasses)
        died = creature.handle_death()
        
        self.assertTrue(died)
        self.assertEqual(len(self.state.carcasses), initial_carcass_count + 1)
        
        # Check the carcass
        carcass = self.state.carcasses[-1]
        self.assertGreater(carcass.resource, 0)
        self.assertEqual(carcass.x, 500)
        self.assertEqual(carcass.y, 500)
        
    def test_carcass_decomp_progress(self):
        """Test that carcasses decompose over time."""
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
        )
        
        initial_resource = carcass.resource
        
        # Simulate 10 seconds of decomposition
        for _ in range(100):
            carcass.update(self.world, 0.1)
        
        # Resource should have decreased
        self.assertLess(carcass.resource, initial_resource)
        
    def test_carcass_consumption(self):
        """Test that creatures can eat carcasses."""
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
        )
        
        initial_resource = carcass.resource
        consumed = carcass.consume(10.0)
        
        self.assertEqual(consumed, 10.0)
        self.assertEqual(carcass.resource, initial_resource - 10.0)
        
    def test_carcass_depletion(self):
        """Test that carcasses are marked as depleted when empty."""
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=5.0,  # Small nutrition
            color=(200, 100, 50),
        )
        
        self.assertFalse(carcass.is_depleted())
        
        # Consume all
        carcass.consume(10.0)
        
        self.assertTrue(carcass.is_depleted())
        
    def test_carcass_physics(self):
        """Test that fresh carcasses sink slowly."""
        carcass = SinkingCarcass(
            position=(500, 100),  # Start high
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
        )
        
        initial_y = carcass.y
        
        # Update physics for a few frames
        for _ in range(10):
            carcass.update(self.world, 0.1)
        
        # Should have sunk (y increased)
        self.assertGreater(carcass.y, initial_y)
        
    def test_buoyancy_stages(self):
        """Test that buoyancy changes with decomposition stages."""
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
        )
        
        # Force BLOATED stage
        carcass.decomposition_progress = 0.3
        carcass._update_decomposition_stage()
        carcass.body_density = carcass._calculate_dynamic_density()
        
        # Should be lighter than water (1.0)
        self.assertLess(carcass.body_density, 1.0)
        
        # Update physics
        initial_y = carcass.y
        for _ in range(10):
            carcass.update(self.world, 0.1)
            
        # Should float up (y decreases)
        self.assertLess(carcass.y, initial_y)
        
    def test_simultaneous_carcasses(self):
        """Test multiple carcasses in simulation."""
        carcass1 = SinkingCarcass(
            position=(300, 300),
            size=(40, 25),
            mass=1.5,
            nutrition=80.0,
            color=(200, 100, 50),
        )
        
        carcass2 = SinkingCarcass(
            position=(700, 300),
            size=(60, 35),
            mass=2.5,
            nutrition=120.0,
            color=(150, 150, 50),
        )
        
        self.state.carcasses = [carcass1, carcass2]
        
        # Update both
        for _ in range(50):
            for carcass in self.state.carcasses:
                carcass.update(self.world, 0.1)
        
        # Both should have decomposed
        self.assertLess(carcass1.resource, 80.0)
        self.assertLess(carcass2.resource, 120.0)


    def test_carcass_drawing(self):
        """Test that carcass drawing works without error."""
        carcass = SinkingCarcass(
            position=(500, 500),
            size=(50, 30),
            mass=2.0,
            nutrition=100.0,
            color=(200, 100, 50),
        )
        
        surface = pygame.Surface((1000, 1000))
        try:
            carcass.draw(surface)
        except Exception as e:
            self.fail(f"Drawing failed with error: {e}")

if __name__ == "__main__":
    unittest.main()

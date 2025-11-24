'['
import unittest
import pygame
import random
from evolution.simulation.state import SimulationState
from evolution.world.world import World
from evolution.entities.lifeform import Lifeform
from evolution.dna.genes import ensure_genome
from evolution.dna.blueprints import generate_modular_blueprint
from evolution.entities.combat import resolve_close_interactions
from evolution.entities.ai import update_brain
from evolution.entities.movement import update_movement

class TestHuntingBehavior(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((100, 100), pygame.HIDDEN)
        self.state = SimulationState()
        self.world = World(1000, 1000)
        self.state.world = self.world
        
        # Create Predator Genome (Carnivore)
        pred_genome_data = generate_modular_blueprint("carnivore", base_form="streamliner")
        pred_profile = {
            "dna_id": 1,
            "base_form": "streamliner",
            "base_form_label": "Streamliner",
            "width": 100, "height": 40,
            "color": (255, 50, 50),
            "health": 100, "maturity": 100,
            "vision": 200, "defence_power": 20, "attack_power": 50,
            "energy": 100, "longevity": 1000,
            "diet": "carnivore",
            "social": 0.1, "boid_tendency": 0.1, "risk_tolerance": 0.9, "restlessness": 0.8,
            "morphology": {}, "development": {},
            "genome": pred_genome_data,
        }
        
        # Create Prey Genome (Herbivore)
        prey_genome_data = generate_modular_blueprint("herbivore", base_form="streamliner")
        prey_profile = {
            "dna_id": 2,
            "base_form": "streamliner",
            "base_form_label": "Streamliner",
            "width": 80, "height": 30,
            "color": (50, 255, 50),
            "health": 50, "maturity": 100,
            "vision": 100, "defence_power": 10, "attack_power": 5,
            "energy": 100, "longevity": 1000,
            "diet": "herbivore",
            "social": 0.8, "boid_tendency": 0.8, "risk_tolerance": 0.2, "restlessness": 0.4,
            "morphology": {}, "development": {},
            "genome": prey_genome_data,
        }

        self.predator = Lifeform(self.state, 500, 500, pred_profile, 1)
        self.predator.energy_now = 50 # Hungry
        self.predator.hunger = 80 # Very hungry
        
        self.prey = Lifeform(self.state, 520, 500, prey_profile, 1)
        
        self.state.lifeforms = [self.predator, self.prey]
        
        # Initialize stats
        self.predator._derive_stats_from_body()
        self.prey._derive_stats_from_body()
        
        # Ensure predator is stronger and has vision
        self.predator.attack_power = max(20.0, self.predator.attack_power)
        self.predator.vision = max(100.0, self.predator.vision)
        self.predator.calculate_attack_power()
        
        self.prey.defence_power = 5.0
        self.prey.attack_power = 1.0 # Nerf prey attack
        self.prey.calculate_defence_power()
        self.prey.calculate_attack_power()

    def test_target_detection(self):
        # Update targets
        self.predator.update_targets()
        self.prey.update_targets()
        
        print(f"Predator Vision: {self.predator.vision}")
        print(f"Distance to Prey: {self.predator.distance_to(self.prey)}")
        print(f"Predator Attack Now: {self.predator.attack_power_now}")
        print(f"Predator Defence Now: {self.predator.defence_power_now}")
        print(f"Prey Attack Now: {self.prey.attack_power_now}")
        print(f"Prey Defence Now: {self.prey.defence_power_now}")
        
        dx = self.prey.x - self.predator.x
        dy = self.prey.y - self.predator.y
        print(f"Delta: {dx}, {dy}")
        
        forward = pygame.math.Vector2(self.predator.x_direction, self.predator.y_direction)
        if forward.length_squared() == 0: forward = pygame.math.Vector2(1, 0)
        print(f"Forward: {forward}")
        
        self.assertIsNotNone(self.predator.closest_prey, "Predator should see prey")
        self.assertEqual(self.predator.closest_prey, self.prey)

    def test_hunting_behavior(self):
        self.predator.update_targets()
        update_brain(self.predator, self.state, 0.1)
        
        print(f"Behavior Mode: {self.predator.current_behavior_mode}")
        self.assertEqual(self.predator.current_behavior_mode, "hunt")
        
        # Check adrenaline
        update_movement(self.predator, self.state, 0.1)
        print(f"Adrenaline: {self.predator.adrenaline_factor}")
        self.assertGreater(self.predator.adrenaline_factor, 0.0)

    def test_combat_interaction(self):
        self.predator.update_targets()
        initial_health = self.prey.health_now
        
        # Force close distance
        self.prey.x = 505
        self.prey.y = 500
        self.predator.rect.center = (500, 500)
        self.prey.rect.center = (505, 500)
        
        resolve_close_interactions(self.predator)
        
        print(f"Prey Health: {initial_health} -> {self.prey.health_now}")
        self.assertLess(self.prey.health_now, initial_health, "Prey should take damage")

if __name__ == '__main__':
    unittest.main()

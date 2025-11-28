import unittest
import pygame

from evolution.simulation.state import SimulationState
from evolution.world.world import World
from evolution.entities.lifeform import Lifeform
from evolution.dna.blueprints import generate_modular_blueprint
from evolution.entities.combat import resolve_close_interactions
from evolution.entities.ai import update_brain


class TestNeuralBehaviors(unittest.TestCase):
    def setUp(self):
        pygame.init()
        pygame.display.set_mode((100, 100), pygame.HIDDEN)
        self.state = SimulationState()
        self.world = World(1000, 1000)
        self.state.world = self.world

        carnivore_genome = generate_modular_blueprint("carnivore", base_form="streamliner")
        herbivore_genome = generate_modular_blueprint("herbivore", base_form="streamliner")

        carnivore_profile = {
            "dna_id": 1,
            "base_form": "streamliner",
            "base_form_label": "Streamliner",
            "width": 100,
            "height": 40,
            "color": (255, 50, 50),
            "health": 100,
            "maturity": 100,
            "vision": 200,
            "defence_power": 20,
            "attack_power": 50,
            "energy": 120,
            "longevity": 1000,
            "diet": "carnivore",
            "genome": carnivore_genome,
        }

        herbivore_profile = {
            "dna_id": 2,
            "base_form": "streamliner",
            "base_form_label": "Streamliner",
            "width": 80,
            "height": 30,
            "color": (50, 255, 50),
            "health": 80,
            "maturity": 100,
            "vision": 120,
            "defence_power": 10,
            "attack_power": 5,
            "energy": 100,
            "longevity": 1000,
            "diet": "herbivore",
            "genome": herbivore_genome,
        }

        self.hunter = Lifeform(self.state, 500, 500, carnivore_profile, 1)
        self.hunter.energy_now = 50
        self.hunter.hunger = 80

        self.target = Lifeform(self.state, 520, 500, herbivore_profile, 1)
        self.state.lifeforms = [self.hunter, self.target]

    def test_target_detection_tracks_neighbors(self):
        self.hunter.update_targets()
        self.assertIs(self.hunter.closest_neighbor, self.target)
        self.assertIsNone(self.hunter.closest_prey)
        self.assertIsNone(self.hunter.closest_enemy)

    def test_neural_controller_outputs(self):
        update_brain(self.hunter, self.state, 0.1)
        self.assertEqual(self.hunter.current_behavior_mode, "neural")
        commands = getattr(self.hunter, "neural_commands", {})
        for key in ("tail_thrust", "left_fin_thrust", "right_fin_thrust", "vertical_thrust", "bite_intent"):
            self.assertIn(key, commands)

    def test_biomass_bite_draws_from_state(self):
        self.hunter.bite_force = 15.0
        self.hunter.attack_power_now = 10.0
        self.hunter.bite_intent = 1.0
        self.target.defence_power_now = 1.0

        self.target.x = 505
        self.target.y = 500
        self.hunter.rect.center = (500, 500)
        self.target.rect.center = (505, 500)

        starting_health = self.target.health_now
        resolve_close_interactions(self.hunter)
        self.assertLess(self.target.health_now, starting_health)


if __name__ == "__main__":
    unittest.main()


import sys
import os
import random
import pygame
from pygame.math import Vector2

# Use real settings
from evolution.config import settings
from evolution.entities.lifeform import Lifeform
from evolution.entities.neural_controller import NeuralController
from evolution.simulation.state import SimulationState
from evolution.simulation.base_population import base_templates

# Override settings for testing
settings.MIN_WIDTH = 10
settings.MIN_HEIGHT = 10
settings.BODY_PIXEL_SCALE = 10.0
settings.USE_BODYGRAPH_SIZE = True
settings.INITIAL_BASEFORM_COUNT = 1
settings.N_LIFEFORMS = 1
settings.MAX_LIFEFORMS = 10
settings.MUTATION_CHANCE = 0
settings.FPS = 30
settings.REPRODUCING_COOLDOWN_VALUE = 100
settings.GROUP_MIN_NEIGHBORS = 3
settings.GROUP_MAX_RADIUS = 100
settings.GROUP_COHESION_THRESHOLD = 0.5
settings.GROUP_PERSISTENCE_FRAMES = 10
settings.GROUP_MATURITY_RATIO = 0.5
settings.MEMORY_MAX_VISITED = 10
settings.MEMORY_MAX_FOOD = 10
settings.MEMORY_MAX_THREATS = 10
settings.MEMORY_MAX_PARTNERS = 10
settings.TELEMETRY_ENABLED = False

def verify_single_species():
    print("\n--- Verifying Single Species Spawn ---")
    rng = random.Random(42)
    # Force settings to 1
    settings.INITIAL_BASEFORM_COUNT = 1
    templates = base_templates(rng, count=1)
    print(f"Templates generated: {len(templates)}", flush=True)
    if len(templates) == 1:
        print("PASS: Only 1 template generated.", flush=True)
        print(f"Template key: {templates[0].key}", flush=True)
    else:
        print(f"FAIL: Generated {len(templates)} templates.", flush=True)

from evolution.entities.ai import update_brain

def verify_brain_control():
    print("\n--- Verifying Brain Control ---", flush=True)
    state = SimulationState()
    rng = random.Random(42)
    templates = base_templates(rng, count=1)
    dna = templates[0].spawn_profile(0, rng)
    
    # Ensure brain weights are present
    if not dna.get("brain_weights"):
        dna["brain_weights"] = [random.uniform(-1, 1) for _ in range(1000)] # Mock weights

    lifeform = Lifeform(state, 100, 100, dna, generation=1)
    
    # Mock neural controller to force outputs
    class MockBrain:
        def __init__(self):
            self.outputs = {}
        def think(self, inputs):
            return self.outputs
        def forward(self, inputs): # ai.py calls forward, not think
            return self.outputs
    
    lifeform._neural_controller = MockBrain()
    
    # Test Movement
    print("Testing Movement Control...", flush=True)
    lifeform._neural_controller.outputs = {
        "tail_thrust": 1.0, # ai.py expects specific keys from controller
        "left_fin_thrust": 0.0,
        "right_fin_thrust": 0.5,
        "vertical_thrust": 0.0,
        "bite_intent": 0.0,
        "lum_intensity": 0.0,
        "lum_pattern_mod": 0.0,
        "reproduce_intent": 0.0
    }
    # Note: ai.py _interpret_outputs maps list to keys. 
    # But MockBrain.forward returns dict? 
    # ai.py: outputs = controller.forward(inputs)
    # ai.py: commands = _interpret_outputs(outputs)
    # ai.py: values = list(outputs)
    # So controller.forward must return a list or iterable!
    
    # I need to check what NeuralController.forward returns.
    # Usually it returns a list of floats.
    
    # Let's check ai.py _interpret_outputs again.
    # It maps list indices to keys.
    # 0: tail, 1: left, 2: right, 3: vertical, 4: bite, 5: lum, 6: pattern, 7: reproduce
    
    lifeform._neural_controller.forward = lambda inputs: [1.0, 0.0, 0.5, 0.0, -1.0, -1.0, 0.0, -1.0] 
    # -1.0 for bite/lum/reproduce because _interpret_outputs does (val + 1.0) * 0.5
    
    update_brain(lifeform, state, 0.1)
    
    print(f"Neural Thrust Ratio: {lifeform.neural_thrust_ratio}", flush=True)
    print(f"Target Turn (derived): {lifeform.neural_commands.get('right_fin_thrust') - lifeform.neural_commands.get('left_fin_thrust')}", flush=True)
    
    if lifeform.neural_thrust_ratio > 0.5:
        print("PASS: Thrust output reflected in lifeform state.", flush=True)
    else:
        print(f"FAIL: Thrust output not set correctly. Ratio: {lifeform.neural_thrust_ratio}", flush=True)
        
    # Test Biting
    print("Testing Biting Control...", flush=True)
    # bite is index 4. Set to 1.0 -> (1+1)*0.5 = 1.0
    lifeform._neural_controller.forward = lambda inputs: [0.0, 0.0, 0.0, 0.0, 1.0, -1.0, 0.0, -1.0]
    update_brain(lifeform, state, 0.1)
    print(f"Bite Intent: {lifeform.bite_intent}", flush=True)
    
    if lifeform.bite_intent > 0.8:
        print("PASS: Bite intent reflected in lifeform state.", flush=True)
    else:
        print(f"FAIL: Bite intent not set correctly. Value: {lifeform.bite_intent}", flush=True)

    # Test Reproduction
    print("Testing Reproduction Control...", flush=True)
    # reproduce is index 7. Set to 1.0
    lifeform._neural_controller.forward = lambda inputs: [0.0, 0.0, 0.0, 0.0, -1.0, -1.0, 0.0, 1.0]
    update_brain(lifeform, state, 0.1)
    print(f"Reproduce Intent: {lifeform.reproduce_intent}", flush=True)
    
    if lifeform.reproduce_intent > 0.8:
        print("PASS: Reproduce intent reflected in lifeform state.", flush=True)
    else:
        print(f"FAIL: Reproduce intent not set correctly. Value: {lifeform.reproduce_intent}", flush=True)

if __name__ == "__main__":
    with open("verify_log.txt", "w") as f:
        sys.stdout = f
        pygame.init()
        verify_single_species()
        verify_brain_control()
        pygame.quit()

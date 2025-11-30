
import sys
import os
import pygame
from pygame.math import Vector2

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evolution.simulation.state import SimulationState
from evolution.entities.lifeform import Lifeform
from evolution.entities.reproduction import create_asexual_offspring
from evolution.rendering.modular_lifeform_renderer import modular_lifeform_renderer
from evolution.config import settings

def verify_refactor():
    pygame.init()
    display = pygame.display.set_mode((800, 600))
    
    print("Initializing simulation state...")
    state = SimulationState()
    # state.initialise_resources() # Not a method on dataclass
    from evolution.systems.spatial_hash import SpatialHashGrid
    state.spatial_grid = SpatialHashGrid(cell_size=100)
    
    # Create a lifeform
    print("Creating lifeform...")
    dna = {
        "dna_id": "test_dna",
        "color": (255, 0, 0),
        "width": 20,
        "height": 20,
        "health": 100,
        "energy": 100,
        "maturity": 10,
        "longevity": 100,
        "vision": 100,
        "diet": "herbivore",
        "digest_efficiency_plants": 1.0,
        "digest_efficiency_meat": 0.0,
        "reproduction_cost": 50,
        "gestation": 0,
        "litter_size": 1,
        "brain_mutability": 0.1,
        "mutation_rate": 0.1,
    }
    lifeform = Lifeform(state, 400, 300, dna, 1)
    state.lifeforms.append(lifeform)
    
    # Test 1: Neural Controller Inputs/Outputs
    print("\nTest 1: Neural Controller Keys")
    from evolution.entities.neural_controller import INPUT_KEYS, OUTPUT_KEYS
    if "reproductive_urge" in INPUT_KEYS:
        print("PASS: reproductive_urge in INPUT_KEYS")
    else:
        print("FAIL: reproductive_urge missing from INPUT_KEYS")
        
    if "reproduce_intent" in OUTPUT_KEYS:
        print("PASS: reproduce_intent in OUTPUT_KEYS")
    else:
        print("FAIL: reproduce_intent missing from OUTPUT_KEYS")

    # Test 2: Asexual Reproduction
    print("\nTest 2: Asexual Reproduction")
    lifeform.age = 20 # Adult
    lifeform.energy_now = 100
    lifeform.reproduced_cooldown = 0
    lifeform.reproduce_intent = 1.0 # High intent
    
    # Force update to trigger logic (simulating combat/interaction check)
    from evolution.entities.combat import resolve_close_interactions
    resolve_close_interactions(lifeform)
    
    # Check if offspring created
    if len(state.lifeforms) > 1:
        print(f"PASS: Offspring created. Total lifeforms: {len(state.lifeforms)}")
        child = state.lifeforms[1]
        print(f"Child DNA ID: {child.dna_id}")
    else:
        print("FAIL: No offspring created")
        # Try manual call
        print("Attempting manual reproduce_asexual call...")
        success = lifeform.reproduce_asexual()
        if success:
             print("PASS: Manual reproduce_asexual succeeded")
        else:
             print("FAIL: Manual reproduce_asexual failed")

    # Test 3: Bioluminescence Rendering
    print("\nTest 3: Bioluminescence Rendering")
    lifeform.lum_intensity = 0.8
    try:
        modular_lifeform_renderer.render_surface(lifeform)
        state_renderer = getattr(lifeform, "_modular_render_state", None)
        if state_renderer and state_renderer.lum_intensity == 0.8:
            print("PASS: lum_intensity passed to renderer state")
        else:
            print(f"FAIL: lum_intensity not passed correctly. Got: {getattr(state_renderer, 'lum_intensity', 'None')}")
    except Exception as e:
        print(f"FAIL: Rendering raised exception: {e}")

    # Test 4: Generic Feeding (AI Sensing)
    print("\nTest 4: Generic Feeding Sensing")
    from evolution.entities.ai import _sense_food_density
    # Add a plant
    class MockPlant:
        def __init__(self, x, y, w, h):
            self.x = x
            self.y = y
            self.width = w
            self.height = h
            
    plant = MockPlant(420, 300, 10, 10)
    state.plants.append(plant)
    state.spatial_grid.add_plant(plant)
    
    # Debug query
    radius = max(12.0, lifeform.vision * 0.6)
    print(f"Vision radius: {radius}")
    plants_found = list(state.spatial_grid.query_plants(lifeform.x, lifeform.y, radius))
    print(f"Plants found in grid: {len(plants_found)}")
    
    # Sense
    food_density = _sense_food_density(lifeform, state, Vector2(1, 0))
    print(f"Food density (herbivore): {food_density}")
    if food_density[0] > 0:
        print("PASS: Herbivore sensed plant")
    else:
        print("FAIL: Herbivore failed to sense plant")
        
    # Change to carnivore
    lifeform.digest_efficiency_plants = 0.0
    lifeform.digest_efficiency_meat = 1.0
    food_density_carn = _sense_food_density(lifeform, state, Vector2(1, 0))
    print(f"Food density (carnivore sensing plant): {food_density_carn}")
    if food_density_carn[0] == 0:
        print("PASS: Carnivore ignored plant")
    else:
        print("FAIL: Carnivore sensed plant (should ignore)")

    print("\nVerification Complete")

if __name__ == "__main__":
    verify_refactor()

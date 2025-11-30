
import logging
import random
import sys
import os
import pygame

# Mock pygame if needed, but try to initialize it headless
os.environ["SDL_VIDEODRIVER"] = "dummy"
pygame.init()
pygame.display.set_mode((1, 1))

from evolution.simulation.state import SimulationState
from evolution.entities.lifeform import Lifeform
from evolution.dna.blueprints import generate_modular_blueprint
from evolution.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("reproduce_test")

def create_dummy_dna(diet="herbivore", dna_id="test_dna"):
    genome = generate_modular_blueprint(diet)
    return {
        "dna_id": dna_id,
        "color": (100, 200, 100),
        "maturity": 100,
        "longevity": 1000,
        "diet": diet,
        "genome": genome,
        "brain_weights": [], # Will be initialized
        "risk_tolerance": 0.5,
        "restlessness": 0.5,
        "digest_efficiency_plants": 1.0,
        "digest_efficiency_meat": 0.0,
        "bite_force": 10.0,
        "tissue_hardness": 0.6,
        "morphology": {},
        "development": {},
    }

def test_reproduction():
    logger.info("Starting reproduction test...")
    
    state = SimulationState()
    
    # Create parent 1
    dna1 = create_dummy_dna(dna_id="parent1")
    parent1 = Lifeform(state, 100, 100, dna1, 1)
    parent1.age = 200 # Adult
    parent1.energy_now = parent1.energy # Full energy
    state.lifeforms.append(parent1)
    state.dna_profiles.append(dna1)
    
    # Create parent 2
    dna2 = create_dummy_dna(dna_id="parent2")
    parent2 = Lifeform(state, 120, 120, dna2, 1)
    parent2.age = 200 # Adult
    parent2.energy_now = parent2.energy # Full energy
    state.lifeforms.append(parent2)
    state.dna_profiles.append(dna2)
    
    logger.info(f"Parent 1 ID: {parent1.id}, DNA: {parent1.dna_id}")
    logger.info(f"Parent 2 ID: {parent2.id}, DNA: {parent2.dna_id}")
    
    # Test Sexual Reproduction
    logger.info("Testing Sexual Reproduction...")
    initial_count = len(state.lifeforms)
    parent1.reproduce(parent2)
    
    if len(state.lifeforms) > initial_count:
        child = state.lifeforms[-1]
        logger.info(f"Sexual reproduction successful! Child ID: {child.id}, DNA: {child.dna_id}")
        logger.info(f"Child parents: {child.parent_ids}")
        assert len(child.parent_ids) == 2
        assert parent1.id in child.parent_ids
        assert parent2.id in child.parent_ids
    else:
        logger.error("Sexual reproduction failed!")
        
    # Test Asexual Reproduction
    logger.info("Testing Asexual Reproduction...")
    initial_count = len(state.lifeforms)
    parent1.reproduce_asexual()
    
    if len(state.lifeforms) > initial_count:
        child = state.lifeforms[-1]
        logger.info(f"Asexual reproduction successful! Child ID: {child.id}, DNA: {child.dna_id}")
        logger.info(f"Child parents: {child.parent_ids}")
        assert len(child.parent_ids) == 1
        assert parent1.id in child.parent_ids
    else:
        logger.error("Asexual reproduction failed!")

if __name__ == "__main__":
    try:
        test_reproduction()
        print("Test completed successfully.")
    except Exception as e:
        logger.exception("Test failed with exception")
        sys.exit(1)

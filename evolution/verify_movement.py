
import pygame
from pygame.math import Vector2
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from evolution.entities.lifeform import Lifeform, BehaviorMode
from evolution.entities import movement, ai
from evolution.simulation.state import SimulationState

class MockWorld:
    def __init__(self):
        self.width = 1000
        self.height = 1000
        self.lifeforms = []
        self.plants = []
        
    def resolve_entity_movement(self, rect, prev_pos, new_pos):
        # Simple bounds checking
        x, y = new_pos
        collided = False
        hit_x = False
        hit_y = False
        
        if x < 0: x = 0; hit_x = True
        if x > self.width: x = self.width; hit_x = True
        if y < 0: y = 0; hit_y = True
        if y > self.height: y = self.height; hit_y = True
        
        return x, y, hit_x, hit_y, collided

    def apply_fluid_dynamics(self, lifeform, thrust, dt, max_speed=100):
        # Simple euler integration
        velocity = lifeform.velocity
        
        # Drag
        drag_coeff = lifeform.drag_coefficient
        drag_force = -velocity * velocity.length() * drag_coeff * 0.5
        
        # Acceleration
        # thrust is already acceleration (m/s^2) from movement.py
        # drag_force is Force, so divide by mass
        acceleration = thrust + (drag_force / lifeform.mass)
        
        lifeform.velocity += acceleration * dt
        # lifeform.velocity *= 0.995 # Reduced drag - removed as we have explicit drag now
        
        pos = Vector2(lifeform.x, lifeform.y) + lifeform.velocity * dt
        return pos, None
        
    def get_environment_context(self, x, y):
        return None, {"movement": 1.0, "hunger": 1.0, "energy": 1.0, "health": 0.0}

    def is_blocked(self, rect, include_water=True):
        return False

def log(msg):
    with open("movement_log.txt", "a") as f:
        f.write(msg + "\n")
    print(msg)

def test_movement():
    # Clear log
    with open("movement_log.txt", "w") as f:
        f.write("Starting test\n")

    state = SimulationState()
    state.world = MockWorld()
    
    # Create a lifeform
    dna = {
        "dna_id": "test_creature",
        "color": (255, 0, 0),
        "maturity": 100,
        "longevity": 1000,
        "boid_tendency": 0.8,
        "morphology": {"fins": 2},
        "vision": 500,
        "risk_tolerance": 0.0
    }
    
    creature = Lifeform(state, 500, 500, dna, 1)
    state.lifeforms.append(creature)
    
    log(f"Initial Mode: {creature.current_behavior_mode}")
    log(f"Initial Thrust Phase: {creature.thrust_phase}")
    if hasattr(creature, "physics_body"):
        pb = creature.physics_body
        log(f"PhysicsBody: Mass={pb.mass}, MaxThrust={pb.max_thrust}, Drag={pb.drag_coefficient}")
        log(f"Propulsion Accel (effort=1.0): {pb.propulsion_acceleration(1.0)}")
    else:
        log("PhysicsBody NOT FOUND")
    
    # Simulate a few frames
    dt = 0.016 # 60 FPS
    for i in range(60):
        ai.update_brain(creature, state, dt)
        movement.update_movement(creature, state, dt)
        
        if i % 10 == 0:
            log(f"Frame {i}: Mode={creature.current_behavior_mode}, Speed={creature.speed:.2f}, Phase={creature.thrust_phase:.2f}, Adrenaline={creature.adrenaline_factor:.2f}")
            
    # Test Flee Mode (Adrenaline)
    log("\n--- Testing Flee Mode ---")
    creature.current_behavior_mode = BehaviorMode.FLEE
    # Mock a threat
    class MockThreat:
        def __init__(self):
            self.health_now = 100
            self.x = 490
            self.y = 490
            self.rect = pygame.Rect(490, 490, 10, 10)
            self.attack_power_now = 1000
            self.id = "threat"
            self.dna_id = "predator"
            self.defence_power_now = 10
            self.energy = 100
            self.energy_now = 100
            self.wounded = 0
            
    creature.closest_enemy = MockThreat()
    creature.update_targets = lambda: None
    
    for i in range(60):
        ai.update_brain(creature, state, dt)
        movement.update_movement(creature, state, dt)
        
        if i % 10 == 0:
             log(f"Frame {i}: Mode={creature.current_behavior_mode}, Phase={creature.thrust_phase:.2f}, Adrenaline={creature.adrenaline_factor:.2f}")

    if creature.adrenaline_factor > 0.1:
        log("SUCCESS: Adrenaline increased in Flee mode.")
    else:
        log("FAILURE: Adrenaline did not increase.")

    # Test Vertical Movement (Diving)
    log("\n--- Testing Vertical Movement ---")
    creature.current_behavior_mode = BehaviorMode.SEARCH
    creature.closest_enemy = None
    creature.y = 100
    creature.x = 500
    # Mock food at depth
    class MockFood:
        def __init__(self):
            self.x = 500
            self.y = 500
            self.rect = pygame.Rect(500, 500, 10, 10)
            self.resource = 100
            self.id = "food"
            
    creature.closest_plant = MockFood()
    creature.hunger = 1000 # Starving
    
    # Monkeypatch update_targets again to persist food
    creature.update_targets = lambda: None
    
    initial_y = creature.y
    for i in range(300):
        ai.update_brain(creature, state, dt)
        movement.update_movement(creature, state, dt)
        if i % 10 == 0:
            log(f"Frame {i}: Dir=({creature.x_direction:.2f}, {creature.y_direction:.2f}), Hunger={creature.hunger}")
        
    log(f"Initial Y: {initial_y}, Final Y: {creature.y}")
    if creature.y > initial_y + 10:
        log("SUCCESS: Creature dived towards food.")
    else:
        log("FAILURE: Creature did not dive.")

if __name__ == "__main__":
    test_movement()

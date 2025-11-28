
import pygame
from pygame.math import Vector2
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from evolution.entities.lifeform import Lifeform
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
    
    log(f"Initial Thrust Phase: {creature.thrust_phase}")
    if hasattr(creature, "physics_body"):
        pb = creature.physics_body
        log(f"PhysicsBody: Mass={pb.mass}, MaxThrust={pb.max_thrust}, Drag={pb.drag_coefficient}")
        log(f"Propulsion Accel (effort=1.0): {pb.propulsion_acceleration(1.0)}")
    else:
        log("PhysicsBody NOT FOUND")
    
    # Simulate a few frames driven only by the neural controller
    dt = 0.016 # 60 FPS
    initial_position = Vector2(creature.x, creature.y)
    for i in range(120):
        ai.update_brain(creature, state, dt)
        movement.update_movement(creature, state, dt)

        if i % 20 == 0:
            log(f"Frame {i}: Speed={creature.speed:.2f}, Phase={creature.thrust_phase:.2f}")

    displacement = Vector2(creature.x, creature.y) - initial_position
    log(f"Neural displacement: {displacement.length():.2f} (dx={displacement.x:.2f}, dy={displacement.y:.2f})")
    if displacement.length() > 1.0:
        log("SUCCESS: Neural controller produced movement without scripted behavior.")
    else:
        log("FAILURE: Neural controller did not move the creature.")

if __name__ == "__main__":
    test_movement()

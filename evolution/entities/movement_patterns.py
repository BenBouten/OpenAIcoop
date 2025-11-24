"""Procedural movement patterns for lifeform searching and wandering."""

import math
from pygame.math import Vector2
import random

def get_wander_vector(
    current_velocity: Vector2,
    current_wander_angle: float,
    wander_strength: float = 0.5,
    steering_strength: float = 0.2
) -> tuple[Vector2, float]:
    """
    Generate a natural 'wander' vector using Reynolds steering behavior.
    Returns (new_direction, new_wander_angle).
    """
    # 1. Project a circle ahead of the agent
    circle_distance = 2.0
    circle_radius = 1.5
    
    # Base direction (forward)
    if current_velocity.length_squared() > 0:
        forward = current_velocity.normalize()
    else:
        forward = Vector2(1, 0)
        
    # 2. Calculate displacement on the circle based on angle
    # Add small random jitter to the angle
    jitter = (random.random() - 0.5) * wander_strength
    new_angle = current_wander_angle + jitter
    
    # Constrain angle to avoid spinning? No, wandering can loop.
    
    displacement = Vector2(math.cos(new_angle), math.sin(new_angle)) * circle_radius
    
    # 3. Target is ahead + displacement
    target = forward * circle_distance + displacement
    
    return target.normalize(), new_angle

def get_vertical_search_vector(t: float) -> Vector2:
    """Generate a vertical bobbing search pattern (for depth checking)."""
    # Slow down the bobbing for more natural buoyancy feel
    y = math.sin(t * 0.8) 
    x = math.cos(t * 0.3) * 0.2
    return Vector2(x, y).normalize()

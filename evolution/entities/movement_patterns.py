"""Procedural movement patterns for lifeform searching and wandering."""

import math
from pygame.math import Vector2
import random

def get_spiral_vector(t: float, scale: float = 1.0) -> Vector2:
    """Generate a spiral pattern vector based on time t."""
    # Expanding spiral: radius increases with time
    # Reset every so often to keep it local
    cycle = t % 20.0
    radius = 1.0 + cycle * 0.5 * scale
    angle = t * 2.0
    
    x = math.cos(angle) * radius
    y = math.sin(angle) * radius
    
    return Vector2(x, y).normalize()

def get_zigzag_vector(t: float, base_direction: Vector2, amplitude: float = 1.0) -> Vector2:
    """Generate a zigzag vector along a base direction."""
    if base_direction.length_squared() == 0:
        return Vector2(1, 0)
        
    # Perpendicular vector
    perp = Vector2(-base_direction.y, base_direction.x).normalize()
    
    # Oscillate side to side
    offset = perp * math.sin(t * 3.0) * amplitude
    
    return (base_direction + offset).normalize()

def get_vertical_search_vector(t: float) -> Vector2:
    """Generate a vertical bobbing search pattern (for depth checking)."""
    y = math.sin(t * 1.5)
    x = math.cos(t * 0.5) * 0.3 # Slight horizontal drift
    return Vector2(x, y).normalize()

def get_clover_vector(t: float) -> Vector2:
    """Generate a clover-leaf pattern."""
    k = 2 # Number of leaves
    r = math.cos(k * t)
    x = r * math.cos(t)
    y = r * math.sin(t)
    return Vector2(x, y).normalize()

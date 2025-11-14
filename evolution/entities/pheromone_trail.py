"""Pheromone trail helpers used by the lifeform AI.

This module replaces the old one-off ``Pheromone`` helper with a richer
representation that stores direction information, handles evaporation and can be
sampled by nearby lifeforms.  The behaviour layer (``ai.update_brain``) uses the
helpers below to deposit new pheromones when a lifeform returns to its nest and
to query pheromone guidance when foraging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import pygame
from pygame.math import Vector2


@dataclass(slots=True)
class PheromoneTrail:
    """Single pheromone marker that slowly evaporates.

    Attributes
    ----------
    position:
        World position where the marker was deposited.
    direction_to_home:
        Normalised vector that points towards the nest/home location.  Ants that
        want to reach the food walk in the *opposite* direction.
    strength:
        Current intensity of the marker.  The renderer uses this value for the
        colour tint and ``update_trails`` decreases it over time.
    evaporation_rate:
        Amount of strength that disappears per simulation second.
    radius:
        Maximum distance (in pixels) at which other lifeforms can sense this
        marker.
    colour:
        RGB tuple that is tinted towards white as the pheromone fades.
    """

    position: Vector2
    direction_to_home: Vector2
    strength: float
    evaporation_rate: float
    radius: float
    colour: Tuple[int, int, int]

    def update(self, dt: float) -> None:
        """Reduce the strength based on the elapsed simulation time."""

        self.strength = max(0.0, self.strength - self.evaporation_rate * dt)

    def is_active(self) -> bool:
        """Return ``True`` while the pheromone is still visible/usable."""

        return self.strength > 0.5

    def draw(self, surface: pygame.Surface) -> None:
        """Render a small rectangle tinted by the current strength."""

        intensity = max(30, min(255, int(self.strength)))
        base = pygame.Color(*self.colour)
        draw_colour = (
            min(255, base.r + (255 - base.r) * (255 - intensity) // 255),
            min(255, base.g + (255 - base.g) * (255 - intensity) // 255),
            min(255, base.b + (255 - base.b) * (255 - intensity) // 255),
        )
        size = 6
        pygame.draw.rect(
            surface,
            draw_colour,
            (self.position.x - size / 2, self.position.y - size / 2, size, size),
        )

    def direction_to_food(self) -> Vector2:
        """Return the vector that points away from the nest towards food."""

        if self.direction_to_home.length_squared() == 0:
            return Vector2()
        return (-self.direction_to_home).normalize()

    def influence_at(self, position: Vector2) -> float:
        """Compute how attractive this pheromone is for a given position."""

        distance = position.distance_to(self.position)
        if distance > self.radius:
            return 0.0
        falloff = max(0.0, 1.0 - distance / max(1.0, self.radius))
        return self.strength * falloff


def create_trail(
    position: Tuple[float, float],
    direction_to_home: Vector2,
    strength: float,
    evaporation_rate: float,
    radius: float,
    colour: Tuple[int, int, int],
) -> PheromoneTrail:
    """Factory helper that normalises vectors and returns a trail instance."""

    normalised = direction_to_home
    if normalised.length_squared() > 0:
        normalised = normalised.normalize()
    return PheromoneTrail(Vector2(position), normalised, strength, evaporation_rate, radius, colour)


def update_trails(
    trails: List[PheromoneTrail],
    dt: float,
    evaporation_rate: Optional[float] = None,
) -> None:
    """Update and prune pheromones in-place.

    Parameters
    ----------
    trails:
        Mutable sequence of pheromone markers.
    dt:
        Simulation delta time (in seconds).
    evaporation_rate:
        Optional override that lets gameplay sliders change the decay speed for
        existing markers.
    """

    active: List[PheromoneTrail] = []
    for trail in trails:
        if evaporation_rate is not None:
            trail.evaporation_rate = evaporation_rate
        trail.update(dt)
        if trail.is_active():
            active.append(trail)
    trails[:] = active


def strongest_trail(
    trails: Iterable[PheromoneTrail],
    position: Tuple[float, float],
    sense_radius: float,
) -> Optional[PheromoneTrail]:
    """Return the strongest pheromone that can be sensed from ``position``."""

    seeker_pos = Vector2(position)
    best: Optional[PheromoneTrail] = None
    best_influence = 0.0

    for trail in trails:
        if seeker_pos.distance_to(trail.position) > sense_radius:
            continue
        influence = trail.influence_at(seeker_pos)
        if influence > best_influence:
            best_influence = influence
            best = trail

    return best


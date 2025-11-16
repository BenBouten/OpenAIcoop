"""Carrion entities spawned when a creature dies."""

from __future__ import annotations

import math
import random
from typing import Tuple

import pygame
from pygame.math import Vector2

from ..config import settings

Color = Tuple[int, int, int]


class SinkingCarcass:
    """Slowly sinking resource that omnivores en carnivores can eat."""

    def __init__(
        self,
        *,
        position: Tuple[float, float],
        size: Tuple[int, int],
        mass: float,
        nutrition: float,
        color: Color,
    ) -> None:
        self.x, self.y = position
        width, height = size
        self.width = max(6, int(width))
        self.height = max(4, int(height * 0.6))
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        self.mass = max(0.5, mass)
        self.velocity = Vector2(random.uniform(-3.0, 3.0), 0.0)
        self.resource = float(max(5.0, nutrition))
        self.decay_rate = max(0.05, self.resource * 0.0005)
        self.color = color
        self.outline_color = tuple(max(0, min(255, channel - 40)) for channel in color)
        self.body_density = self.mass / max(1.0, self.width * self.height * 0.1)

    def update(self, world: "World", dt: float) -> None:
        from .ocean_physics import OceanPhysics  # lazy import to avoid cycles

        gravity = 9.81
        fluid_density = 1.0
        current = Vector2()
        if hasattr(world, "ocean") and isinstance(world.ocean, OceanPhysics):
            fluid = world.ocean.properties_at(self.rect.centery)
            gravity = world.ocean.gravity
            fluid_density = fluid.density
            current = fluid.current
        buoyancy = (fluid_density / max(0.2, self.body_density) - 1.0) * gravity
        vertical_acc = gravity + buoyancy
        self.velocity.y += vertical_acc * dt
        self.velocity += (current - self.velocity) * 0.05 * dt
        self.x += self.velocity.x * dt
        self.y += self.velocity.y * dt
        max_x = world.width - self.width
        max_y = world.height - self.height
        if self.x < 0:
            self.x = 0
            self.velocity.x *= -0.3
        elif self.x > max_x:
            self.x = max_x
            self.velocity.x *= -0.3
        if self.y > max_y:
            self.y = max_y
            self.velocity.y *= -0.2
        self.rect.topleft = (int(self.x), int(self.y))
        self.resource = max(0.0, self.resource - self.decay_rate * dt)

    def draw(self, surface: pygame.Surface) -> None:
        if self.resource <= 0:
            return
        ellipse = pygame.Rect(0, 0, self.width, self.height)
        body_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.ellipse(body_surface, (*self.color, 180), ellipse)
        pygame.draw.ellipse(body_surface, self.outline_color, ellipse, 2)
        surface.blit(body_surface, self.rect.topleft)

    def is_depleted(self) -> bool:
        return self.resource <= 0.25

    def distance_to(self, point: Tuple[float, float]) -> float:
        dx = self.rect.centerx - point[0]
        dy = self.rect.centery - point[1]
        return math.hypot(dx, dy)

    def consume(self, amount: float) -> float:
        if self.resource <= 0:
            return 0.0
        bite = min(amount, self.resource)
        self.resource -= bite
        return bite

    def blocks_rect(self, _rect: pygame.Rect) -> bool:
        return False

    def contains_point(self, x: float, y: float) -> bool:
        return self.rect.collidepoint(int(x), int(y))

    def movement_modifier_for(self, _lifeform: "Lifeform") -> float:
        return 1.0

    def apply_effect(self, lifeform: "Lifeform", nutrition: float) -> None:
        hunger_reduction = nutrition * settings.PLANT_HUNGER_SATIATION_PER_NUTRITION * 1.4
        lifeform.hunger = max(settings.HUNGER_MINIMUM, lifeform.hunger - hunger_reduction)
        lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + nutrition * 0.8)
        lifeform.health_now = min(lifeform.health, lifeform.health_now + nutrition * 0.2)

    def summary(self) -> dict:
        return {
            "resource": round(self.resource, 2),
            "position": (self.x, self.y),
        }

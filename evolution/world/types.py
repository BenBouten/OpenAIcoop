"""Shared world data structures for terrain generation and simulation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame


Color = Tuple[int, int, int]


@dataclass
class WeatherPattern:
    name: str
    temperature: int
    precipitation: str
    movement_modifier: float = 1.0
    hunger_modifier: float = 1.0
    regrowth_modifier: float = 1.0
    energy_modifier: float = 1.0
    health_tick: float = 0.0
    duration_range: Tuple[int, int] = (15000, 30000)

    def random_duration(self) -> int:
        return random.randint(*self.duration_range)


@dataclass
class Barrier:
    rect: pygame.Rect
    color: Color = (90, 90, 90)
    label: str = ""


@dataclass
class WaterBody:
    kind: str
    segments: List[pygame.Rect]
    color: Color = (70, 140, 220)

    def collides(self, rect: pygame.Rect) -> bool:
        return any(segment.colliderect(rect) for segment in self.segments)


@dataclass
class BiomeRegion:
    name: str
    rect: pygame.Rect
    color: Color
    weather_patterns: List[WeatherPattern]
    movement_modifier: float = 1.0
    hunger_modifier: float = 1.0
    regrowth_modifier: float = 1.0
    energy_modifier: float = 1.0
    health_modifier: float = 0.0
    active_weather: Optional[WeatherPattern] = None
    weather_expires_at: int = 0
    mask: Optional[pygame.Mask] = None
    mask_offset: Tuple[int, int] = (0, 0)

    def update_weather(self, now_ms: int) -> None:
        if self.active_weather is None or now_ms >= self.weather_expires_at:
            self.active_weather = random.choice(self.weather_patterns)
            self.weather_expires_at = now_ms + self.active_weather.random_duration()

    def contains(self, x: float, y: float) -> bool:
        if not self.rect.collidepoint(int(x), int(y)):
            return False
        if self.mask is None:
            return True
        local_x = int(x) - self.mask_offset[0]
        local_y = int(y) - self.mask_offset[1]
        if 0 <= local_x < self.mask.get_size()[0] and 0 <= local_y < self.mask.get_size()[1]:
            return bool(self.mask.get_at((local_x, local_y)))
        return False

    def get_effects(self) -> Dict[str, float | int | str]:
        weather = self.active_weather
        if weather is None:
            weather = WeatherPattern(
                name="Stabiel",
                temperature=20,
                precipitation="helder",
            )
        return {
            "movement": self.movement_modifier * weather.movement_modifier,
            "hunger": self.hunger_modifier * weather.hunger_modifier,
            "regrowth": self.regrowth_modifier * weather.regrowth_modifier,
            "energy": self.energy_modifier * weather.energy_modifier,
            "health": self.health_modifier + weather.health_tick,
            "temperature": weather.temperature,
            "precipitation": weather.precipitation,
            "weather_name": weather.name,
        }

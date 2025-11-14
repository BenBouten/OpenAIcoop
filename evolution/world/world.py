"""World generation and biome management for the evolution simulation."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pygame

from ..config import settings


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
    color: Tuple[int, int, int] = (90, 90, 90)
    label: str = ""


@dataclass
class WaterBody:
    kind: str
    segments: List[pygame.Rect]
    color: Tuple[int, int, int] = (70, 140, 220)

    def collides(self, rect: pygame.Rect) -> bool:
        return any(segment.colliderect(rect) for segment in self.segments)


@dataclass
class BiomeRegion:
    name: str
    rect: pygame.Rect
    color: Tuple[int, int, int]
    weather_patterns: List[WeatherPattern]
    movement_modifier: float = 1.0
    hunger_modifier: float = 1.0
    regrowth_modifier: float = 1.0
    energy_modifier: float = 1.0
    health_modifier: float = 0.0
    active_weather: Optional[WeatherPattern] = None
    weather_expires_at: int = 0

    def update_weather(self, now_ms: int) -> None:
        if self.active_weather is None or now_ms >= self.weather_expires_at:
            self.active_weather = random.choice(self.weather_patterns)
            self.weather_expires_at = now_ms + self.active_weather.random_duration()

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


class World:
    def __init__(
        self,
        width: int,
        height: int,
        environment_modifiers: Optional[Dict[str, float]] = None,
    ):
        self.width = width
        self.height = height
        self.background_color = (228, 222, 208)
        self.barriers: List[Barrier] = []
        self.water_bodies: List[WaterBody] = []
        self.biomes: List[BiomeRegion] = []
        self.environment_modifiers = environment_modifiers
        self._generate()

    def set_environment_modifiers(self, modifiers: Dict[str, float]) -> None:
        self.environment_modifiers = modifiers

    def _generate(self) -> None:
        self.barriers.clear()
        self.water_bodies.clear()
        self.biomes.clear()
        self._create_border_barriers()
        self._create_interior_barriers()
        self._create_water_bodies()
        self._create_biomes()

    def regenerate(self) -> None:
        self._generate()

    def _create_border_barriers(self) -> None:
        border_thickness = 12
        self.barriers.extend([
            Barrier(pygame.Rect(0, 0, self.width, border_thickness)),
            Barrier(pygame.Rect(0, 0, border_thickness, self.height)),
            Barrier(pygame.Rect(0, self.height - border_thickness, self.width, border_thickness)),
            Barrier(pygame.Rect(self.width - border_thickness, 0, border_thickness, self.height)),
        ])

    def _create_interior_barriers(self) -> None:
        ridge_rect = pygame.Rect(self.width // 3, 140, 40, self.height - 280)
        canyon_rect = pygame.Rect(2 * self.width // 3, self.height // 2, 30, self.height // 2 - 60)
        self.barriers.extend([
            Barrier(ridge_rect, (120, 110, 95), "rotsrug"),
            Barrier(canyon_rect, (110, 100, 85), "canyon"),
        ])

    def _create_water_bodies(self) -> None:
        sea_rect = pygame.Rect(40, self.height - 220, self.width // 2, 220)
        sea = WaterBody("sea", [sea_rect], color=(64, 140, 200))

        river_segments: List[pygame.Rect] = []
        segment_width = 32
        x = self.width - 220
        y = 0
        while y < self.height:
            segment = pygame.Rect(x, y, segment_width, 140)
            river_segments.append(segment)
            x += random.randint(-80, 60)
            x = max(self.width // 3, min(self.width - segment_width - 40, x))
            y += 120
        river = WaterBody("river", river_segments, color=(60, 150, 210))

        delta_segments: List[pygame.Rect] = []
        for idx, segment in enumerate(river_segments[-3:]):
            offset = idx * 50
            delta_segments.append(
                pygame.Rect(segment.x - offset, segment.bottom - 60, segment_width + 100, 80)
            )
        delta = WaterBody("delta", delta_segments, color=(70, 170, 220))

        self.water_bodies.extend([sea, river, delta])

    def _create_biomes(self) -> None:
        temperate_patterns = [
            WeatherPattern(
                "Zonnig",
                23,
                "helder",
                movement_modifier=1.05,
                hunger_modifier=0.9,
                regrowth_modifier=1.15,
                energy_modifier=1.1,
            ),
            WeatherPattern(
                "Lichte regen",
                18,
                "regen",
                movement_modifier=0.95,
                hunger_modifier=1.0,
                regrowth_modifier=1.35,
                energy_modifier=0.95,
            ),
            WeatherPattern(
                "Mist",
                15,
                "mist",
                movement_modifier=0.85,
                hunger_modifier=1.05,
                regrowth_modifier=1.2,
                energy_modifier=0.9,
                duration_range=(12000, 20000),
            ),
        ]
        forest_patterns = [
            WeatherPattern(
                "Dichte mist",
                14,
                "mist",
                movement_modifier=0.8,
                hunger_modifier=1.1,
                regrowth_modifier=1.4,
                energy_modifier=0.9,
            ),
            WeatherPattern(
                "Regenstorm",
                16,
                "storm",
                movement_modifier=0.7,
                hunger_modifier=1.15,
                regrowth_modifier=1.55,
                energy_modifier=0.85,
                health_tick=-0.2,
                duration_range=(10000, 18000),
            ),
            WeatherPattern(
                "Zwoel",
                22,
                "bewolkt",
                movement_modifier=0.9,
                hunger_modifier=1.05,
                regrowth_modifier=1.2,
                energy_modifier=1.0,
            ),
        ]
        desert_patterns = [
            WeatherPattern(
                "Hitteslag",
                36,
                "droog",
                movement_modifier=0.7,
                hunger_modifier=1.35,
                regrowth_modifier=0.6,
                energy_modifier=0.7,
                health_tick=-0.3,
                duration_range=(12000, 20000),
            ),
            WeatherPattern(
                "Koele nacht",
                20,
                "helder",
                movement_modifier=1.05,
                hunger_modifier=0.95,
                regrowth_modifier=0.8,
                energy_modifier=1.1,
            ),
            WeatherPattern(
                "Zandstorm",
                32,
                "storm",
                movement_modifier=0.55,
                hunger_modifier=1.45,
                regrowth_modifier=0.5,
                energy_modifier=0.6,
                health_tick=-0.4,
                duration_range=(8000, 15000),
            ),
        ]
        tundra_patterns = [
            WeatherPattern(
                "Sneeuw",
                -4,
                "sneeuw",
                movement_modifier=0.65,
                hunger_modifier=1.25,
                regrowth_modifier=0.7,
                energy_modifier=0.8,
                health_tick=-0.2,
            ),
            WeatherPattern(
                "Heldere kou",
                -10,
                "helder",
                movement_modifier=0.75,
                hunger_modifier=1.1,
                regrowth_modifier=0.5,
                energy_modifier=0.85,
            ),
            WeatherPattern(
                "Dooi",
                2,
                "regen",
                movement_modifier=0.85,
                hunger_modifier=1.0,
                regrowth_modifier=0.9,
                energy_modifier=0.9,
            ),
        ]
        marsh_patterns = [
            WeatherPattern(
                "Damp",
                19,
                "mist",
                movement_modifier=0.8,
                hunger_modifier=1.05,
                regrowth_modifier=1.5,
                energy_modifier=0.95,
            ),
            WeatherPattern(
                "Zware regen",
                17,
                "regen",
                movement_modifier=0.75,
                hunger_modifier=1.0,
                regrowth_modifier=1.6,
                energy_modifier=0.9,
                health_tick=0.1,
            ),
            WeatherPattern(
                "Helder",
                21,
                "helder",
                movement_modifier=0.95,
                hunger_modifier=0.95,
                regrowth_modifier=1.2,
                energy_modifier=1.05,
            ),
        ]

        self.biomes = [
            BiomeRegion(
                "Rivierdelta",
                pygame.Rect(
                    self.width // 3 - 80,
                    self.height // 2 - 160,
                    self.width // 2 + 40,
                    320,
                ),
                (120, 200, 150),
                marsh_patterns,
                movement_modifier=0.85,
                hunger_modifier=0.95,
                regrowth_modifier=1.4,
                energy_modifier=0.95,
                health_modifier=0.05,
            ),
            BiomeRegion(
                "Bosrand",
                pygame.Rect(60, 60, self.width // 3 - 20, self.height // 2),
                (80, 170, 120),
                forest_patterns,
                movement_modifier=0.8,
                hunger_modifier=0.9,
                regrowth_modifier=1.5,
                energy_modifier=1.0,
                health_modifier=0.02,
            ),
            BiomeRegion(
                "Steppe",
                pygame.Rect(
                    self.width // 3 + 20,
                    100,
                    self.width // 3 + 160,
                    self.height // 2 - 40,
                ),
                (180, 200, 120),
                temperate_patterns,
                movement_modifier=1.05,
                hunger_modifier=0.95,
                regrowth_modifier=1.0,
                energy_modifier=1.1,
            ),
            BiomeRegion(
                "Woestijnrand",
                pygame.Rect(
                    self.width // 2 + 120,
                    self.height - 320,
                    self.width // 2 - 160,
                    240,
                ),
                (210, 190, 120),
                desert_patterns,
                movement_modifier=0.75,
                hunger_modifier=1.3,
                regrowth_modifier=0.6,
                energy_modifier=0.8,
                health_modifier=-0.1,
            ),
            BiomeRegion(
                "Toendra",
                pygame.Rect(self.width - 420, 40, 360, 260),
                (180, 210, 220),
                tundra_patterns,
                movement_modifier=0.7,
                hunger_modifier=1.2,
                regrowth_modifier=0.65,
                energy_modifier=0.85,
                health_modifier=-0.05,
            ),
        ]

    def update(self, now_ms: int) -> None:
        for biome in self.biomes:
            biome.update_weather(now_ms)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(self.background_color)
        for biome in self.biomes:
            overlay = pygame.Surface((biome.rect.width, biome.rect.height), pygame.SRCALPHA)
            overlay.fill((*biome.color, 80))
            surface.blit(overlay, biome.rect.topleft)

        for water in self.water_bodies:
            for segment in water.segments:
                pygame.draw.rect(surface, water.color, segment)

        for barrier in self.barriers:
            pygame.draw.rect(surface, barrier.color, barrier.rect)

    def draw_weather_overview(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        panel_width = 320
        panel_height = 26 + 20 * len(self.biomes)
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 170))
        surface.blit(panel, (surface.get_width() // 2 - panel_width // 2, 12))

        title = font.render("Weer per biome", True, settings.BLACK)
        surface.blit(title, (surface.get_width() // 2 - title.get_width() // 2, 20))

        y_offset = 46
        for biome in self.biomes:
            _, effects = self.get_environment_context(
                biome.rect.centerx,
                biome.rect.centery,
            )
            text = font.render(
                f"{biome.name}: {effects['weather_name']} ({effects['temperature']}°C, {effects['precipitation']})",
                True,
                settings.BLACK,
            )
            surface.blit(text, (surface.get_width() // 2 - panel_width // 2 + 10, y_offset))
            y_offset += 20

    def get_biome_at(self, x: float, y: float) -> Optional[BiomeRegion]:
        point = (int(x), int(y))
        for biome in self.biomes:
            if biome.rect.collidepoint(point):
                return biome
        if self.biomes:
            return self.biomes[0]
        return None

    def get_environment_context(self, x: float, y: float) -> Tuple[Optional[BiomeRegion], Dict[str, float | int | str]]:
        biome = self.get_biome_at(x, y)
        effects: Dict[str, float | int | str]
        if biome:
            effects = biome.get_effects()
        else:
            effects = {
                "movement": 1.0,
                "hunger": 1.0,
                "regrowth": 1.0,
                "energy": 1.0,
                "health": 0.0,
                "temperature": 20,
                "precipitation": "helder",
                "weather_name": "Stabiel",
            }
        intensity = 1.0
        if self.environment_modifiers is not None:
            intensity = float(self.environment_modifiers.get("weather_intensity", 1.0))
        if intensity != 1.0:
            movement = float(effects.get("movement", 1.0))
            hunger = float(effects.get("hunger", 1.0))
            regrowth = float(effects.get("regrowth", 1.0))
            energy = float(effects.get("energy", 1.0))
            health = float(effects.get("health", 0.0))
            effects["movement"] = 1.0 + (movement - 1.0) * intensity
            effects["hunger"] = 1.0 + (hunger - 1.0) * intensity
            effects["regrowth"] = 1.0 + (regrowth - 1.0) * intensity
            effects["energy"] = 1.0 + (energy - 1.0) * intensity
            effects["health"] = 0.0 + health * intensity
        return biome, effects

    def get_regrowth_modifier(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return float(effects["regrowth"])

    def get_hunger_modifier(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return float(effects["hunger"])

    def get_energy_modifier(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return float(effects["energy"])

    def get_health_tick(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return float(effects["health"])

    def is_blocked(self, rect: pygame.Rect, include_water: bool = True) -> bool:
        for barrier in self.barriers:
            if rect.colliderect(barrier.rect):
                return True
        if include_water:
            for water in self.water_bodies:
                if water.collides(rect):
                    return True
        return False

    def resolve_entity_movement(
        self,
        entity_rect: pygame.Rect,
        previous_pos: Tuple[float, float],
        attempted_pos: Tuple[float, float],
    ) -> Tuple[float, float, bool, bool, bool]:
        attempt_x, attempt_y = attempted_pos
        max_x = self.width - entity_rect.width
        max_y = self.height - entity_rect.height
        clamped_x = max(0.0, min(max_x, attempt_x))
        clamped_y = max(0.0, min(max_y, attempt_y))
        hit_boundary_x = not math.isclose(clamped_x, attempt_x, abs_tol=1e-3)
        hit_boundary_y = not math.isclose(clamped_y, attempt_y, abs_tol=1e-3)

        entity_rect.update(int(clamped_x), int(clamped_y), entity_rect.width, entity_rect.height)

        collided = False
        if self.is_blocked(entity_rect):
            collided = True
            clamped_x, clamped_y = previous_pos
            entity_rect.update(int(clamped_x), int(clamped_y), entity_rect.width, entity_rect.height)

        return clamped_x, clamped_y, hit_boundary_x, hit_boundary_y, collided

    def random_position(
        self,
        width: int,
        height: int,
        preferred_biome: Optional[BiomeRegion] = None,
        avoid_water: bool = True,
        avoid_positions: Optional[List[Tuple[float, float]]] = None,
        min_distance: float = 0.0,
        biome_padding: int = 0,
    ) -> Tuple[float, float, Optional[BiomeRegion]]:
        attempts = 0
        x = random.randint(0, max(1, self.width - width))
        y = random.randint(0, max(1, self.height - height))
        avoid_positions = avoid_positions or []

        while attempts < 260:
            if preferred_biome is None and not self.biomes:
                biome = None
            else:
                biome = preferred_biome or random.choice(self.biomes)
            if biome:
                spawn_rect = biome.rect.inflate(-biome_padding, -biome_padding)
                if spawn_rect.width <= 0 or spawn_rect.height <= 0:
                    spawn_rect = biome.rect
            else:
                spawn_rect = pygame.Rect(0, 0, self.width, self.height)

            x = random.randint(spawn_rect.left, max(spawn_rect.left, spawn_rect.right - width))
            y = random.randint(spawn_rect.top, max(spawn_rect.top, spawn_rect.bottom - height))
            candidate = pygame.Rect(x, y, width, height)

            if candidate.right > self.width or candidate.bottom > self.height:
                attempts += 1
                continue
            if self.is_blocked(candidate, include_water=avoid_water):
                attempts += 1
                continue

            if avoid_positions and min_distance > 0:
                center = (candidate.centerx, candidate.centery)
                too_close = False
                for px, py in avoid_positions:
                    if math.hypot(center[0] - px, center[1] - py) < min_distance:
                        too_close = True
                        break
                if too_close:
                    attempts += 1
                    continue

            return float(x), float(y), self.get_biome_at(candidate.centerx, candidate.centery)

            
        return float(x), float(y), self.get_biome_at(x, y)

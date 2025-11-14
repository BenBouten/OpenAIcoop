"""World generation and biome management for the evolution simulation."""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

import pygame

from ..config import settings


from .map_generator import MapBlueprint, generate_map
from .types import Barrier, BiomeRegion, WaterBody, WeatherPattern


class World:
    def __init__(self, width: int, height: int, world_type: Optional[str] = None):
        self.width = width
        self.height = height
        self.background_color = (228, 222, 208)
        self.barriers: List[Barrier] = []
        self.water_bodies: List[WaterBody] = []
        self.biomes: List[BiomeRegion] = []
        self.vegetation_masks: List[pygame.Rect] = []
        self.world_type = self._normalise_world_type(world_type)
        self._generate()

    @staticmethod
    def _normalise_world_type(world_type: Optional[str]) -> str:
        if not world_type:
            return "Rift Valley"
        cleaned = world_type.strip().lower().replace("_", " ")
        cleaned = cleaned.replace("–", "-")
        if cleaned in {"archipelago", "archipel"}:
            return "Archipelago"
        if cleaned in {"desert-jungle split", "desert jungle split"}:
            return "Desert–Jungle Split"
        return "Rift Valley"

    def set_world_type(self, world_type: Optional[str]) -> None:
        self.world_type = self._normalise_world_type(world_type)
        self._generate()

    def _generate(self) -> None:
        blueprint: MapBlueprint = generate_map(self.world_type, self.width, self.height)
        self.background_color = blueprint.background_color
        self.barriers = list(blueprint.barriers)
        self.water_bodies = list(blueprint.water_bodies)
        self.biomes = list(blueprint.biomes)
        self.vegetation_masks = list(blueprint.vegetation_masks)

    def regenerate(self) -> None:
        self._generate()

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
            effects = biome.get_effects()
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

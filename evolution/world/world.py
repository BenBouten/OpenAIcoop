"""World generation and biome management for the evolution simulation."""
from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector2

from ..config import settings
from ..rendering.ocean_renderer import OceanRenderer  # ⬅️ NIEUW

from .ocean_physics import OceanPhysics
from .ocean_world import BubbleColumn, DepthLayer, OceanBlueprint, RadVentField, build_ocean_blueprint
from .types import Barrier, BiomeRegion, WaterBody, WeatherPattern


class World:
    def __init__(
        self,
        width: int,
        height: int,
        world_type: Optional[str] = None,
        environment_modifiers: Optional[Dict[str, float]] = None,
    ):
        self.width = width
        self.height = height
        self.background_color = (6, 18, 42)
        self.barriers: List[Barrier] = []
        self.water_bodies: List[WaterBody] = []
        self.biomes: List[BiomeRegion] = []
        self.layers: List[DepthLayer] = []
        self.rad_vents: List[RadVentField] = []
        self.bubble_columns: List[BubbleColumn] = []
        self.vegetation_masks: List[pygame.Rect] = []
        self.carcasses: List[object] = []
        self.environment_modifiers = environment_modifiers
        self.world_type = "Alien Ocean"
        self.ocean = OceanPhysics(self.width, self.height - settings.OCEAN_SURFACE_Y, surface_y=settings.OCEAN_SURFACE_Y)
        self._background_surface: Optional[pygame.Surface] = None
        self._label_font: Optional[pygame.font.Font] = None
        self._time_seconds: float = 0.0
        self._layer_lookup: List[Tuple[int, int, DepthLayer]] = []

        # 🌊 Nieuwe renderer voor de volledige oceaanachtergrond
        self._renderer = OceanRenderer(self.width, self.height)

        self._last_update_ms: Optional[int] = None
        self._bubble_rng = random.Random(4242)
        self._generate()

    @property
    def static_background(self) -> Optional[pygame.Surface]:
        """Return the cached static background surface."""

        return getattr(self._renderer, "static_background", None)

    def set_environment_modifiers(self, modifiers: Dict[str, float]) -> None:
        self.environment_modifiers = modifiers

    def set_world_type(self, world_type: Optional[str]) -> None:
        # De oceaanwereld is de enige beschikbare kaart en fungeert als
        # vaste sandbox voor de simulatie. We accepteren de call zodat
        # bestaande code paden blijven werken.
        self.world_type = "Alien Ocean"
        self._generate()

    def _generate(self) -> None:
        blueprint: OceanBlueprint = build_ocean_blueprint(self.width, self.height)
        self.background_color = blueprint.background_color
        self.barriers = list(blueprint.barriers)
        self.water_bodies = list(blueprint.water_bodies)
        self.layers = list(blueprint.layers)
        self.biomes = [layer.biome for layer in self.layers]
        self.vegetation_masks = list(blueprint.vegetation_masks)
        self.rad_vents = list(blueprint.vents)
        self.bubble_columns = list(blueprint.bubble_columns)
        self.ocean = OceanPhysics(self.width, self.height - settings.OCEAN_SURFACE_Y, surface_y=settings.OCEAN_SURFACE_Y)
        self._background_surface = self._render_background()
        self._rebuild_layer_lookup()
        self._last_update_ms = None

    def regenerate(self) -> None:
        self._generate()

    def _render_background(self) -> Optional[pygame.Surface]:
        if not self.layers:
            return None
        background = pygame.Surface((self.width, self.height))
        for layer in self.layers:
            rect = layer.biome.rect
            segment = pygame.Surface(rect.size)
            self._draw_gradient(segment, layer.top_color, layer.bottom_color)
            background.blit(segment, rect.topleft)
        return background

    @staticmethod
    def _draw_gradient(surface: pygame.Surface, top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> None:
        height = surface.get_height()
        width = surface.get_width()
        if height <= 0 or width <= 0:
            surface.fill(top_color)
            return
        for row in range(height):
            ratio = row / max(1, height - 1)
            color = tuple(
                int(top_color[idx] + (bottom_color[idx] - top_color[idx]) * ratio)
                for idx in range(3)
            )
            pygame.draw.line(surface, color, (0, row), (width, row))

    def _draw_layer_overlays(self, surface: pygame.Surface) -> None:
        if not self.layers:
            return
        for layer in self.layers:
            rect = layer.biome.rect
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            step = max(18, rect.height // 36)
            offset = math.sin(self._time_seconds * layer.caustic_speed) * layer.caustic_density
            for row in range(0, rect.height, step):
                y = (row + int(offset)) % max(1, rect.height)
                alpha = max(12, min(70, 70 - row // 2))
                pygame.draw.line(
                    overlay,
                    (*layer.caustic_tint, alpha),
                    (0, y),
                    (rect.width, y),
                    2,
            )
            surface.blit(overlay, rect.topleft, special_flags=pygame.BLEND_RGB_ADD)

    def _draw_light_shafts(self, surface: pygame.Surface) -> None:
        columns = 6
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for idx in range(columns):
            width = max(90, self.width // (columns * 2))
            center = int((idx + 0.5) * self.width / columns)
            offset = math.sin(self._time_seconds * 0.22 + idx * 0.6) * 60
            rect = pygame.Rect(center - width // 2 + int(offset), 0, width, self.height)
            pygame.draw.rect(
                overlay,
                (40, 110, 210, 18),
                rect,
                border_radius=width // 2,
            )
        surface.blit(overlay, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    def _draw_layer_labels(
        self,
        surface: pygame.Surface,
        *,
        offset: Tuple[int, int] = (0, 0),
        viewport: Optional[pygame.Rect] = None,
    ) -> None:
        if not self.layers:
            return
        if self._label_font is None:
            self._label_font = pygame.font.Font(None, 20)
        for layer in self.layers:
            if viewport is not None and not layer.biome.rect.colliderect(viewport):
                continue
            weather = layer.biome.active_weather.name if layer.biome.active_weather else "Stabiel"
            label = f"{layer.biome.name} – {weather}"
            text = self._label_font.render(label, True, (220, 235, 255))
            position = (
                24 - offset[0],
                layer.biome.rect.centery - text.get_height() // 2 - offset[1],
            )
            surface.blit(text, position)

    def _draw_rad_vent(self, surface: pygame.Surface, vent: RadVentField) -> None:
        radius = max(20, vent.radius)
        overlay = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        alpha = int(150 * vent.intensity)
        pygame.draw.circle(overlay, (*vent.color, alpha), (radius, radius), radius)
        pygame.draw.circle(
            overlay,
            (255, 255, 255, max(30, int(alpha * 0.6))),
            (radius, radius),
            int(radius * 0.45),
            3,
        )
        surface.blit(
            overlay,
            (vent.center[0] - radius, vent.center[1] - radius),
            special_flags=pygame.BLEND_ADD,
        )

    def update(self, now_ms: int) -> None:
        self._time_seconds = now_ms / 1000.0
        delta_seconds = 0.0
        if self._last_update_ms is not None:
            delta_seconds = max(0.0, (now_ms - self._last_update_ms) / 1000.0)
        self._last_update_ms = now_ms
        self.ocean.update(now_ms)
        for vent in self.rad_vents:
            vent.update(self._time_seconds)
        for column in self.bubble_columns:
            column.update(delta_seconds, self._bubble_rng)
        for biome in self.biomes:
            biome.update_weather(now_ms)

    def draw_static_region(self, surface: pygame.Surface, region: pygame.Rect) -> None:
        """Render static layers for a region into ``surface``."""

        surface.fill(self.background_color)

        background = self.static_background
        if background is not None:
            surface.blit(background, (0, 0), region)

        for water in self.water_bodies:
            for segment in water.segments:
                if not segment.colliderect(region):
                    continue
                local_rect = segment.move(-region.x, -region.y)
                pygame.draw.rect(surface, water.color, local_rect)

        for barrier in self.barriers:
            if not barrier.rect.colliderect(region):
                continue
            local_rect = barrier.rect.move(-region.x, -region.y)
            pygame.draw.rect(surface, barrier.color, local_rect)

    def draw_dynamic_layers(
        self, surface: pygame.Surface, viewport: pygame.Rect, offset: Tuple[int, int]
    ) -> None:
        """Draw dynamic overlays that should be re-rendered each frame."""

        self._renderer.draw_waves_region(surface, self._time_seconds, viewport, offset)

        for vent in self.rad_vents:
            radius = max(20, vent.radius)
            vent_rect = pygame.Rect(
                vent.center[0] - radius,
                vent.center[1] - radius,
                radius * 2,
                radius * 2,
            )
            if not vent_rect.colliderect(viewport):
                continue
            self._renderer.draw_rad_vent(
                surface,
                vent.center,
                radius=radius,
                color=vent.color,
                intensity=vent.intensity,
                offset=offset,
            )

        for column in self.bubble_columns:
            col_rect = pygame.Rect(
                column.base[0] - column.width,
                column.base[1] - column.height,
                column.width * 2,
                column.height,
            )
            if col_rect.colliderect(viewport):
                column.draw(surface, offset=offset)

        self._draw_layer_labels(surface, offset=offset, viewport=viewport)

    def _rebuild_layer_lookup(self) -> None:
        """Cache y-ranges for each layer for fast biome queries."""

        self._layer_lookup = []
        for layer in self.layers:
            rect = layer.biome.rect
            self._layer_lookup.append((rect.top, rect.bottom, layer))
        self._layer_lookup.sort(key=lambda item: item[0])

    def draw(
        self,
        surface: pygame.Surface,
        viewport: Optional[pygame.Rect] = None,
        *,
        offset: Tuple[int, int] = (0, 0),
    ) -> None:
        """Compatibility wrapper that renders static + dynamic layers."""

        region = viewport or pygame.Rect(0, 0, self.width, self.height)
        self.draw_static_region(surface, region)
        self.draw_dynamic_layers(surface, region, offset)



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
                f"{biome.name}: {effects['weather_name']} "
                f"({effects['temperature']}°C, {effects['precipitation']})",
                True,
                settings.BLACK,
            )
            surface.blit(
                text,
                (surface.get_width() // 2 - panel_width // 2 + 10, y_offset),
            )
            y_offset += 20


    # ------------------------------------------------------------------ #
    #  ALLES HIERONDER: gameplay / logic (ONGEWIJZIGD)
    # ------------------------------------------------------------------ #

    def get_biome_at(self, x: float, y: float) -> Optional[BiomeRegion]:
        layer = self.get_layer_at(y)
        if layer:
            biome = layer.biome
            if biome.contains(x, y):
                return biome
        if self.biomes:
            return self.biomes[0]
        return None

    def get_layer_at(self, y: float) -> Optional[DepthLayer]:
        """Return the depth layer intersecting a vertical coordinate."""

        if not self._layer_lookup:
            return self.layers[0] if self.layers else None
        for top, bottom, layer in self._layer_lookup:
            if top <= y < bottom:
                return layer
        return self._layer_lookup[-1][2]

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
        self.ocean.enrich_effects(effects, y)
        return biome, effects

    def get_mutation_multiplier(self, x: float, y: float) -> float:
        """Return a distance-weighted mutation multiplier based on nearby vents."""

        multiplier = 1.0
        for vent in self.rad_vents:
            dx = x - vent.center[0]
            dy = y - vent.center[1]
            dist = math.hypot(dx, dy)
            if dist >= vent.radius or vent.radius <= 0:
                continue
            influence = 1.0 - (dist / vent.radius)
            multiplier += vent.mutation_bonus * max(0.0, influence)
        return min(multiplier, 4.0)

    def sample_environment(self, x: float, y: float) -> Dict[str, float]:
        """Collect sensory-friendly environment data for the given coordinate."""

        depth = max(0.0, min(float(self.height), float(y)))
        biome, biome_effects = self.get_environment_context(x, depth)
        fluid = self.ocean.properties_at(depth) if self.ocean else None
        mutation_mult = self.get_mutation_multiplier(x, y)

        data = {
            "depth_norm": depth / float(self.height) if self.height else 0.0,
            "biome_movement": float(biome_effects.get("movement", 1.0)),
            "biome_hunger": float(biome_effects.get("hunger", 1.0)),
            "biome_regrowth": float(biome_effects.get("regrowth", 1.0)),
            "biome_health": float(biome_effects.get("health", 0.0)),
            "mutation_multiplier": float(mutation_mult),
        }

        if fluid:
            data.update(
                {
                    "density": float(fluid.density),
                    "drag": float(fluid.drag),
                    "light": float(fluid.light),
                    "current_x": float(fluid.current.x),
                    "current_y": float(fluid.current.y),
                    "temperature": float(fluid.temperature),
                    "pressure": float(fluid.pressure),
                }
            )

        return data

    def apply_fluid_dynamics(
        self, lifeform, thrust: Vector2, dt: float, *, max_speed: float
    ) -> Tuple[Vector2, Optional[object]]:
        if self.ocean:
            return self.ocean.integrate_body(lifeform, thrust, dt, max_speed=max_speed)
        position = Vector2(lifeform.x, lifeform.y) + thrust * dt
        return position, None

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
        clamped_y = max(float(settings.OCEAN_SURFACE_Y), min(max_y, attempt_y))
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
            if biome and not biome.contains(candidate.centerx, candidate.centery):
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

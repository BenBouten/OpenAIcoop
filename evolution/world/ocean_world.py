"""Procedural generator for the layered alien ocean world."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import pygame
from pygame.math import Vector2

from .types import Barrier, BiomeRegion, WaterBody, WeatherPattern

Color = Tuple[int, int, int]


@dataclass(frozen=True)
class DepthLayer:
    """Visual & biome information for a single depth band."""

    biome: BiomeRegion
    top_color: Color
    bottom_color: Color
    caustic_tint: Color
    caustic_speed: float
    caustic_density: int
    parallax: float


@dataclass
class RadVentField:
    """Radioactive vent hotspot that pulses with neon light."""

    center: Tuple[int, int]
    radius: int
    pulse_speed: float
    mutation_bonus: float
    color: Color = (255, 229, 128)
    phase: float = field(default_factory=lambda: random.random() * math.tau)
    intensity: float = 0.0

    def update(self, time_seconds: float) -> None:
        wave = math.sin(time_seconds * self.pulse_speed + self.phase)
        self.intensity = 0.5 + 0.5 * (wave + 1.0) / 2.0


@dataclass
class OceanBlueprint:
    """Container describing the generated ocean layout."""

    background_color: Color
    layers: List[DepthLayer]
    barriers: List[Barrier]
    water_bodies: List[WaterBody]
    vegetation_masks: List[pygame.Rect]
    vents: List[RadVentField]
    bubble_columns: List["BubbleColumn"]


@dataclass
class BubbleColumn:
    """Gentle stream of bubbles that drifts upward as decoration."""

    base: Tuple[int, int]
    width: int
    height: int
    spawn_interval: float
    rise_speed: float
    max_radius: int
    drift: float
    color: Color = (195, 225, 255)
    bubbles: List[Tuple[Vector2, float, float]] = field(default_factory=list)
    _time_accumulator: float = 0.0

    def update(self, dt: float, rng: random.Random) -> None:
        if dt <= 0:
            return
        self._time_accumulator += dt
        while self._time_accumulator >= self.spawn_interval:
            self._time_accumulator -= self.spawn_interval
            self._spawn_bubble(rng)

        target_top = self.base[1] - self.height
        alive: List[Tuple[Vector2, float, float]] = []
        for position, velocity, radius in self.bubbles:
            position.y -= velocity * dt
            position.x += math.sin(position.y * 0.02) * self.drift * dt
            velocity *= 0.995
            if position.y + radius > target_top:
                alive.append((position, velocity, radius))
        self.bubbles = alive[-80:]

    def draw(self, surface: pygame.Surface) -> None:
        if not self.bubbles:
            return
        for position, _, radius in self.bubbles:
            pygame.draw.circle(
                surface,
                self.color,
                (int(position.x), int(position.y)),
                max(1, int(radius)),
                width=1,
            )

    def _spawn_bubble(self, rng: random.Random) -> None:
        radius = rng.uniform(1.5, float(self.max_radius))
        x = rng.uniform(self.base[0] - self.width / 2, self.base[0] + self.width / 2)
        y = float(self.base[1])
        rise = rng.uniform(self.rise_speed * 0.5, self.rise_speed * 1.35)
        self.bubbles.append((Vector2(x, y), rise, radius))


def build_ocean_blueprint(width: int, height: int) -> OceanBlueprint:
    """Assemble the layered sideways ocean described in the design doc."""

    rng = random.Random(1337)
    layer_specs = _layer_specs()
    layers: List[DepthLayer] = []
    y_cursor = 0
    remaining_layers = len(layer_specs)

    for index, spec in enumerate(layer_specs):
        remaining_layers = len(layer_specs) - index - 1
        min_remaining = remaining_layers * _MIN_LAYER_HEIGHT
        target_height = max(_MIN_LAYER_HEIGHT, int(height * spec["ratio"]))
        available_height = height - y_cursor - min_remaining
        layer_height = min(target_height, available_height) if remaining_layers else height - y_cursor
        layer_height = max(_MIN_LAYER_HEIGHT, layer_height)
        rect = pygame.Rect(0, y_cursor, width, min(layer_height, height - y_cursor))
        biome = _build_biome(spec["name"], rect, spec)
        layers.append(
            DepthLayer(
                biome=biome,
                top_color=spec["top_color"],
                bottom_color=spec["bottom_color"],
                caustic_tint=spec["caustic_tint"],
                caustic_speed=spec["caustic_speed"],
                caustic_density=spec["caustic_density"],
                parallax=spec["parallax"],
            )
        )
        y_cursor += rect.height

    barriers = _build_side_cliffs(width, height, rng)
    barriers += _build_seafloor_ridges(width, height, rng)
    barriers += _build_cave_systems(width, height, rng)
    vents = _build_rad_vents(layers, width, rng)
    vegetation_masks = _build_vegetation_masks(layers, width, rng)
    bubble_columns = _build_bubble_columns(width, height, rng)
    background_color = layers[0].top_color if layers else (6, 18, 42)

    return OceanBlueprint(
        background_color=background_color,
        layers=layers,
        barriers=barriers,
        water_bodies=[],
        vegetation_masks=vegetation_masks,
        vents=vents,
        bubble_columns=bubble_columns,
    )


_MIN_LAYER_HEIGHT = 1080


def _layer_specs() -> List[dict]:
    return [
        {
            "name": "Surface",
            "ratio": 0.12,
            "base_color": (78, 181, 214),
            "top_color": (118, 212, 233),
            "bottom_color": (22, 66, 124),
            "caustic_tint": (210, 255, 255),
            "caustic_speed": 0.25,
            "caustic_density": 65,
            "parallax": 1.0,
            "movement": 1.15,
            "hunger": 0.85,
            "regrowth": 1.25,
            "energy": 1.15,
            "health": 0.05,
        },
        {
            "name": "Sunlit",
            "ratio": 0.2,
            "base_color": (40, 130, 190),
            "top_color": (34, 118, 176),
            "bottom_color": (12, 54, 120),
            "caustic_tint": (140, 230, 255),
            "caustic_speed": 0.32,
            "caustic_density": 55,
            "parallax": 0.85,
            "movement": 1.05,
            "hunger": 0.92,
            "regrowth": 1.15,
            "energy": 1.05,
            "health": 0.02,
        },
        {
            "name": "Twilight",
            "ratio": 0.22,
            "base_color": (24, 92, 150),
            "top_color": (20, 74, 130),
            "bottom_color": (10, 38, 82),
            "caustic_tint": (120, 210, 255),
            "caustic_speed": 0.38,
            "caustic_density": 48,
            "parallax": 0.7,
            "movement": 0.95,
            "hunger": 1.05,
            "regrowth": 1.0,
            "energy": 1.0,
            "health": 0.0,
        },
        {
            "name": "Midnight",
            "ratio": 0.24,
            "base_color": (18, 52, 96),
            "top_color": (14, 40, 76),
            "bottom_color": (8, 18, 48),
            "caustic_tint": (90, 180, 255),
            "caustic_speed": 0.44,
            "caustic_density": 42,
            "parallax": 0.55,
            "movement": 0.85,
            "hunger": 1.15,
            "regrowth": 0.85,
            "energy": 0.95,
            "health": -0.05,
        },
        {
            "name": "Abyss",
            "ratio": 0.22,
            "base_color": (6, 14, 32),
            "top_color": (8, 16, 40),
            "bottom_color": (2, 6, 18),
            "caustic_tint": (70, 120, 220),
            "caustic_speed": 0.55,
            "caustic_density": 36,
            "parallax": 0.45,
            "movement": 0.75,
            "hunger": 1.25,
            "regrowth": 0.6,
            "energy": 0.8,
            "health": -0.1,
        },
    ]


def _build_biome(name: str, rect: pygame.Rect, spec: dict) -> BiomeRegion:
    patterns = _weather_for_layer(name)
    biome = BiomeRegion(
        name,
        rect,
        spec["base_color"],
        patterns,
        movement_modifier=spec["movement"],
        hunger_modifier=spec["hunger"],
        regrowth_modifier=spec["regrowth"],
        energy_modifier=spec["energy"],
        health_modifier=spec["health"],
    )
    biome.mask = None
    biome.mask_offset = (rect.left, rect.top)
    return biome


def _weather_for_layer(name: str) -> List[WeatherPattern]:
    if name == "Surface":
        return [
            WeatherPattern("Rustige golfslag", 28, "helder", movement_modifier=1.2, regrowth_modifier=1.2, energy_modifier=1.2),
            WeatherPattern("Springtij", 25, "dauw", movement_modifier=1.05, hunger_modifier=0.9, regrowth_modifier=1.3),
            WeatherPattern(
                "Stormschuim",
                24,
                "storm",
                movement_modifier=0.9,
                hunger_modifier=1.0,
                regrowth_modifier=1.1,
                energy_modifier=0.95,
                health_tick=-0.05,
                duration_range=(9000, 15000),
            ),
        ]
    if name == "Sunlit":
        return [
            WeatherPattern("Caustic dans", 22, "helder", movement_modifier=1.1, hunger_modifier=0.95, regrowth_modifier=1.1),
            WeatherPattern("Planktonsluier", 20, "mist", movement_modifier=0.92, hunger_modifier=1.05, regrowth_modifier=1.25),
            WeatherPattern("Zijstroming", 18, "wind", movement_modifier=1.0, hunger_modifier=1.0, regrowth_modifier=1.05, energy_modifier=1.05),
        ]
    if name == "Twilight":
        return [
            WeatherPattern("Rad-vent pulse", 14, "gas", movement_modifier=0.95, hunger_modifier=1.05, energy_modifier=1.0, health_tick=0.02),
            WeatherPattern("Traagslopers", 12, "stil", movement_modifier=0.85, hunger_modifier=1.1, regrowth_modifier=0.95),
            WeatherPattern("Schuine drift", 10, "wind", movement_modifier=1.05, hunger_modifier=1.0, energy_modifier=1.05),
        ]
    if name == "Midnight":
        return [
            WeatherPattern("Stromingswissel", 6, "wind", movement_modifier=0.85, hunger_modifier=1.15, energy_modifier=0.95, health_tick=-0.03),
            WeatherPattern("Ionische stilte", 5, "stil", movement_modifier=0.8, hunger_modifier=1.1, regrowth_modifier=0.8, energy_modifier=0.9),
            WeatherPattern("Benthische golf", 7, "trillingen", movement_modifier=0.95, hunger_modifier=1.0, regrowth_modifier=0.9, energy_modifier=1.0),
        ]
    return [
        WeatherPattern("Abyssale rust", 2, "donker", movement_modifier=0.7, hunger_modifier=1.2, regrowth_modifier=0.5, energy_modifier=0.75, health_tick=-0.06),
        WeatherPattern("Bioluminescente storm", 4, "lichtflitsen", movement_modifier=0.8, hunger_modifier=1.1, regrowth_modifier=0.6, energy_modifier=0.85),
    ]


def _build_side_cliffs(width: int, height: int, rng: random.Random) -> List[Barrier]:
    color = (18, 24, 42)
    cliffs: List[Barrier] = []
    step_height = 320
    for side in (-1, 1):
        y = 0
        while y < height:
            seg_height = min(height - y, rng.randint(step_height - 80, step_height + 140))
            seg_width = rng.randint(120, 220)
            ledge_height = rng.randint(30, 90)
            if side == -1:
                left = 0
            else:
                left = width - seg_width
            pocket_top = y + rng.randint(40, max(50, seg_height - 120))
            # Split the cliff into an upper and lower piece to leave a recessed alcove.
            upper_height = max(0, pocket_top - y)
            lower_height = max(0, seg_height - upper_height - ledge_height)
            if upper_height > 0:
                cliffs.append(Barrier(pygame.Rect(left, y, seg_width, upper_height), color, "basalt cliff"))
            if lower_height > 0:
                lower_top = pocket_top + ledge_height
                cliffs.append(
                    Barrier(
                        pygame.Rect(left, lower_top, seg_width, lower_height),
                        color,
                        "basalt cliff",
                    )
                )
            y += seg_height
    return cliffs


def _build_seafloor_ridges(width: int, height: int, rng: random.Random) -> List[Barrier]:
    ridges: List[Barrier] = []
    baseline = height - rng.randint(140, 220)
    x = 0
    while x < width:
        ridge_width = rng.randint(180, 360)
        ridge_height = rng.randint(180, 420)
        ridge_height += int(math.sin(x * 0.02) * 40)
        ridge_left = max(0, min(width - ridge_width, x + rng.randint(-60, 90)))
        ridge_top = max(0, baseline - ridge_height + rng.randint(-40, 40))
        ridge_rect = pygame.Rect(ridge_left, ridge_top, ridge_width, height - ridge_top)
        ridges.append(Barrier(ridge_rect, (20, 30, 48), "volcanic ridge"))
        x += ridge_width - rng.randint(-40, 120)
    return ridges


def _build_cave_systems(width: int, height: int, rng: random.Random) -> List[Barrier]:
    caves: List[Barrier] = []
    band_top = int(height * 0.55)
    band_bottom = height - 40
    attempts = 5
    for _ in range(attempts):
        span = rng.randint(220, 360)
        center = rng.randint(int(width * 0.15), int(width * 0.85))
        roof_height = rng.randint(90, 140)
        throat = rng.randint(60, 100)
        roof_top = rng.randint(band_top, band_bottom - roof_height - 40)
        roof_rect = pygame.Rect(center - span // 2, roof_top, span, roof_height)
        caves.append(Barrier(roof_rect, (22, 28, 54), "cave ceiling"))

        left_pillar_width = rng.randint(40, 80)
        right_pillar_width = rng.randint(40, 80)
        pillar_height = rng.randint(roof_height - 30, roof_height + 80)
        left_pillar = pygame.Rect(roof_rect.left - left_pillar_width, roof_top + throat, left_pillar_width, pillar_height)
        right_pillar = pygame.Rect(roof_rect.right, roof_top + throat, right_pillar_width, pillar_height)
        caves.append(Barrier(left_pillar, (16, 22, 46), "cave buttress"))
        caves.append(Barrier(right_pillar, (16, 22, 46), "cave buttress"))
    return caves


def _build_bubble_columns(width: int, height: int, rng: random.Random) -> List[BubbleColumn]:
    columns: List[BubbleColumn] = []
    count = rng.randint(5, 8)
    for _ in range(count):
        base_x = rng.randint(int(width * 0.08), int(width * 0.92))
        base_y = rng.randint(int(height * 0.55), height - 30)
        columns.append(
            BubbleColumn(
                base=(base_x, base_y),
                width=rng.randint(24, 48),
                height=rng.randint(320, 520),
                spawn_interval=rng.uniform(0.35, 0.85),
                rise_speed=rng.uniform(24.0, 40.0),
                max_radius=rng.randint(3, 6),
                drift=rng.uniform(4.0, 12.0),
            )
        )
    return columns


def _build_rad_vents(layers: Sequence[DepthLayer], width: int, rng: random.Random) -> List[RadVentField]:
    vents: List[RadVentField] = []
    for layer in layers:
        if layer.biome.name not in {"Twilight", "Midnight"}:
            continue
        count = 2 if layer.biome.name == "Twilight" else 1
        for _ in range(count):
            center_x = rng.randint(int(width * 0.2), int(width * 0.8))
            center_y = rng.randint(layer.biome.rect.top + 120, layer.biome.rect.bottom - 120)
            radius = rng.randint(180, 260)
            vents.append(
                RadVentField(
                    center=(center_x, center_y),
                    radius=radius,
                    pulse_speed=rng.uniform(0.35, 0.7),
                    mutation_bonus=0.35 if layer.biome.name == "Twilight" else 0.5,
                )
            )
    return vents


def _build_vegetation_masks(
    layers: Sequence[DepthLayer], width: int, rng: random.Random
) -> List[pygame.Rect]:
    masks: List[pygame.Rect] = []
    for layer in layers:
        if layer.biome.name not in {"Surface", "Sunlit", "Twilight"}:
            continue
        attempts = rng.randint(2, 4)
        for _ in range(attempts):
            mask_width = rng.randint(int(width * 0.15), int(width * 0.3))
            mask_height = rng.randint(int(layer.biome.rect.height * 0.25), int(layer.biome.rect.height * 0.6))
            left = rng.randint(40, max(41, width - mask_width - 40))
            top = rng.randint(
                layer.biome.rect.top + 40,
                max(layer.biome.rect.top + 40, layer.biome.rect.bottom - mask_height - 40),
            )
            masks.append(pygame.Rect(left, top, mask_width, mask_height))
    return masks


__all__ = [
    "DepthLayer",
    "OceanBlueprint",
    "RadVentField",
    "BubbleColumn",
    "build_ocean_blueprint",
]

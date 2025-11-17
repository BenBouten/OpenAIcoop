"""Procedural generator for the layered alien ocean world."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import pygame

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
    vents = _build_rad_vents(layers, width, rng)
    vegetation_masks = _build_vegetation_masks(layers, width, rng)
    background_color = layers[0].top_color if layers else (6, 18, 42)

    return OceanBlueprint(
        background_color=background_color,
        layers=layers,
        barriers=barriers,
        water_bodies=[],
        vegetation_masks=vegetation_masks,
        vents=vents,
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
            if side == -1:
                left = 0
            else:
                left = width - seg_width
            rect = pygame.Rect(left, y, seg_width, seg_height)
            cliffs.append(Barrier(rect, color, "basalt cliff"))
            y += seg_height
    return cliffs


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
    "build_ocean_blueprint",
]

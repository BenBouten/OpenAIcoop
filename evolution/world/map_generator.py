"""Procedural map generation helpers for different world types."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import pygame

from .organic import generate_blob_mask
from .types import Barrier, BiomeRegion, WaterBody, WeatherPattern


Color = Tuple[int, int, int]


@dataclass
class MapBlueprint:
    """Container describing the generated layout for a world map."""

    background_color: Color
    barriers: List[Barrier]
    water_bodies: List[WaterBody]
    biomes: List[BiomeRegion]
    vegetation_masks: List[pygame.Rect]


def normalize_world_type(world_type: str | None) -> str:
    if not world_type:
        return "Rift Valley"
    cleaned = world_type.strip().lower().replace("_", " ")
    cleaned = cleaned.replace("–", "-")
    if cleaned in {"abyssal ocean", "ocean", "ocean depths", "deep ocean"}:
        return "Abyssal Ocean"
    if cleaned in {"archipelago", "archipel"}:
        return "Archipelago"
    if cleaned in {"desert-jungle split", "desert jungle split"}:
        return "Desert–Jungle Split"
    return "Rift Valley"


def _create_border_barriers(width: int, height: int, thickness: int = 12) -> List[Barrier]:
    return [
        Barrier(pygame.Rect(0, 0, width, thickness)),
        Barrier(pygame.Rect(0, 0, thickness, height)),
        Barrier(pygame.Rect(0, height - thickness, width, thickness)),
        Barrier(pygame.Rect(width - thickness, 0, thickness, height)),
    ]


def _rect_from_bounds(
    left: int, top: int, right: int, bottom: int, max_width: int, max_height: int
) -> pygame.Rect:
    left = max(0, min(left, max_width - 10))
    top = max(0, min(top, max_height - 10))
    right = max(left + 10, min(right, max_width))
    bottom = max(top + 10, min(bottom, max_height))
    return pygame.Rect(left, top, right - left, bottom - top)


def _create_biome_region(
    name: str,
    rect: pygame.Rect,
    color: Color,
    patterns: List[WeatherPattern],
    *,
    movement_modifier: float = 1.0,
    hunger_modifier: float = 1.0,
    regrowth_modifier: float = 1.0,
    energy_modifier: float = 1.0,
    health_modifier: float = 0.0,
    mask_complexity: int = 12,
    mask_irregularity: float = 0.35,
    mask_variation: float = 0.35,
) -> BiomeRegion:
    mask = generate_blob_mask(
        max(12, rect.width),
        max(12, rect.height),
        complexity=mask_complexity,
        angular_variation=mask_irregularity,
        radial_variation=mask_variation,
    )
    region = BiomeRegion(
        name,
        rect,
        color,
        patterns,
        movement_modifier=movement_modifier,
        hunger_modifier=hunger_modifier,
        regrowth_modifier=regrowth_modifier,
        energy_modifier=energy_modifier,
        health_modifier=health_modifier,
    )
    region.mask = mask
    region.mask_offset = (rect.left, rect.top)
    return region


def _build_weather_patterns() -> Dict[str, List[WeatherPattern]]:
    return {
        "temperate": [
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
        ],
        "forest": [
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
        ],
        "desert": [
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
        ],
        "tundra": [
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
        ],
        "marsh": [
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
        ],
        "tropical": [
            WeatherPattern(
                "Tropische bui",
                28,
                "regen",
                movement_modifier=0.75,
                hunger_modifier=0.95,
                regrowth_modifier=1.6,
                energy_modifier=0.95,
                health_tick=0.05,
                duration_range=(9000, 16000),
            ),
            WeatherPattern(
                "Vochtige hitte",
                31,
                "benauwd",
                movement_modifier=0.8,
                hunger_modifier=1.1,
                regrowth_modifier=1.45,
                energy_modifier=0.9,
            ),
            WeatherPattern(
                "Zonnestraal",
                27,
                "helder",
                movement_modifier=0.95,
                hunger_modifier=0.9,
                regrowth_modifier=1.3,
                energy_modifier=1.05,
            ),
        ],
        "savanna": [
            WeatherPattern(
                "Droge bries",
                29,
                "droog",
                movement_modifier=1.05,
                hunger_modifier=0.95,
                regrowth_modifier=1.05,
                energy_modifier=1.05,
            ),
            WeatherPattern(
                "Warme regen",
                24,
                "regen",
                movement_modifier=0.95,
                hunger_modifier=1.0,
                regrowth_modifier=1.25,
                energy_modifier=0.95,
            ),
            WeatherPattern(
                "Hittesluier",
                33,
                "heet",
                movement_modifier=0.85,
                hunger_modifier=1.15,
                regrowth_modifier=0.9,
                energy_modifier=0.85,
                duration_range=(9000, 15000),
            ),
        ],
        "coastal": [
            WeatherPattern(
                "Zeebries",
                24,
                "winderig",
                movement_modifier=1.0,
                hunger_modifier=0.95,
                regrowth_modifier=1.2,
                energy_modifier=1.0,
            ),
            WeatherPattern(
                "Moesson",
                22,
                "storm",
                movement_modifier=0.75,
                hunger_modifier=1.05,
                regrowth_modifier=1.55,
                energy_modifier=0.9,
                duration_range=(8000, 15000),
            ),
            WeatherPattern(
                "Heldere kust",
                26,
                "helder",
                movement_modifier=1.05,
                hunger_modifier=0.9,
                regrowth_modifier=1.3,
                energy_modifier=1.05,
            ),
        ],
        "sunlit": [
            WeatherPattern(
                "Kalme golfslag",
                24,
                "helder",
                movement_modifier=1.1,
                hunger_modifier=0.85,
                regrowth_modifier=1.35,
                energy_modifier=1.15,
            ),
            WeatherPattern(
                "Storm op het oppervlak",
                20,
                "storm",
                movement_modifier=0.85,
                hunger_modifier=0.95,
                regrowth_modifier=1.2,
                energy_modifier=0.9,
                duration_range=(9000, 16000),
            ),
            WeatherPattern(
                "Planktonbloei",
                22,
                "bewolkt",
                movement_modifier=1.0,
                hunger_modifier=0.8,
                regrowth_modifier=1.5,
                energy_modifier=1.05,
            ),
        ],
        "twilight": [
            WeatherPattern(
                "Drijfzand van licht",
                14,
                "mist",
                movement_modifier=0.9,
                hunger_modifier=1.05,
                regrowth_modifier=1.15,
                energy_modifier=0.95,
            ),
            WeatherPattern(
                "Koude stroming",
                10,
                "bewolkt",
                movement_modifier=0.85,
                hunger_modifier=1.1,
                regrowth_modifier=1.1,
                energy_modifier=0.9,
            ),
            WeatherPattern(
                "Zoemende bioluminescentie",
                12,
                "helder",
                movement_modifier=0.95,
                hunger_modifier=1.0,
                regrowth_modifier=1.2,
                energy_modifier=1.0,
            ),
        ],
        "midnight": [
            WeatherPattern(
                "Diepzee stilte",
                4,
                "stil",
                movement_modifier=0.8,
                hunger_modifier=1.2,
                regrowth_modifier=0.9,
                energy_modifier=0.85,
            ),
            WeatherPattern(
                "Drukgolven",
                2,
                "winderig",
                movement_modifier=0.75,
                hunger_modifier=1.25,
                regrowth_modifier=0.85,
                energy_modifier=0.8,
                health_tick=-0.1,
            ),
            WeatherPattern(
                "Bioluminescente regen",
                6,
                "regen",
                movement_modifier=0.82,
                hunger_modifier=1.1,
                regrowth_modifier=0.95,
                energy_modifier=0.9,
            ),
        ],
        "abyss": [
            WeatherPattern(
                "Abyssale druk",
                1,
                "stil",
                movement_modifier=0.7,
                hunger_modifier=1.35,
                regrowth_modifier=0.6,
                energy_modifier=0.8,
                health_tick=-0.2,
            ),
            WeatherPattern(
                "Chemische nevel",
                3,
                "mist",
                movement_modifier=0.75,
                hunger_modifier=1.3,
                regrowth_modifier=0.65,
                energy_modifier=0.85,
                health_tick=-0.15,
            ),
            WeatherPattern(
                "Echo van de diepzee",
                -1,
                "helder",
                movement_modifier=0.72,
                hunger_modifier=1.25,
                regrowth_modifier=0.7,
                energy_modifier=0.82,
                health_tick=-0.18,
            ),
        ],
        "vents": [
            WeatherPattern(
                "Zwarte roker",
                5,
                "storm",
                movement_modifier=0.75,
                hunger_modifier=0.95,
                regrowth_modifier=1.4,
                energy_modifier=0.9,
                health_tick=0.08,
            ),
            WeatherPattern(
                "Chemosynthese",
                8,
                "mist",
                movement_modifier=0.8,
                hunger_modifier=0.9,
                regrowth_modifier=1.6,
                energy_modifier=0.95,
                health_tick=0.12,
            ),
            WeatherPattern(
                "Thermale kolom",
                12,
                "winderig",
                movement_modifier=0.85,
                hunger_modifier=0.92,
                regrowth_modifier=1.45,
                energy_modifier=1.0,
            ),
        ],
    }


def _generate_abyssal_ocean(width: int, height: int) -> MapBlueprint:
    patterns = _build_weather_patterns()
    barriers = _create_border_barriers(width, height, thickness=18)
    water_bodies: List[WaterBody] = []

    def _layer_rect(start_ratio: float, end_ratio: float) -> pygame.Rect:
        top = int(height * start_ratio) + 30
        bottom = int(height * end_ratio) - 30
        rect_height = max(80, bottom - top)
        return pygame.Rect(60, top, width - 120, rect_height)

    depth_layers = [
        {
            "name": "Oppervlaktezone",
            "color": (86, 176, 224),
            "start": 0.0,
            "end": 0.16,
            "pattern": "sunlit",
            "movement": 1.15,
            "hunger": 0.9,
            "regrowth": 1.4,
            "energy": 1.1,
            "health": 0.05,
            "mask_complexity": 18,
            "mask_irregularity": 0.3,
        },
        {
            "name": "Schemerzone",
            "color": (62, 120, 180),
            "start": 0.16,
            "end": 0.35,
            "pattern": "twilight",
            "movement": 0.95,
            "hunger": 1.05,
            "regrowth": 1.15,
            "energy": 0.95,
            "health": 0.02,
            "mask_complexity": 16,
            "mask_irregularity": 0.36,
        },
        {
            "name": "Middernachtzone",
            "color": (28, 64, 120),
            "start": 0.35,
            "end": 0.58,
            "pattern": "midnight",
            "movement": 0.85,
            "hunger": 1.2,
            "regrowth": 0.95,
            "energy": 0.88,
            "health": -0.02,
            "mask_complexity": 14,
            "mask_irregularity": 0.38,
        },
        {
            "name": "Abyss",
            "color": (12, 30, 78),
            "start": 0.58,
            "end": 0.82,
            "pattern": "abyss",
            "movement": 0.78,
            "hunger": 1.3,
            "regrowth": 0.7,
            "energy": 0.82,
            "health": -0.08,
            "mask_complexity": 12,
            "mask_irregularity": 0.4,
        },
        {
            "name": "Bathyplaine",
            "color": (6, 14, 38),
            "start": 0.82,
            "end": 1.0,
            "pattern": "abyss",
            "movement": 0.72,
            "hunger": 1.35,
            "regrowth": 0.6,
            "energy": 0.78,
            "health": -0.12,
            "mask_complexity": 11,
            "mask_irregularity": 0.42,
        },
    ]

    biomes: List[BiomeRegion] = []
    for layer in depth_layers:
        biomes.append(
            _create_biome_region(
                layer["name"],
                _layer_rect(layer["start"], layer["end"]),
                layer["color"],
                patterns[layer["pattern"]][:],
                movement_modifier=layer["movement"],
                hunger_modifier=layer["hunger"],
                regrowth_modifier=layer["regrowth"],
                energy_modifier=layer["energy"],
                health_modifier=layer["health"],
                mask_complexity=layer["mask_complexity"],
                mask_irregularity=layer["mask_irregularity"],
                mask_variation=0.32,
            )
        )

    luminous_reef = _rect_from_bounds(
        width // 6,
        int(height * 0.26),
        width - width // 6,
        int(height * 0.36),
        width,
        height,
    )
    biomes.append(
        _create_biome_region(
            "Bioluminescente Rifwand",
            luminous_reef,
            (80, 160, 190),
            patterns["twilight"][:],
            movement_modifier=0.92,
            hunger_modifier=0.95,
            regrowth_modifier=1.25,
            energy_modifier=1.05,
            health_modifier=0.04,
            mask_complexity=20,
            mask_irregularity=0.28,
            mask_variation=0.5,
        )
    )

    vent_rect = _rect_from_bounds(
        width // 2 - width // 6,
        int(height * 0.8),
        width // 2 + width // 6,
        int(height * 0.92),
        width,
        height,
    )
    biomes.append(
        _create_biome_region(
            "Hydrothermale Vents",
            vent_rect,
            (48, 48, 96),
            patterns["vents"][:],
            movement_modifier=0.8,
            hunger_modifier=0.9,
            regrowth_modifier=1.35,
            energy_modifier=0.92,
            health_modifier=0.06,
            mask_complexity=13,
            mask_irregularity=0.4,
            mask_variation=0.45,
        )
    )

    vegetation_masks = [
        pygame.Rect(140, int(height * 0.04), width - 280, 260),
        pygame.Rect(220, int(height * 0.32), width - 440, 280),
        pygame.Rect(260, int(height * 0.58), width - 520, 320),
    ]

    return MapBlueprint(
        background_color=(4, 16, 32),
        barriers=barriers,
        water_bodies=water_bodies,
        biomes=biomes,
        vegetation_masks=vegetation_masks,
    )


def _generate_rift_valley(width: int, height: int) -> MapBlueprint:
    patterns = _build_weather_patterns()
    barriers: List[Barrier] = []
    water_bodies: List[WaterBody] = []

    biomes = [
        _create_biome_region(
            "Rivierdelta",
            pygame.Rect(
                width // 3 - 80,
                height // 2 - 160,
                width // 2 + 40,
                320,
            ),
            (120, 200, 150),
            patterns["marsh"][:],
            movement_modifier=0.85,
            hunger_modifier=0.95,
            regrowth_modifier=1.4,
            energy_modifier=0.95,
            health_modifier=0.05,
            mask_complexity=14,
            mask_irregularity=0.4,
            mask_variation=0.45,
        ),
        _create_biome_region(
            "Bosrand",
            pygame.Rect(60, 60, width // 3 - 20, height // 2),
            (80, 170, 120),
            patterns["forest"][:],
            movement_modifier=0.8,
            hunger_modifier=0.9,
            regrowth_modifier=1.5,
            energy_modifier=1.0,
            health_modifier=0.02,
            mask_complexity=16,
            mask_irregularity=0.32,
        ),
        _create_biome_region(
            "Steppe",
            pygame.Rect(
                width // 3 + 20,
                100,
                width // 3 + 160,
                height // 2 - 40,
            ),
            (180, 200, 120),
            patterns["temperate"][:],
            movement_modifier=1.05,
            hunger_modifier=0.95,
            regrowth_modifier=1.0,
            energy_modifier=1.1,
            mask_complexity=12,
            mask_irregularity=0.28,
        ),
        _create_biome_region(
            "Woestijnrand",
            pygame.Rect(
                width // 2 + 120,
                height - 320,
                width // 2 - 160,
                240,
            ),
            (210, 190, 120),
            patterns["desert"][:],
            movement_modifier=0.75,
            hunger_modifier=1.3,
            regrowth_modifier=0.6,
            energy_modifier=0.8,
            health_modifier=-0.1,
            mask_complexity=11,
            mask_irregularity=0.42,
        ),
        _create_biome_region(
            "Toendra",
            pygame.Rect(width - 420, 40, 360, 260),
            (180, 210, 220),
            patterns["tundra"][:],
            movement_modifier=0.7,
            hunger_modifier=1.2,
            regrowth_modifier=0.65,
            energy_modifier=0.85,
            health_modifier=-0.05,
            mask_complexity=13,
            mask_irregularity=0.38,
        ),
    ]

    vegetation_masks = [biome.rect.copy() for biome in biomes if "Rivier" in biome.name]

    return MapBlueprint(
        background_color=(228, 222, 208),
        barriers=barriers,
        water_bodies=water_bodies,
        biomes=biomes,
        vegetation_masks=vegetation_masks,
    )


def _generate_archipelago(width: int, height: int) -> MapBlueprint:
    patterns = _build_weather_patterns()

    strait_width = max(140, width // 10)
    strait_height = max(160, height // 6)
    strait_left = width // 2 - strait_width // 2 + random.randint(-60, 60)
    strait_left = max(180, min(strait_left, width - strait_width - 180))
    strait_top = height // 2 - strait_height // 2 + random.randint(-40, 40)
    strait_top = max(160, min(strait_top, height - strait_height - 160))

    vertical_strait = pygame.Rect(strait_left, 0, strait_width, height)
    horizontal_strait = pygame.Rect(0, strait_top, width, strait_height)

    lagoon1 = _rect_from_bounds(
        strait_left - 220,
        strait_top - 140,
        strait_left - 20,
        strait_top + 120,
        width,
        height,
    )
    lagoon2 = _rect_from_bounds(
        strait_left + strait_width + 20,
        strait_top + strait_height - 120,
        strait_left + strait_width + 260,
        strait_top + strait_height + 120,
        width,
        height,
    )

    water_bodies: List[WaterBody] = []
    barriers: List[Barrier] = []

    margin = 80
    top_left = _rect_from_bounds(
        margin,
        margin,
        vertical_strait.left - margin,
        horizontal_strait.top - margin,
        width,
        height,
    )
    top_right = _rect_from_bounds(
        vertical_strait.right + margin,
        margin,
        width - margin,
        horizontal_strait.top - margin,
        width,
        height,
    )
    bottom_left = _rect_from_bounds(
        margin,
        horizontal_strait.bottom + margin,
        vertical_strait.left - margin,
        height - margin,
        width,
        height,
    )
    bottom_right = _rect_from_bounds(
        vertical_strait.right + margin,
        horizontal_strait.bottom + margin,
        width - margin,
        height - margin,
        width,
        height,
    )
    central = _rect_from_bounds(
        vertical_strait.left - 160,
        horizontal_strait.top - 120,
        vertical_strait.right + 160,
        horizontal_strait.bottom + 120,
        width,
        height,
    )

    biomes = [
        _create_biome_region(
            "Bosrijk Eiland",
            top_left,
            (90, 180, 140),
            patterns["forest"][:],
            movement_modifier=0.82,
            hunger_modifier=0.92,
            regrowth_modifier=1.5,
            energy_modifier=1.0,
            health_modifier=0.03,
            mask_complexity=15,
            mask_irregularity=0.3,
        ),
        _create_biome_region(
            "Steppe Eiland",
            top_right,
            (200, 205, 150),
            patterns["temperate"][:],
            movement_modifier=1.1,
            hunger_modifier=0.95,
            regrowth_modifier=1.05,
            energy_modifier=1.1,
            mask_complexity=12,
            mask_irregularity=0.34,
        ),
        _create_biome_region(
            "Woestijn Eiland",
            bottom_left,
            (222, 198, 140),
            patterns["desert"][:],
            movement_modifier=0.78,
            hunger_modifier=1.3,
            regrowth_modifier=0.55,
            energy_modifier=0.82,
            health_modifier=-0.08,
            mask_complexity=11,
            mask_irregularity=0.4,
        ),
        _create_biome_region(
            "Moeras Eiland",
            bottom_right,
            (140, 200, 170),
            patterns["marsh"][:],
            movement_modifier=0.8,
            hunger_modifier=0.92,
            regrowth_modifier=1.55,
            energy_modifier=0.95,
            health_modifier=0.06,
            mask_complexity=14,
            mask_irregularity=0.36,
        ),
        _create_biome_region(
            "Koraal Rif",
            central,
            (110, 210, 210),
            patterns["coastal"][:],
            movement_modifier=0.9,
            hunger_modifier=0.85,
            regrowth_modifier=1.4,
            energy_modifier=1.0,
            mask_complexity=18,
            mask_irregularity=0.28,
        ),
    ]

    vegetation_masks = []
    for rect in (top_left, top_right, bottom_left, bottom_right):
        shrunk = rect.inflate(-160, -160)
        if shrunk.width > 40 and shrunk.height > 40:
            vegetation_masks.append(shrunk)

    return MapBlueprint(
        background_color=(214, 232, 238),
        barriers=barriers,
        water_bodies=water_bodies,
        biomes=biomes,
        vegetation_masks=vegetation_masks,
    )


def _generate_desert_jungle(width: int, height: int) -> MapBlueprint:
    patterns = _build_weather_patterns()
    barriers: List[Barrier] = []
    water_bodies: List[WaterBody] = []

    desert_rect = _rect_from_bounds(40, 60, width // 2 + 20, height - 60, width, height)
    dunes_rect = _rect_from_bounds(60, height // 2 + 80, width // 2 - 140, height - 80, width, height)
    savanna_rect = _rect_from_bounds(
        width // 2 - 200,
        140,
        width // 2 + 220,
        height - 140,
        width,
        height,
    )
    jungle_rect = _rect_from_bounds(width // 2 + 120, 60, width - 40, height - 60, width, height)
    delta_rect = _rect_from_bounds(width // 2 + 60, height - 260, width - 80, height - 80, width, height)

    biomes = [
        _create_biome_region(
            "Woestijn",
            desert_rect,
            (214, 193, 134),
            patterns["desert"][:],
            movement_modifier=0.7,
            hunger_modifier=1.35,
            regrowth_modifier=0.6,
            energy_modifier=0.8,
            health_modifier=-0.12,
            mask_complexity=10,
            mask_irregularity=0.45,
            mask_variation=0.4,
        ),
        _create_biome_region(
            "Duinveld",
            dunes_rect,
            (222, 178, 110),
            patterns["desert"][:],
            movement_modifier=0.75,
            hunger_modifier=1.25,
            regrowth_modifier=0.55,
            energy_modifier=0.78,
            health_modifier=-0.1,
            mask_complexity=9,
            mask_irregularity=0.42,
        ),
        _create_biome_region(
            "Savanne",
            savanna_rect,
            (200, 205, 150),
            patterns["savanna"][:],
            movement_modifier=1.0,
            hunger_modifier=1.0,
            regrowth_modifier=1.1,
            energy_modifier=1.05,
            health_modifier=0.02,
            mask_complexity=12,
            mask_irregularity=0.33,
        ),
        _create_biome_region(
            "Jungle",
            jungle_rect,
            (90, 170, 110),
            patterns["tropical"][:],
            movement_modifier=0.75,
            hunger_modifier=1.1,
            regrowth_modifier=1.6,
            energy_modifier=0.95,
            health_modifier=0.08,
            mask_complexity=16,
            mask_irregularity=0.37,
            mask_variation=0.4,
        ),
        _create_biome_region(
            "Rivier",
            delta_rect,
            (120, 200, 150),
            patterns["marsh"][:],
            movement_modifier=0.85,
            hunger_modifier=0.95,
            regrowth_modifier=1.35,
            energy_modifier=0.95,
            health_modifier=0.05,
            mask_complexity=14,
            mask_irregularity=0.4,
        ),
    ]

    vegetation_masks = [
        rect.inflate(-120, -120)
        for rect in (savanna_rect, jungle_rect)
        if rect.width > 200 and rect.height > 200
    ]

    return MapBlueprint(
        background_color=(236, 222, 196),
        barriers=barriers,
        water_bodies=water_bodies,
        biomes=biomes,
        vegetation_masks=vegetation_masks,
    )


_GENERATOR_MAP: Dict[str, Callable[[int, int], MapBlueprint]] = {
    "Abyssal Ocean": _generate_abyssal_ocean,
    "Archipelago": _generate_archipelago,
    "Rift Valley": _generate_rift_valley,
    "Desert–Jungle Split": _generate_desert_jungle,
}


def generate_map(world_type: str | None, width: int, height: int) -> MapBlueprint:
    """Generate a map blueprint for the requested world type."""

    canonical = normalize_world_type(world_type)
    generator = _GENERATOR_MAP.get(canonical, _generate_rift_valley)
    return generator(width, height)


__all__ = ["MapBlueprint", "generate_map", "normalize_world_type"]


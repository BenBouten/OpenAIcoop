"""Simulation bootstrap helpers consolidating world and entity initialisation."""

from __future__ import annotations

import math
import random
import logging
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

import pygame

from ..config import settings
from ..entities.lifeform import Lifeform
from ..world.vegetation import MossCluster, create_initial_clusters
from ..world.world import BiomeRegion, World
from ..systems.telemetry import enable_telemetry
from .state import SimulationState
from .base_population import base_templates

if TYPE_CHECKING:
    from ..rendering.camera import Camera
    from ..rendering.effects import EffectManager
    from ..systems.events import EventManager
    from ..systems.notifications import NotificationManager
    from ..systems.player import PlayerController

Vegetation = MossCluster

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# High level orchestration
# ---------------------------------------------------------------------------

def reset_simulation(
    state: SimulationState,
    world: World,
    camera: "Camera",
    event_manager: "EventManager",
    player_controller: "PlayerController",
    notification_manager: "NotificationManager",
    effects_manager: "EffectManager",
    *,
    on_spawn: Optional[Callable[[object], None]] = None,
) -> None:
    """Reset all shared simulation state and regenerate the world."""
    
    enable_telemetry("all")

    state.lifeforms.clear()
    state.dna_profiles.clear()
    state.dna_id_counts.clear()
    state.dna_lineage.clear()
    state.lifeform_genetics.clear()
    state.plants.clear()
    state.carcasses.clear()
    state.death_ages.clear()
    state.dna_home_biome.clear()
    state.lifeform_id_counter = 0
    state.selected_lifeform = None
    state.last_debug_log_path = None

    world.regenerate()

    state.world = world
    state.world_type = world.world_type
    state.camera = camera
    state.events = event_manager
    state.player = player_controller
    state.notifications = notification_manager
    state.effects = effects_manager
    state.pending_template_callback = on_spawn

    notification_manager.clear()
    event_manager.reset()
    event_manager.schedule_default_events()
    player_controller.reset()
    effects_manager.clear()

    state.environment_modifiers.setdefault("plant_regrowth", 1.0)
    state.environment_modifiers.setdefault("hunger_rate", 1.0)
    state.environment_modifiers.setdefault("weather_intensity", 1.0)
    state.environment_modifiers.setdefault("moss_growth_speed", 1.0)

    state.last_plant_regrowth = state.environment_modifiers.get("plant_regrowth", 1.0)
    state.last_moss_growth_speed = state.environment_modifiers.get("moss_growth_speed", 1.0)

    world.set_environment_modifiers(state.environment_modifiers)
    camera.reset()


# ---------------------------------------------------------------------------
# DNA & spawning helpers
# ---------------------------------------------------------------------------

def generate_dna_profiles(state: SimulationState, world: World) -> None:
    """Generate a small neutral DNA catalogue from base templates."""

    rng = random.Random()
    state.dna_profiles.clear()
    state.dna_home_biome.clear()

    templates = base_templates(rng, count=settings.INITIAL_BASEFORM_COUNT)
    dna_id = 0

    def _register_profile(profile: dict) -> None:
        state.dna_profiles.append(profile)
        home = determine_home_biome(profile, world.biomes) if world.biomes else None
        state.dna_home_biome[profile["dna_id"]] = home

    for template in templates:
        _register_profile(template.spawn_profile(dna_id, rng))
        dna_id += 1

    clones_needed = max(settings.N_LIFEFORMS - len(state.dna_profiles), 0)
    for _ in range(clones_needed):
        template = rng.choice(templates)
        _register_profile(template.spawn_profile(dna_id, rng))
        dna_id += 1


def spawn_lifeforms(state: SimulationState, world: World) -> None:
    """Spawn the configured number of lifeforms using the DNA catalogue."""

    if not state.dna_profiles:
        return

    rng = random.Random()
    anchors = _select_nutrient_anchors(state.plants, rng)
    occupied: List[Tuple[float, float]] = []
    max_spawns = min(settings.N_LIFEFORMS, len(state.dna_profiles))

    for dna_profile in state.dna_profiles[:max_spawns]:
        spawn = _spawn_near_anchor_or_random(
            world,
            dna_profile,
            anchors,
            occupied,
            rng,
        )
        x, y, biome = spawn
        center = (
            x + dna_profile["width"] / 2,
            y + dna_profile["height"] / 2,
        )
        occupied.append(center)

        lifeform = Lifeform(state, x, y, dna_profile, generation=1)
        lifeform.current_biome = biome
        state.lifeforms.append(lifeform)


def _select_nutrient_anchors(
    plants: List[MossCluster] | None, rng: random.Random, target: int = 3
) -> List[Tuple[float, float]]:
    anchors: List[Tuple[float, float]] = []
    if plants:
        anchors = [
            (float(cluster.rect.centerx), float(cluster.rect.centery))
            for cluster in plants
            if getattr(cluster, "rect", None) is not None
        ]

    anchors.sort(key=lambda pt: pt[1])
    if not anchors:
        return []
    if len(anchors) <= target:
        return anchors

    selections: List[Tuple[float, float]] = []
    stride = len(anchors) / float(target)
    seen: set[Tuple[float, float]] = set()
    for idx in range(target):
        base_index = int(idx * stride)
        offset = rng.randint(0, max(0, int(stride) - 1)) if stride > 1 else 0
        choice = anchors[min(len(anchors) - 1, base_index + offset)]
        if choice in seen:
            continue
        selections.append(choice)
        seen.add(choice)
    return selections or anchors


def _spawn_near_anchor_or_random(
    world: World,
    dna_profile: dict,
    anchors: List[Tuple[float, float]],
    occupied: List[Tuple[float, float]],
    rng: random.Random,
) -> Tuple[float, float, Optional[BiomeRegion]]:
    width = int(dna_profile.get("width", settings.MIN_WIDTH))
    height = int(dna_profile.get("height", settings.MIN_HEIGHT))
    min_spacing = max(140.0, float(dna_profile.get("collision_radius") or 60.0) * 2.0)

    if anchors:
        for _ in range(3):
            anchor = rng.choice(anchors)
            placed = _attempt_anchor_spawn(
                world, width, height, anchor, occupied, min_spacing, rng
            )
            if placed is not None:
                return placed

    return world.random_position(
        width,
        height,
        avoid_positions=occupied,
        min_distance=min_spacing,
        biome_padding=32,
    )


def _attempt_anchor_spawn(
    world: World,
    width: int,
    height: int,
    anchor: Tuple[float, float],
    occupied: List[Tuple[float, float]],
    min_spacing: float,
    rng: random.Random,
) -> Tuple[float, float, Optional[BiomeRegion]] | None:
    for _ in range(90):
        radius = rng.uniform(30.0, 240.0)
        angle = rng.uniform(0.0, math.tau)
        center_x = anchor[0] + math.cos(angle) * radius
        center_y = anchor[1] + math.sin(angle) * radius
        x = max(0.0, min(world.width - width, center_x - width / 2))
        y = max(0.0, min(world.height - height, center_y - height / 2))
        center = (x + width / 2, y + height / 2)

        too_close = any(
            math.hypot(center[0] - px, center[1] - py) < min_spacing for px, py in occupied
        )
        if too_close:
            continue

        rect = pygame.Rect(x, y, width, height)
        if world.is_blocked(rect):
            continue

        biome = world.get_biome_at(int(center[0]), int(center[1]))
        return x, y, biome
    return None


def seed_vegetation(state: SimulationState, world: World) -> None:
    """Populate the world with the initial vegetation clusters."""

    state.plants.clear()
    abundance = state.environment_modifiers.get("plant_regrowth", 1.0)
    moss_growth = state.environment_modifiers.get("moss_growth_speed", 1.0)
    clusters = create_initial_clusters(world, count=32)
    for cluster in clusters:
        cluster.set_capacity_multiplier(abundance)
        cluster.set_growth_speed_modifier(moss_growth)
        state.plants.append(cluster)


# ---------------------------------------------------------------------------
# Biome helpers
# ---------------------------------------------------------------------------

def determine_home_biome(
    dna_profile: dict,
    biomes: List[BiomeRegion],
) -> Optional[BiomeRegion]:
    if not biomes:
        return None

    size = (dna_profile["width"] + dna_profile["height"]) / 2
    if settings.USE_BODYGRAPH_SIZE:
        geometry = dna_profile.get("geometry", {})
        size = (geometry.get("width", size) + geometry.get("height", size)) / 2
        min_size = min(settings.MIN_WIDTH, geometry.get("width", settings.MIN_WIDTH))
        max_size = max(settings.MAX_WIDTH, geometry.get("width", settings.MAX_WIDTH))
    else:
        min_size = (settings.MIN_WIDTH + settings.MIN_HEIGHT) / 2
        max_size = (settings.MAX_WIDTH + settings.MAX_HEIGHT) / 2

    size_norm = _normalize(size, min_size, max_size)
    heat_tolerance = _normalize(dna_profile["energy"], 60, 120)
    hydration_dependence = 1.0 - heat_tolerance
    resilience = (
        _normalize(dna_profile["health"], 1, 220)
        + _normalize(dna_profile["defence_power"], 1, 110)
    ) / 2
    mobility = (
        _normalize(dna_profile["vision"], settings.VISION_MIN, settings.VISION_MAX)
        + (1.0 - size_norm)
    ) / 2
    longevity_factor = _normalize(dna_profile["longevity"], 800, 5200)
    aggression = _normalize(dna_profile["attack_power"], 1, 110)

    preferred_biome: Optional[BiomeRegion] = None
    preferred_score = -1.0

    for biome in biomes:
        name = biome.name.lower()
        score = 0.0
        if "woestijn" in name:
            score = (
                heat_tolerance * 0.55
                + resilience * 0.25
                + aggression * 0.15
                + mobility * 0.1
                - hydration_dependence * 0.2
            )
        elif "toendra" in name:
            score = (
                (1.0 - heat_tolerance) * 0.35
                + longevity_factor * 0.35
                + resilience * 0.2
                + hydration_dependence * 0.1
            )
        elif "bos" in name:
            score = (
                mobility * 0.35
                + hydration_dependence * 0.2
                + resilience * 0.25
                + (1.0 - size_norm) * 0.1
                + aggression * 0.1
            )
        elif "rivier" in name or "delta" in name or "moeras" in name:
            score = (
                hydration_dependence * 0.45
                + mobility * 0.2
                + resilience * 0.2
                + longevity_factor * 0.15
            )
        elif "steppe" in name:
            score = (
                mobility * 0.3
                + heat_tolerance * 0.25
                + resilience * 0.2
                + aggression * 0.15
                + longevity_factor * 0.1
            )
        else:
            score = (
                resilience * 0.3
                + mobility * 0.25
                + longevity_factor * 0.2
                + (1.0 - abs(heat_tolerance - 0.5)) * 0.25
            )

        if score > preferred_score:
            preferred_biome = biome
            preferred_score = score

    return preferred_biome


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.5
    return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))

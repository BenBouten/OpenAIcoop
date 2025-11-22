"""Simulation bootstrap helpers consolidating world and entity initialisation."""

from __future__ import annotations

import math
import random
import logging
from typing import Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from ..config import settings
from ..body.body_graph import BodyGraph
from ..body.modules import catalogue_jellyfish_modules
from ..dna.blueprints import generate_modular_blueprint
from ..dna.development import generate_development_plan
from ..dna.factory import build_body_graph, serialize_body_graph
from ..entities.lifeform import Lifeform
from ..morphology.genotype import MorphologyGenotype
from ..world.vegetation import MossCluster, create_initial_clusters
from ..world.world import BiomeRegion, World
from .state import SimulationState

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
    """Generate the configurable DNA profile catalogue."""

    state.dna_profiles.clear()
    state.dna_home_biome.clear()

    for dna_id in range(settings.N_DNA_PROFILES):
        diet = random.choices(
            ["herbivore", "omnivore", "carnivore"],
            weights=[0.4, 0.35, 0.25],
        )[0]

        if diet == "herbivore":
            attack_power = random.randint(5, 45)
            defence_power = random.randint(35, 85)
            vision_value = random.randint(
                settings.VISION_MIN,
                max(settings.VISION_MIN + 1, settings.VISION_MAX - 10),
            )
            energy_value = random.randint(88, 110)
            longevity_value = random.randint(1600, 5200)
            social_tendency = random.uniform(0.6, 1.0)
            risk_tolerance = random.uniform(0.1, 0.5)
            restlessness_range = (0.18, 0.55)
            boid_range = (0.7, 1.0)
        elif diet == "carnivore":
            attack_power = random.randint(45, 95)
            defence_power = random.randint(20, 65)
            vision_value = random.randint(
                max(settings.VISION_MIN, 28),
                settings.VISION_MAX,
            )
            energy_value = random.randint(78, 96)
            longevity_value = random.randint(900, 3600)
            social_tendency = random.uniform(0.2, 0.6)
            risk_tolerance = random.uniform(0.6, 1.0)
            restlessness_range = (0.55, 0.95)
            boid_range = (0.25, 0.7)
        else:
            attack_power = random.randint(30, 85)
            defence_power = random.randint(25, 75)
            vision_value = random.randint(
                max(settings.VISION_MIN, 24),
                settings.VISION_MAX,
            )
            energy_value = random.randint(82, 104)
            longevity_value = random.randint(1200, 4200)
            social_tendency = random.uniform(0.4, 0.85)
            risk_tolerance = random.uniform(0.4, 0.8)
            restlessness_range = (0.32, 0.78)
            boid_range = (0.45, 0.9)

        morphology = MorphologyGenotype.random()
        development = generate_development_plan(diet)
        restlessness = random.uniform(*restlessness_range)
        boid_tendency = random.uniform(*boid_range)

        genome_blueprint = generate_modular_blueprint(diet, rng=random)

        dna_profile = {
            "dna_id": dna_id,
            "width": random.randint(settings.MIN_WIDTH, settings.MAX_WIDTH),
            "height": random.randint(settings.MIN_HEIGHT, settings.MAX_HEIGHT),
            "color": (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255),
            ),
            "health": random.randint(1, 200),
            "maturity": random.randint(
                settings.MIN_MATURITY,
                settings.MAX_MATURITY,
            ),
            "vision": vision_value,
            "defence_power": defence_power,
            "attack_power": attack_power,
            "energy": energy_value,
            "longevity": longevity_value,
            "diet": diet,
            "social": social_tendency,
            "boid_tendency": boid_tendency,
            "risk_tolerance": risk_tolerance,
            "restlessness": restlessness,
            "morphology": morphology.to_dict(),
            "development": development,
            "genome": genome_blueprint,
        }
        graph, geometry = build_body_graph(genome_blueprint, include_geometry=True)
        dna_profile["geometry"] = geometry
        dna_profile["collision_radius"] = geometry.get("collision_radius", 8.0)
        geometry = dna_profile.get("geometry", {})
        if settings.USE_BODYGRAPH_SIZE and geometry:
            width_m = geometry.get("width", settings.MIN_WIDTH / settings.BODY_PIXEL_SCALE)
            height_m = geometry.get("height", settings.MIN_HEIGHT / settings.BODY_PIXEL_SCALE)
            dna_profile["width"] = int(round(width_m * settings.BODY_PIXEL_SCALE))
            dna_profile["height"] = int(round(height_m * settings.BODY_PIXEL_SCALE))
        state.dna_profiles.append(dna_profile)

        if world.biomes:
            home = determine_home_biome(dna_profile, world.biomes)
        else:
            home = None
        state.dna_home_biome[dna_profile["dna_id"]] = home

    jelly_profile = _build_jellyfish_profile(len(state.dna_profiles))
    state.dna_profiles.append(jelly_profile)

    if world.biomes:
        jelly_home = determine_home_biome(jelly_profile, world.biomes)
    else:
        jelly_home = None
    state.dna_home_biome[jelly_profile["dna_id"]] = jelly_home


def spawn_lifeforms(state: SimulationState, world: World) -> None:
    """Spawn the configured number of lifeforms using the DNA catalogue."""

    if not state.dna_profiles:
        return

    spawn_positions_by_dna: Dict[int, List[Tuple[float, float]]] = {
        profile["dna_id"]: [] for profile in state.dna_profiles
    }

    def _spawn_from_profile(dna_profile: dict) -> None:
        preferred_biome = state.dna_home_biome.get(dna_profile["dna_id"])
        other_positions = [
            pos
            for dna_id, positions in spawn_positions_by_dna.items()
            if dna_id != dna_profile["dna_id"]
            for pos in positions
        ]

        spawn_attempts = 0
        min_spacing = 160
        radius = float(dna_profile.get("collision_radius") or 80.0)
        if settings.USE_BODYGRAPH_SIZE:
            min_spacing = max(min_spacing, radius * 2 + 80)
        while True:
            x, y, biome = world.random_position(
                dna_profile["width"],
                dna_profile["height"],
                preferred_biome=preferred_biome,
                avoid_positions=other_positions,
                min_distance=min_spacing,
                biome_padding=40,
            )
            center = (
                x + dna_profile["width"] / 2,
                y + dna_profile["height"] / 2,
            )
            same_species_positions = spawn_positions_by_dna.setdefault(
                dna_profile["dna_id"],
                [],
            )
            too_close_same = any(
                math.hypot(center[0] - px, center[1] - py) < 160
                for px, py in same_species_positions
            )
            if not too_close_same or spawn_attempts > 120:
                same_species_positions.append(center)
                break
            spawn_attempts += 1
            if settings.USE_BODYGRAPH_SIZE and spawn_attempts % 40 == 0:
                logger.debug(
                    "Spawn retry %s for DNA %s (radius=%.1f, spacing=%.1f)",
                    spawn_attempts,
                    dna_profile["dna_id"],
                    radius,
                    min_spacing,
                )
        if settings.USE_BODYGRAPH_SIZE and spawn_attempts:
            logger.info(
                "Spawned DNA %s after %s retries (radius=%.1f, size=%s)",
                dna_profile["dna_id"],
                spawn_attempts,
                radius,
                (dna_profile["width"], dna_profile["height"]),
            )

        lifeform = Lifeform(state, x, y, dna_profile, generation=1)
        lifeform.current_biome = biome
        state.lifeforms.append(lifeform)

    guaranteed_profiles = [p for p in state.dna_profiles if p.get("guaranteed_spawn")]

    # Ensure that the alien ocean always starts with a small, diverse roster.
    guaranteed_species = 0
    if state.world_type == "Alien Ocean":
        guaranteed_species = min(
            settings.STARTING_SPECIES_COUNT,
            len(state.dna_profiles),
            settings.N_LIFEFORMS,
        )

    guaranteed_ids = {profile["dna_id"] for profile in guaranteed_profiles}
    pool = [p for p in state.dna_profiles if p["dna_id"] not in guaranteed_ids]
    sample_count = max(0, guaranteed_species - len(guaranteed_profiles))
    sampled_profiles = (
        random.sample(pool, sample_count)
        if sample_count and pool
        else []
    )

    for profile in guaranteed_profiles + sampled_profiles:
        if len(state.lifeforms) >= settings.N_LIFEFORMS:
            break
        _spawn_from_profile(profile)

    remaining_spawns = max(0, settings.N_LIFEFORMS - len(state.lifeforms))
    for _ in range(remaining_spawns):
        dna_profile = random.choice(state.dna_profiles)
        _spawn_from_profile(dna_profile)

    if settings.USE_BODYGRAPH_SIZE:
        largest = max(state.dna_profiles, key=lambda p: p.get("collision_radius", 0))
        largest_radius = float(largest.get("collision_radius") or 0.0)
        logger.info(
            "Largest spawn collision radius %.1f (dna %s, size=%sx%s)",
            largest_radius,
            largest.get("dna_id"),
            largest.get("width"),
            largest.get("height"),
        )


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


def _build_jellyfish_profile(dna_id: int) -> dict:
    """Seed a bell-and-tentacle drifter that always spawns at startup."""

    rng = random.Random()
    modules = catalogue_jellyfish_modules()
    graph = BodyGraph("bell_core", modules["bell_core"])
    graph.add_module("bell_siphon", modules["bell_siphon"], "bell_core", "siphon_nozzle")
    graph.add_module("bell_sensor", modules["bell_sensor"], "bell_core", "umbrella_sensor")
    graph.add_module("tentacle_front", modules["tentacle_front"], "bell_core", "tentacle_socket_front")
    graph.add_module("tentacle_left", modules["tentacle_left"], "bell_core", "tentacle_socket_left")
    graph.add_module("tentacle_right", modules["tentacle_right"], "bell_core", "tentacle_socket_right")
    graph.add_module("tentacle_rear", modules["tentacle_rear"], "bell_core", "tentacle_socket_rear")

    genome = serialize_body_graph(graph).to_dict()

    return {
        "dna_id": dna_id,
        "width": rng.randint(settings.MIN_WIDTH + 1, settings.MAX_WIDTH - 2),
        "height": rng.randint(settings.MIN_HEIGHT + 1, settings.MAX_HEIGHT - 1),
        "color": (
            rng.randint(120, 220),
            rng.randint(160, 255),
            rng.randint(180, 255),
        ),
        "health": rng.randint(70, 130),
        "maturity": rng.randint(settings.MIN_MATURITY + 40, settings.MAX_MATURITY - 30),
        "vision": rng.randint(settings.VISION_MIN + 10, settings.VISION_MAX - 6),
        "defence_power": rng.randint(22, 60),
        "attack_power": rng.randint(12, 40),
        "energy": rng.randint(90, 120),
        "longevity": rng.randint(2200, 5200),
        "diet": "omnivore",
        "social": rng.uniform(0.35, 0.8),
        "boid_tendency": rng.uniform(0.35, 0.85),
        "risk_tolerance": rng.uniform(0.35, 0.75),
        "restlessness": rng.uniform(0.28, 0.62),
        "morphology": MorphologyGenotype.random().to_dict(),
        "development": generate_development_plan("omnivore"),
        "genome": genome,
        "guaranteed_spawn": True,
    }

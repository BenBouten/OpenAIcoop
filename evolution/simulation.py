"""Core simulation loop and entities for the evolution project."""

from __future__ import annotations

import datetime
import logging
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pygame

from .config import settings
from .entities import movement
from .entities.lifeform import Lifeform
from .entities.pheromones import Pheromone
from .rendering.camera import Camera
from .rendering.draw_lifeform import draw_lifeform, draw_lifeform_vision
from .simulation.state import SimulationState
from .systems.events import EventManager
from .systems.notifications import NotificationManager
from .systems.player import PlayerController
from .world.vegetation import MossCluster, create_initial_clusters
from .world.world import BiomeRegion, World

DNA_CLUSTER_RADIUS = 180


MAP_TYPE_OPTIONS = [
    "Archipelago",
    "Rift Valley",
    "Desert–Jungle Split",
]


@dataclass
class NotificationContext:
    notification_manager: NotificationManager
    show_debug: bool = False
    show_action: bool = False

    def debug(self, message: str, duration: Optional[int] = None) -> None:
        if self.show_debug:
            self.notification_manager.add(message, settings.BLUE, duration)

    def action(self, message: str, duration: Optional[int] = None) -> None:
        if self.show_action:
            self.notification_manager.add(message, settings.SEA, duration)


notification_context = NotificationContext(NotificationManager())


def _initialise_logger() -> logging.Logger:
    log_dir = settings.LOG_DIRECTORY
    if not isinstance(log_dir, Path):
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / settings.DEBUG_LOG_FILE

    logger = logging.getLogger("evolution.simulation")
    if logger.handlers:
        return logger

    level_name = str(settings.DEBUG_LOG_LEVEL).upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(level)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False

    logger.info("Debug logging initialised at %s", log_path)
    return logger


logger = _initialise_logger()


state = SimulationState()
state.notification_context = notification_context
state.notifications = notification_context.notification_manager


Vegetation = MossCluster


class Graph:
    def __init__(self):
        self.figure, self.axes = plt.subplots()
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")

    def update(self, death_ages_by_dna: Dict[int, List[int]]) -> None:
        self.axes.clear()
        dna_ids = []
        avg_ages = []
        for dna_id, ages in death_ages_by_dna.items():
            dna_ids.append(dna_id)
            avg_ages.append(sum(ages) / len(ages))
        self.axes.bar(dna_ids, avg_ages)
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")
        self.figure.canvas.draw()

    def draw(self, screen):
        plt.draw()
        graph_surface = pygame.surfarray.make_surface(self.figure)
        screen.blit(graph_surface, (0, 0))


world: World
camera: Camera
notification_manager: NotificationManager = notification_context.notification_manager
event_manager: EventManager
player_controller: PlayerController

lifeforms: List[Lifeform] = state.lifeforms
pheromones: List[Pheromone] = state.pheromones
dna_profiles: List[dict] = state.dna_profiles
plants: List[Vegetation] = state.plants

dna_id_counts: Dict[int, int] = {}
dna_home_biome: Dict[int, Optional[BiomeRegion]] = state.dna_home_biome

death_ages: List[int] = state.death_ages
latest_stats: Optional[Dict[str, float]] = None

environment_modifiers: Dict[str, float] = state.environment_modifiers
_last_food_multiplier = environment_modifiers.get("plant_regrowth", 1.0)
_last_moss_growth = environment_modifiers.get("moss_growth_speed", 1.0)


def _sync_food_abundance() -> None:
    global _last_food_multiplier
    current = environment_modifiers.get("plant_regrowth", 1.0)
    if math.isclose(current, _last_food_multiplier, rel_tol=1e-4, abs_tol=1e-6):
        return
    _last_food_multiplier = current
    if state.world is not None:
        state.world.set_environment_modifiers(state.environment_modifiers)
    for plant in plants:
        plant.set_capacity_multiplier(current)


def _sync_moss_growth_speed() -> None:
    global _last_moss_growth
    current = environment_modifiers.get("moss_growth_speed", 1.0)
    if math.isclose(current, _last_moss_growth, rel_tol=1e-4, abs_tol=1e-6):
        return
    _last_moss_growth = current
    for plant in plants:
        plant.set_growth_speed_modifier(current)

show_debug = False
show_leader = False
show_action = False
show_vision = False
show_dna_id = True
show_dna_info = False

start_time = datetime.datetime.now()
clock = pygame.time.Clock()
fps = settings.FPS


def reset_list_values(world_type: Optional[str] = None) -> None:
    global latest_stats, _last_food_multiplier, _last_moss_growth
    target_world_type = world_type if world_type is not None else world.world_type
    world.set_world_type(target_world_type)
    state.world_type = world.world_type
    state.lifeforms.clear()
    state.dna_profiles.clear()
    state.dna_id_counts.clear()
    state.dna_lineage.clear()
    state.lifeform_genetics.clear()
    state.pheromones.clear()
    state.plants.clear()
    state.death_ages.clear()
    state.lifeform_id_counter = 0
    latest_stats = None
    notification_manager.clear()
    event_manager.reset()
    event_manager.schedule_default_events()
    player_controller.reset()
    environment_modifiers["plant_regrowth"] = 1.0
    environment_modifiers["hunger_rate"] = 1.0
    environment_modifiers["moss_growth_speed"] = 1.0
    _last_food_multiplier = environment_modifiers["plant_regrowth"]
    _last_moss_growth = environment_modifiers["moss_growth_speed"]
    camera.reset()


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.5
    return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))


def determine_home_biome(dna_profile, biomes: List[BiomeRegion]) -> Optional[BiomeRegion]:
    if not biomes:
        return None

    size = (dna_profile['width'] + dna_profile['height']) / 2
    min_size = (settings.MIN_WIDTH + settings.MIN_HEIGHT) / 2
    max_size = (settings.MAX_WIDTH + settings.MAX_HEIGHT) / 2

    size_norm = _normalize(size, min_size, max_size)
    heat_tolerance = _normalize(dna_profile['energy'], 60, 120)
    hydration_dependence = 1.0 - heat_tolerance
    resilience = (
        _normalize(dna_profile['health'], 1, 220)
        + _normalize(dna_profile['defence_power'], 1, 110)
    ) / 2
    mobility = (
        _normalize(dna_profile['vision'], settings.VISION_MIN, settings.VISION_MAX)
        + (1.0 - size_norm)
    ) / 2
    longevity_factor = _normalize(dna_profile['longevity'], 800, 5200)
    aggression = _normalize(dna_profile['attack_power'], 1, 110)

    preferred_biome = None
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


def reset_dna_profiles():
    dna_profiles.clear()
    dna_home_biome.clear()
    for dna_id in range(settings.N_DNA_PROFILES):
        diet = random.choices(
            ['herbivore', 'omnivore', 'carnivore'],
            weights=[0.4, 0.35, 0.25],
        )[0]

        if diet == 'herbivore':
            attack_power = random.randint(5, 45)
            defence_power = random.randint(35, 85)
            vision_value = random.randint(settings.VISION_MIN, max(settings.VISION_MIN + 1, settings.VISION_MAX - 10))
            energy_value = random.randint(88, 110)
            longevity_value = random.randint(1600, 5200)
            social_tendency = random.uniform(0.6, 1.0)
            risk_tolerance = random.uniform(0.1, 0.5)
        elif diet == 'carnivore':
            attack_power = random.randint(45, 95)
            defence_power = random.randint(20, 65)
            vision_value = random.randint(max(settings.VISION_MIN, 28), settings.VISION_MAX)
            energy_value = random.randint(78, 96)
            longevity_value = random.randint(900, 3600)
            social_tendency = random.uniform(0.2, 0.6)
            risk_tolerance = random.uniform(0.6, 1.0)
        else:
            attack_power = random.randint(30, 85)
            defence_power = random.randint(25, 75)
            vision_value = random.randint(max(settings.VISION_MIN, 24), settings.VISION_MAX)
            energy_value = random.randint(82, 104)
            longevity_value = random.randint(1200, 4200)
            social_tendency = random.uniform(0.4, 0.85)
            risk_tolerance = random.uniform(0.4, 0.8)

        dna_profile = {
            'dna_id': dna_id,
            'width': random.randint(settings.MIN_WIDTH, settings.MAX_WIDTH),
            'height': random.randint(settings.MIN_HEIGHT, settings.MAX_HEIGHT),
            'color': (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            'health': random.randint(1, 200),
            'maturity': random.randint(settings.MIN_MATURITY, settings.MAX_MATURITY),
            'vision': vision_value,
            'defence_power': defence_power,
            'attack_power': attack_power,
            'energy': energy_value,
            'longevity': longevity_value,
            'diet': diet,
            'social': social_tendency,
            'risk_tolerance': risk_tolerance,
        }
        dna_profiles.append(dna_profile)
        if world.biomes:
            dna_home_biome[dna_profile['dna_id']] = determine_home_biome(dna_profile, world.biomes)
        else:
            dna_home_biome[dna_profile['dna_id']] = None


def init_lifeforms():
    cluster_centers = {}  # dna_id -> (x, y)

    for _ in range(settings.N_LIFEFORMS):

        dna_profile = random.choice(dna_profiles)
        dna_id = dna_profile["dna_id"]
        generation = 1

        preferred_biome = dna_home_biome.get(dna_id)

        # ---- CLUSTER CENTER PER DNA ----
        if dna_id not in cluster_centers:
            # kies eerste spawnpunt als cluster center
            cx, cy, _ = world.random_position(
                dna_profile["width"],
                dna_profile["height"],
                preferred_biome=preferred_biome
            )
            cluster_centers[dna_id] = (cx, cy)

        cx, cy = cluster_centers[dna_id]

        # ---- SPAWN MET CLUSTER RADIUS ----
        # (vereist kleine update in world.random_position())
        x = cx + random.randint(-160, 160)
        y = cy + random.randint(-160, 160)

        # clamp binnen world-bounds
        x = max(0, min(int(x), world.width - dna_profile["width"]))
        y = max(0, min(int(y), world.height - dna_profile["height"]))

        lifeform = Lifeform(state, x, y, dna_profile, generation)
        lifeforms.append(lifeform)

        logger.info(
            "Spawned lifeform %s (dna %s) cluster at (%.1f, %.1f)",
            lifeform.id, dna_id, x, y
        )

        spawn_attempts = 0
        while True:
            x, y, biome = world.random_position(
                dna_profile['width'],
                dna_profile['height'],
                preferred_biome=preferred_biome,
                avoid_positions=other_positions,
                min_distance=320,
                biome_padding=40,
            )
            center = (x + dna_profile['width'] / 2, y + dna_profile['height'] / 2)
            same_species_positions = spawn_positions_by_dna.setdefault(dna_profile['dna_id'], [])
            too_close_same = any(
                math.hypot(center[0] - px, center[1] - py) < 160 for px, py in same_species_positions
            )
            if not too_close_same or spawn_attempts > 120:
                same_species_positions.append(center)
                break
            spawn_attempts += 1

        lifeform = Lifeform(state, x, y, dna_profile, generation)
        lifeform.current_biome = biome
        lifeforms.append(lifeform)
        logger.info(
            "Spawned lifeform %s (dna %s) at (%.1f, %.1f) in biome %s",
            lifeform.id,
            dna_profile['dna_id'],
            x,
            y,
            biome.name if biome else "onbekend",
        )


def init_vegetation():
    plants.clear()
    abundance = environment_modifiers.get("plant_regrowth", 1.0)
    clusters = create_initial_clusters(world, count=4)
    for cluster in clusters:
        cluster.set_capacity_multiplier(abundance)
        cluster.set_growth_speed_modifier(environment_modifiers.get("moss_growth_speed", 1.0))
        plants.append(cluster)


def collect_population_stats(formatted_time_passed: str):
    stats = {
        "lifeform_count": len(lifeforms),
        "formatted_time": formatted_time_passed,
        "average_health": 0,
        "average_vision": 0,
        "average_gen": 0,
        "average_hunger": 0,
        "average_size": 0,
        "average_age": 0,
        "average_maturity": 0,
        "average_speed": 0,
        "average_cooldown": 0,
        "death_age_avg": sum(death_ages) / len(death_ages) if death_ages else 0,
        "dna_count": {},
        "dna_attribute_averages": {},
    }

    if lifeforms:
        count = len(lifeforms)
        totals = {
            "health_now": 0.0,
            "vision": 0.0,
            "generation": 0.0,
            "hunger": 0.0,
            "size": 0.0,
            "age": 0.0,
            "maturity": 0.0,
            "speed": 0.0,
            "reproduced_cooldown": 0.0,
        }
        dna_attributes = [
            "health",
            "vision",
            "attack_power_now",
            "defence_power_now",
            "speed",
            "maturity",
            "size",
            "longevity",
            "energy",
        ]
        dna_totals: Dict[int, Dict[str, float]] = {}

        for lifeform in lifeforms:
            totals["health_now"] += lifeform.health_now
            totals["vision"] += lifeform.vision
            totals["generation"] += lifeform.generation
            totals["hunger"] += lifeform.hunger
            totals["size"] += lifeform.size
            totals["age"] += lifeform.age
            totals["maturity"] += lifeform.maturity
            totals["speed"] += lifeform.speed
            totals["reproduced_cooldown"] += lifeform.reproduced_cooldown

            dna_entry = dna_totals.setdefault(
                lifeform.dna_id,
                {"count": 0, **{attr: 0.0 for attr in dna_attributes}},
            )
            dna_entry["count"] += 1
            for attribute in dna_attributes:
                dna_entry[attribute] += getattr(lifeform, attribute)

        stats["average_health"] = totals["health_now"] / count
        stats["average_vision"] = totals["vision"] / count
        stats["average_gen"] = totals["generation"] / count
        stats["average_hunger"] = totals["hunger"] / count
        stats["average_size"] = totals["size"] / count
        stats["average_age"] = totals["age"] / count
        stats["average_maturity"] = totals["maturity"] / count
        stats["average_speed"] = totals["speed"] / count
        stats["average_cooldown"] = totals["reproduced_cooldown"] / count
        stats["dna_count"] = {dna_id: data["count"] for dna_id, data in dna_totals.items()}
        stats["dna_attribute_averages"] = {
            dna_id: {attr: data[attr] / data["count"] for attr in dna_attributes}
            for dna_id, data in dna_totals.items()
            if data["count"]
        }

    return stats


def draw_stats_panel(surface, font_small, font_large, stats):
    text_lines = [
        f"Number of Lifeforms: {stats['lifeform_count']}",
        f"Total time passed: {stats['formatted_time']}",
        f"Average health: {int(stats['average_health'])}",
        f"Average vision: {int(stats['average_vision'])}",
        f"Average generation: {int(stats['average_gen'])}",
        f"Average hunger: {int(stats['average_hunger'])}",
        f"Average size: {int(stats['average_size'])}",
        f"Average age: {int(stats['average_age'])}",
        f"Average age of dying: {int(stats['death_age_avg'])}",
        f"Average maturity age: {int(stats['average_maturity'])}",
        f"Average speed: {round(stats['average_speed'], 2)}",
        f"Average reproduction cooldown: {round(stats['average_cooldown'])}",
        f"Total of DNA id's: {len(dna_profiles)}",
        "Alive lifeforms: "
    ]

    for idx, line in enumerate(text_lines):
        text_surface = font_small.render(line, True, settings.BLACK)
        surface.blit(text_surface, (50, 20 + idx * 20))

    y_offset = 300
    dna_count_sorted = sorted(stats['dna_count'].items(), key=lambda item: item[1], reverse=True)
    dna_attribute_averages = stats.get('dna_attribute_averages', {})
    for dna_id, count in dna_count_sorted:
        text = font_large.render(f"Nr. per dna_{dna_id}: {count}", True, settings.BLACK)
        surface.blit(text, (50, y_offset))
        y_offset += 35

        if show_dna_info:
            averages = dna_attribute_averages.get(dna_id)
            if averages:
                for attribute in [
                    "health",
                    "vision",
                    "attack_power_now",
                    "defence_power_now",
                    "speed",
                    "maturity",
                    "size",
                    "longevity",
                    "energy",
                ]:
                    attribute_value = averages.get(attribute)
                    if attribute_value is not None:
                        text = font_small.render(f"{attribute}: {round(attribute_value, 2)}", True, settings.BLACK)
                        surface.blit(text, (50, y_offset))
                        y_offset += 20


def run() -> None:
    global world, camera, notification_manager, event_manager, player_controller, start_time
    pygame.init()
    screen = pygame.display.set_mode((settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT))
    pygame.display.set_caption("Evolution Sim")

    world_surface = pygame.Surface((settings.WORLD_WIDTH, settings.WORLD_HEIGHT))

    world = World(
        settings.WORLD_WIDTH,
        settings.WORLD_HEIGHT,
        world_type=state.world_type,
        environment_modifiers=environment_modifiers,
    )
    camera = Camera(settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT, settings.WORLD_WIDTH, settings.WORLD_HEIGHT)
    camera.center_on(settings.WORLD_WIDTH / 2, settings.WORLD_HEIGHT / 2)
    logger.info(
        "Simulation run initialised with world size %sx%s and %s starting lifeforms",
        settings.WORLD_WIDTH,
        settings.WORLD_HEIGHT,
        settings.N_LIFEFORMS,
    )

    notification_manager = notification_context.notification_manager
    event_manager = EventManager(notification_manager, environment_modifiers)
    player_controller = PlayerController(notification_manager, dna_profiles, lifeforms)

    state.world = world
    state.world_type = world.world_type
    state.camera = camera
    state.events = event_manager
    state.player = player_controller
    state.notifications = notification_manager

    player_controller.reset()
    graph = Graph()

    running = True
    starting_screen = True
    paused = True

    global show_debug, show_leader, show_action, show_vision, show_dna_id, show_dna_info

    while running:
        delta_time = clock.tick(fps) / 1000.0
        start_button = pygame.Rect(settings.WINDOW_WIDTH - 260, settings.WINDOW_HEIGHT // 2 - 30, 200, 60)
        reset_button = pygame.Rect(30, settings.WINDOW_HEIGHT - 60, 180, 40)
        show_dna_button = pygame.Rect(reset_button.left, reset_button.top - 40, 24, 24)
        show_dna_info_button = pygame.Rect(show_dna_button.right + 10, show_dna_button.top, 24, 24)
        map_button_rects: List[Tuple[pygame.Rect, str]] = []

        if starting_screen:
            screen.fill(settings.BACKGROUND)
            title_font = pygame.font.Font(None, 48)
            info_font = pygame.font.Font(None, 26)
            button_font = pygame.font.Font(None, 30)

            pygame.draw.rect(screen, settings.GREEN, start_button)
            pygame.draw.rect(screen, settings.BLACK, start_button, 3)

            start_text = button_font.render("Start", True, settings.BLACK)
            text_rect = start_text.get_rect(center=start_button.center)
            screen.blit(start_text, text_rect)

            title_surface = title_font.render("Evolution Sim", True, settings.BLACK)
            screen.blit(title_surface, (50, 40))

            instructions = [
                "Kies een kaarttype en druk op Start om te beginnen.",
                "Gebruik WASD of de pijltjestoetsen om de camera te bewegen.",
                "Houd Shift ingedrukt om sneller te scrollen.",
                "Druk op M om het genlab te openen of sluiten.",
            ]
            for idx, line in enumerate(instructions):
                info_surface = info_font.render(line, True, settings.BLACK)
                screen.blit(info_surface, (50, 110 + idx * 32))

            map_title = info_font.render("Kaarttype", True, settings.BLACK)
            screen.blit(map_title, (50, 200))

            button_width = 320
            button_height = 50
            button_spacing = 18
            button_left = 50
            button_top = 240
            for idx, label in enumerate(MAP_TYPE_OPTIONS):
                rect = pygame.Rect(
                    button_left,
                    button_top + idx * (button_height + button_spacing),
                    button_width,
                    button_height,
                )
                map_button_rects.append((rect, label))
                is_selected = state.world_type == label
                fill_color = settings.SEA if is_selected else (235, 235, 235)
                pygame.draw.rect(screen, fill_color, rect, border_radius=8)
                pygame.draw.rect(screen, settings.BLACK, rect, 2, border_radius=8)
                option_text = button_font.render(label, True, settings.BLACK)
                screen.blit(option_text, option_text.get_rect(center=rect.center))

            selection_text = info_font.render(
                f"Geselecteerde kaart: {state.world_type}", True, settings.BLACK
            )
            screen.blit(
                selection_text,
                (
                    button_left,
                    button_top + len(MAP_TYPE_OPTIONS) * (button_height + button_spacing) + 10,
                ),
            )

            notification_manager.update()
            notification_manager.draw(screen, info_font)
        else:
            font1_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus8-Regular.ttf"
            expanded_path1 = os.path.expanduser(font1_path)
            font2_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus-Bold.ttf"
            expanded_path2 = os.path.expanduser(font2_path)

            font = pygame.font.Font(expanded_path1, 12)
            font2 = pygame.font.Font(expanded_path1, 18)
            font3 = pygame.font.Font(expanded_path2, 22)

            keys = pygame.key.get_pressed()
            horizontal = (keys[pygame.K_d] - keys[pygame.K_a])
            vertical = (keys[pygame.K_s] - keys[pygame.K_w])
            if not player_controller.management_mode:
                horizontal += keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
                vertical += keys[pygame.K_DOWN] - keys[pygame.K_UP]
            boost = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            camera.move(horizontal, vertical, boost)

            if not paused:
                world.update(pygame.time.get_ticks())
                world.draw(world_surface)

                current_time = datetime.datetime.now()
                time_passed = current_time - start_time
                formatted_time_passed = datetime.timedelta(seconds=int(time_passed.total_seconds()))
                formatted_time_passed = str(formatted_time_passed).split(".")[0]

                if death_ages:
                    death_age_avg = sum(death_ages) / len(death_ages)

                for plant in plants:
                    plant.set_size()
                    plant.regrow(world, plants)
                    plant.draw(world_surface)

                if pheromones:
                    active_pheromones: List[Pheromone] = []
                    for pheromone in pheromones:
                        pheromone.strength -= 10
                        if pheromone.strength > 0:
                            pheromone.draw(world_surface)
                            active_pheromones.append(pheromone)
                    pheromones[:] = active_pheromones

                lifeform_snapshot = list(lifeforms)
                average_maturity = (
                    sum(l.maturity for l in lifeform_snapshot) / len(lifeform_snapshot)
                    if lifeform_snapshot
                    else None
                )

                for lifeform in lifeform_snapshot:
                    # 1) DNA-afhankelijke eigenschappen & omgeving
                    lifeform.set_speed(average_maturity)
                    lifeform.calculate_attack_power()
                    lifeform.calculate_defence_power()
                    lifeform.check_group()  # boids / groepsgedrag, wordt gelezen door AI

                    # 2) Interne levensloop (hunger, age, energy, health, environment)
                    lifeform.progression(delta_time)

                    # 3) AI + movement + collision + boundary + stuck-detectie
                    #    - ai.update_brain() wordt binnen movement.update_movement aangeroepen
                    movement.update_movement(lifeform, state, delta_time)

                    # 4) Oriëntatie & groei
                    lifeform.update_angle()
                    lifeform.grow()
                    lifeform.set_size()  # nieuwe size na groei
                    lifeform.add_tail()  # pheromone-trail

                    # 5) Death-afhandeling (verwijdert zichzelf uit state.lifeforms)
                    if lifeform.handle_death():
                        continue

                    # 6) Rendering & overlays
                    draw_lifeform(world_surface, lifeform, settings)

                    if show_vision:
                        draw_lifeform_vision(world_surface, lifeform, settings)

                    if show_debug:
                        text = font.render(
                            f"Health: {lifeform.health_now} ID: {lifeform.id} "
                            f"cooldown {lifeform.reproduced_cooldown} "
                            f"gen: {lifeform.generation} "
                            f"dna_id {lifeform.dna_id} "
                            f"hunger: {lifeform.hunger} "
                            f"age: {lifeform.age} ",
                            True,
                            (0, 0, 0),
                        )
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 30)))

                    if show_dna_id:
                        text = font2.render(f"{lifeform.dna_id}", True, (0, 0, 0))
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 10)))

                    if show_leader and lifeform.is_leader:
                        text = font.render("L", True, (0, 0, 0))
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 30)))

                    if show_action:
                        text = font.render(
                            f"Current target, enemy: {lifeform.closest_enemy.id if lifeform.closest_enemy is not None else None}"
                            f", prey: {lifeform.closest_prey.id if lifeform.closest_prey is not None else None}, partner: "
                            f"{lifeform.closest_partner.id if lifeform.closest_partner is not None else None}, is following: "
                            f"{lifeform.closest_follower.id if lifeform.closest_follower is not None else None} ",
                            True,
                            settings.BLACK,
                        )
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 20)))

                    if lifeform.reproduced_cooldown > 0:
                        lifeform.reproduced_cooldown -= 1

                stats = collect_population_stats(formatted_time_passed)
                global latest_stats
                latest_stats = stats
                event_manager.schedule_default_events()
                event_manager.update(pygame.time.get_ticks(), stats, player_controller)
                _sync_food_abundance()
                _sync_moss_growth_speed()
                notification_manager.update()

                screen.blit(world_surface, (0, 0), area=camera.viewport)
                world.draw_weather_overview(screen, font2)
                draw_stats_panel(screen, font2, font3, stats)

                pygame.draw.rect(screen, settings.GREEN, reset_button)
                pygame.draw.rect(screen, settings.BLACK, reset_button, 2)
                pygame.draw.rect(screen, settings.GREEN, show_dna_button)
                pygame.draw.rect(screen, settings.BLACK, show_dna_button, 2)
                pygame.draw.rect(screen, settings.GREEN, show_dna_info_button)
                pygame.draw.rect(screen, settings.BLACK, show_dna_info_button, 2)

                reset_label = font.render("Reset", True, settings.BLACK)
                screen.blit(reset_label, (reset_button.x + 28, reset_button.y + 6))
                dna_label = font.render("DNA", True, settings.BLACK)
                screen.blit(dna_label, (show_dna_button.right + 8, show_dna_button.y + 4))
                dna_info_label = font.render("Info", True, settings.BLACK)
                screen.blit(dna_info_label, (show_dna_info_button.right + 8, show_dna_info_button.y + 4))
                if latest_stats:
                    draw_stats_panel(screen, font2, font3, latest_stats)
                notification_manager.draw(screen, font)
                player_controller.draw_overlay(screen, font2)
                event_manager.draw(screen, font2)

        pygame.display.flip()

        if not paused and not starting_screen and len(lifeforms) > 1:
            pass

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_n:
                    x = random.randint(0, max(0, world.width - 1))
                    y = random.randint(0, max(0, world.height - 1))

                    generation = 1

                    dna_profile = random.choice(dna_profiles)

                    lifeform = Lifeform(state, x, y, dna_profile, generation)
                    if random.randint(0, 100) < 10:
                        lifeform.is_leader = True
                    lifeforms.append(lifeform)

                elif event.key == pygame.K_b:
                    show_debug = not show_debug
                    notification_context.show_debug = show_debug
                elif event.key == pygame.K_l:
                    show_leader = not show_leader
                elif event.key == pygame.K_s:
                    show_action = not show_action
                    notification_context.show_action = show_action
                elif event.key == pygame.K_v:
                    show_vision = not show_vision
                elif event.key == pygame.K_d:
                    show_dna_id = not show_dna_id
                elif event.key == pygame.K_m:
                    player_controller.toggle_management()
                elif player_controller.management_mode:
                    if event.key == pygame.K_RIGHT:
                        player_controller.cycle_profile(1)
                    elif event.key == pygame.K_LEFT:
                        player_controller.cycle_profile(-1)
                    elif event.key == pygame.K_UP:
                        player_controller.adjust_attribute(1)
                    elif event.key == pygame.K_DOWN:
                        player_controller.adjust_attribute(-1)
                    elif event.key == pygame.K_TAB:
                        direction = -1 if (event.mod & pygame.KMOD_SHIFT) else 1
                        player_controller.cycle_attribute(direction)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if starting_screen:
                    if start_button.collidepoint(event.pos):
                        reset_list_values(state.world_type)
                        reset_dna_profiles()
                        init_lifeforms()
                        init_vegetation()
                        start_time = datetime.datetime.now()
                        notification_manager.add("Simulatie gestart", settings.GREEN)
                        starting_screen = False
                        paused = False
                        notification_manager.add(
                            "Gebruik WASD of pijltjes om de camera te bewegen (Shift = snel)",
                            settings.BLUE,
                        )
                    else:
                        previous_type = state.world_type
                        for rect, label in map_button_rects:
                            if rect.collidepoint(event.pos):
                                world.set_world_type(label)
                                state.world_type = world.world_type
                                if previous_type != state.world_type:
                                    notification_manager.add(
                                        f"Kaarttype ingesteld op {state.world_type}",
                                        settings.SEA,
                                    )
                                camera.reset()
                                break
                else:
                    if reset_button.collidepoint(event.pos):
                        reset_list_values(state.world_type)
                        notification_manager.add("Simulatie gereset", settings.BLUE)
                        starting_screen = True
                        paused = True
                    if show_dna_button.collidepoint(event.pos):
                        notification_manager.add("DNA-ID overlay gewisseld", settings.SEA)
                        show_dna_id = not show_dna_id
                    if show_dna_info_button.collidepoint(event.pos):
                        show_dna_info = not show_dna_info

    pygame.quit()

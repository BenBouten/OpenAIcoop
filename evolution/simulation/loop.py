"""Main pygame simulation loop for the evolution project."""

from __future__ import annotations

import datetime
import logging
import os
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:  # pragma: no cover - optional dependency
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    MATPLOTLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback when matplotlib is missing
    plt = None
    FigureCanvasAgg = None
    MATPLOTLIB_AVAILABLE = False

import pygame

from ..config import settings
from ..entities import movement
from ..entities.lifeform import Lifeform
from ..rendering.camera import Camera
from ..rendering.draw_lifeform import draw_lifeform, draw_lifeform_vision
from ..rendering.effects import EffectManager
from ..rendering.gameplay_panel import GameplaySettingsPanel, SliderConfig
from ..rendering.lifeform_inspector import LifeformInspector
from ..systems import stats as stats_system
from ..systems.events import EventManager
from ..systems.notifications import NotificationManager
from ..systems.player import PlayerController
from ..world.world import World
from . import bootstrap, environment
from .state import SimulationState


# ---------------------------------------------------------------------------
# Notifications & logging
# ---------------------------------------------------------------------------

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

# Centrale sim-state (gedeeld met Lifeform e.d.)
state = SimulationState()

notification_context = NotificationContext(NotificationManager())
state.notification_context = notification_context
state.notifications = notification_context.notification_manager


MAP_TYPE_OPTIONS = [
    "Archipelago",
    "Rift Valley",
    "Desert–Jungle Split",
]


class Graph:
    """Render a statistics bar chart using matplotlib when available."""

    def __init__(self):
        self.surface: Optional[pygame.Surface] = None
        self._needs_redraw = False
        self.available = MATPLOTLIB_AVAILABLE
        if not self.available:
            logger.warning("Matplotlib is not available; DNA graph will be disabled")
            return

        assert plt is not None and FigureCanvasAgg is not None
        self.figure, self.axes = plt.subplots()
        self.canvas = FigureCanvasAgg(self.figure)
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")
        self._needs_redraw = True

    def update(self, death_ages_by_dna: Dict[int, List[int]]) -> None:
        if not self.available:
            return

        self.axes.clear()
        dna_ids = []
        avg_ages = []
        for dna_id, ages in death_ages_by_dna.items():
            if not ages:
                continue
            dna_ids.append(dna_id)
            avg_ages.append(sum(ages) / len(ages))
        self.axes.bar(dna_ids, avg_ages)
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")
        self._needs_redraw = True

    def draw(self, screen: pygame.Surface) -> None:
        if not self.available:
            return

        if self._needs_redraw or self.surface is None:
            try:
                self.canvas.draw()
                raw = bytes(self.canvas.buffer_rgba())
                width, height = self.canvas.get_width_height()
                graph_surface = pygame.image.frombuffer(raw, (width, height), "RGBA")
                self.surface = graph_surface.convert_alpha()
                self._needs_redraw = False
            except (ValueError, pygame.error) as exc:
                logger.warning("Unable to render DNA graph: %s", exc)
                self.available = False
                self.surface = None
                return

        if self.surface:
            screen.blit(self.surface, (0, 0))


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _load_font(preferred_path: str, size: int) -> pygame.font.Font:
    """Attempt to load a custom font, falling back to the default if missing."""

    expanded_path = os.path.expanduser(preferred_path)
    if expanded_path and os.path.isfile(expanded_path):
        try:
            return pygame.font.Font(expanded_path, size)
        except OSError as exc:
            logger.warning("Unable to load font '%s': %s", expanded_path, exc)
    else:
        logger.debug("Custom font '%s' not found; using default font", expanded_path)

    return pygame.font.Font(None, size)


# ---------------------------------------------------------------------------
# Globale referenties / kortere aliassen
# ---------------------------------------------------------------------------

world: World
camera: Camera
notification_manager: NotificationManager = notification_context.notification_manager
event_manager: EventManager
player_controller: PlayerController

lifeforms: List[Lifeform] = state.lifeforms
dna_profiles: List[dict] = state.dna_profiles
plants: List = state.plants

death_ages: List[int] = state.death_ages
latest_stats: Optional[Dict[str, float]] = None

environment_modifiers: Dict[str, float] = state.environment_modifiers

show_debug = False
show_leader = False
show_action = False
show_vision = False
show_dna_id = True
show_dna_info = False

start_time = datetime.datetime.now()
clock = pygame.time.Clock()
fps = settings.FPS



def draw_stats_panel(
    surface: pygame.Surface,
    font_small: pygame.font.Font,
    font_large: pygame.font.Font,
    stats: Dict[str, object],
) -> None:
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
        f"Average mass: {round(stats['average_mass'], 2)}",
        f"Average reach: {round(stats['average_reach'], 2)}",
        f"Average maintenance cost: {round(stats['average_maintenance_cost'], 3)}",
        f"Average sensory rays: {round(stats['average_perception_rays'], 1)}",
        f"Average hearing range: {round(stats['average_hearing_range'], 1)}",
        f"Average reproduction cooldown: {round(stats['average_cooldown'])}",
        f"Total of DNA id's: {len(dna_profiles)}",
        "Alive lifeforms: ",
    ]

    for idx, line in enumerate(text_lines):
        text_surface = font_small.render(line, True, settings.BLACK)
        surface.blit(text_surface, (50, 20 + idx * 20))

    y_offset = 300
    dna_count_sorted = sorted(
        stats['dna_count'].items(),
        key=lambda item: item[1],
        reverse=True,
    )
    dna_attribute_averages = stats.get('dna_attribute_averages', {})
    for dna_id, count in dna_count_sorted:
        text = font_large.render(
            f"Nr. per dna_{dna_id}: {count}",
            True,
            settings.BLACK,
        )
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
                    "mass",
                    "reach",
                    "perception_rays",
                    "maintenance_cost",
                    "hearing_range",
                ]:
                    attribute_value = averages.get(attribute)
                    if attribute_value is not None:
                        text = font_small.render(
                            f"{attribute}: {round(attribute_value, 2)}",
                            True,
                            settings.BLACK,
                        )
                        surface.blit(text, (50, y_offset))
                        y_offset += 20


# ---------------------------------------------------------------------------
# Hoofd-loop
# ---------------------------------------------------------------------------

def run() -> None:
    """Start de pygame-simulatie."""
    global world, camera, notification_manager, event_manager, player_controller
    global latest_stats, show_debug, show_leader, show_action, show_vision, show_dna_id, show_dna_info
    global start_time

    pygame.init()
    screen = pygame.display.set_mode(
        (settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT),
    )
    pygame.display.set_caption("Evolution Sim")

    world_surface = pygame.Surface(
        (settings.WORLD_WIDTH, settings.WORLD_HEIGHT),
    )

    font1_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus8-Regular.ttf"
    font2_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus-Bold.ttf"
    font = _load_font(font1_path, 12)
    font2 = _load_font(font1_path, 18)
    font3 = _load_font(font2_path, 22)

    panel_width = 260
    panel_margin = 16
    panel_rect = pygame.Rect(
        settings.WINDOW_WIDTH - panel_width - panel_margin,
        20,
        panel_width,
        settings.WINDOW_HEIGHT - 40,
    )

    def _set_environment_modifier(key: str, value: float) -> None:
        numeric_value = float(value)
        environment_modifiers[key] = numeric_value
        state.environment_modifiers[key] = numeric_value
        if state.world is not None:
            state.world.set_environment_modifiers(state.environment_modifiers)
        if key == "plant_regrowth":
            environment.sync_food_abundance(state)
        elif key == "moss_growth_speed":
            environment.sync_moss_growth_speed(state)

    def _set_mutation_rate(value: float) -> None:
        settings.MUTATION_CHANCE = int(round(value))

    def _set_max_lifeforms(value: float) -> None:
        settings.MAX_LIFEFORMS = int(round(value))

    def _set_reproduction_cooldown(value: float) -> None:
        cooldown = int(round(value))
        settings.REPRODUCING_COOLDOWN_VALUE = cooldown
        settings.POPULATION_CAP_RETRY_COOLDOWN = max(1, cooldown // 2)

    def _set_energy_recovery(value: float) -> None:
        settings.ENERGY_RECOVERY_PER_SECOND = float(value)

    def _set_age_rate(value: float) -> None:
        settings.AGE_RATE_PER_SECOND = float(value)

    def _set_hunger_penalty(value: float) -> None:
        settings.HUNGER_HEALTH_PENALTY_PER_SECOND = float(value)
        settings.EXTREME_HUNGER_HEALTH_PENALTY_PER_SECOND = float(value) * 10

    def _initialise_population() -> None:
        global latest_stats
        bootstrap.generate_dna_profiles(state, world)
        bootstrap.spawn_lifeforms(state, world)
        bootstrap.seed_vegetation(state, world)
        environment.sync_food_abundance(state)
        environment.sync_moss_growth_speed(state)
        latest_stats = None

    def _build_slider_configs() -> List[SliderConfig]:
        return [
            SliderConfig(
                key="food_abundance",
                label="Food abundance",
                min_value=0.2,
                max_value=3.0,
                start_value=environment_modifiers.get("plant_regrowth", 1.0),
                step=0.05,
                value_format="{value:.2f}x",
                callback=lambda value: _set_environment_modifier("plant_regrowth", value),
            ),
            SliderConfig(
                key="moss_growth_speed",
                label="Moss growth speed",
                min_value=0.2,
                max_value=3.0,
                start_value=environment_modifiers.get("moss_growth_speed", 1.0),
                step=0.05,
                value_format="{value:.2f}x",
                callback=lambda value: _set_environment_modifier("moss_growth_speed", value),
            ),
            SliderConfig(
                key="hunger_rate",
                label="Hunger rate",
                min_value=0.2,
                max_value=2.0,
                start_value=environment_modifiers.get("hunger_rate", 1.0),
                step=0.05,
                value_format="{value:.2f}x",
                callback=lambda value: _set_environment_modifier("hunger_rate", value),
            ),
            SliderConfig(
                key="weather_intensity",
                label="Weather intensity",
                min_value=0.0,
                max_value=2.0,
                start_value=environment_modifiers.get("weather_intensity", 1.0),
                step=0.05,
                value_format="{value:.2f}x",
                callback=lambda value: _set_environment_modifier("weather_intensity", value),
            ),
            SliderConfig(
                key="mutation_rate",
                label="Mutation rate",
                min_value=0.0,
                max_value=35.0,
                start_value=float(settings.MUTATION_CHANCE),
                step=1.0,
                value_format="{value:.0f}%",
                callback=_set_mutation_rate,
            ),
            SliderConfig(
                key="max_lifeforms",
                label="Max lifeforms",
                min_value=50.0,
                max_value=400.0,
                start_value=float(settings.MAX_LIFEFORMS),
                step=10.0,
                value_format="{value:.0f}",
                callback=_set_max_lifeforms,
            ),
            SliderConfig(
                key="reproduction_cooldown",
                label="Reproduction cooldown",
                min_value=20.0,
                max_value=200.0,
                start_value=float(settings.REPRODUCING_COOLDOWN_VALUE),
                step=5.0,
                value_format="{value:.0f} fr",
                callback=_set_reproduction_cooldown,
            ),
            SliderConfig(
                key="energy_recovery",
                label="Energy recovery",
                min_value=5.0,
                max_value=40.0,
                start_value=float(settings.ENERGY_RECOVERY_PER_SECOND),
                step=1.0,
                value_format="{value:.0f}/s",
                callback=_set_energy_recovery,
            ),
            SliderConfig(
                key="age_rate",
                label="Age rate",
                min_value=1.0,
                max_value=10.0,
                start_value=float(settings.AGE_RATE_PER_SECOND),
                step=0.5,
                value_format="{value:.1f}/s",
                callback=_set_age_rate,
            ),
            SliderConfig(
                key="hunger_penalty",
                label="Hunger damage",
                min_value=0.0,
                max_value=10.0,
                start_value=float(settings.HUNGER_HEALTH_PENALTY_PER_SECOND),
                step=0.5,
                value_format="{value:.1f}/s",
                callback=_set_hunger_penalty,
            ),
        ]

    gameplay_panel = GameplaySettingsPanel(
        panel_rect,
        font2,
        font3,
        _build_slider_configs(),
    )

    def _lifeform_at_screen_pos(position: Tuple[int, int]) -> Optional[Lifeform]:
        if not lifeforms:
            return None
        screen_x, screen_y = position
        world_x = camera.viewport.x + screen_x
        world_y = camera.viewport.y + screen_y
        best: Optional[Lifeform] = None
        best_distance = float("inf")
        for lifeform in lifeforms:
            if lifeform.health_now <= 0:
                continue
            rect = lifeform.rect.inflate(6, 6)
            if not rect.collidepoint(world_x, world_y):
                continue
            centerx, centery = lifeform.rect.center
            distance = float((centerx - world_x) ** 2 + (centery - world_y) ** 2)
            if distance < best_distance:
                best_distance = distance
                best = lifeform
        return best

    # Wereld & camera
    world = World(
        settings.WORLD_WIDTH,
        settings.WORLD_HEIGHT,
        world_type=state.world_type,
        environment_modifiers=environment_modifiers,
    )
    camera = Camera(
        settings.WINDOW_WIDTH,
        settings.WINDOW_HEIGHT,
        settings.WORLD_WIDTH,
        settings.WORLD_HEIGHT,
    )
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
    effects_manager = EffectManager()
    effects_manager.set_font(font2)

    bootstrap.reset_simulation(
        state,
        world,
        camera,
        event_manager,
        player_controller,
        notification_manager,
        effects_manager,
        state.world_type,
    )
    graph = Graph()
    inspector = LifeformInspector(state, font2, font3)

    running = True
    starting_screen = True
    paused = True
    fullscreen = False

    while running:
        delta_time = clock.tick(fps) / 1000.0
        start_button = pygame.Rect(
            panel_rect.left - 220,
            settings.WINDOW_HEIGHT // 2 - 30,
            200,
            60,
        )
        reset_button = pygame.Rect(30, settings.WINDOW_HEIGHT - 60, 180, 40)
        show_dna_button = pygame.Rect(
            reset_button.left,
            reset_button.top - 40,
            24,
            24,
        )
        show_dna_info_button = pygame.Rect(
            show_dna_button.right + 10,
            show_dna_button.top,
            24,
            24,
        )
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

            button_width = 180
            button_height = 32
            for idx, label in enumerate(MAP_TYPE_OPTIONS):
                rect = pygame.Rect(
                    50,
                    260 + idx * (button_height + 10),
                    button_width,
                    button_height,
                )
                map_button_rects.append((rect, label))
                color = settings.SEA if label == state.world_type else settings.GREEN
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, settings.BLACK, rect, 2)
                option_surface = button_font.render(label, True, settings.BLACK)
                option_rect = option_surface.get_rect(center=rect.center)
                screen.blit(option_surface, option_rect)
            gameplay_panel.draw(screen)
            notification_manager.update()
            notification_manager.draw(screen, info_font)

        else:
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
                formatted_time_passed = datetime.timedelta(
                    seconds=int(time_passed.total_seconds()),
                )
                formatted_time_passed = str(formatted_time_passed).split(".")[0]

                if death_ages:
                    _ = sum(death_ages) / len(death_ages)  # death_age_avg, nu niet gebruikt

                for plant in plants:
                    plant.set_size()
                    plant.regrow(world, plants)
                    plant.draw(world_surface)

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
                    lifeform.check_group()

                    # 2) Interne levensloop
                    lifeform.progression(delta_time)

                    # 3) AI + movement + collision
                    movement.update_movement(lifeform, state, delta_time)

                    # 4) Oriëntatie & groei
                    lifeform.update_angle()
                    lifeform.grow()
                    lifeform.set_size()

                    # 5) Death-afhandeling
                    if lifeform.handle_death():
                        continue

                    # 6) Rendering
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
                        world_surface.blit(
                            text,
                            (int(lifeform.x), int(lifeform.y - 30)),
                        )

                    if show_dna_id:
                        text = font2.render(f"{lifeform.dna_id}", True, (0, 0, 0))
                        world_surface.blit(
                            text,
                            (int(lifeform.x), int(lifeform.y - 10)),
                        )

                    if show_leader and lifeform.is_leader:
                        text = font.render("L", True, (0, 0, 0))
                        world_surface.blit(
                            text,
                            (int(lifeform.x), int(lifeform.y - 30)),
                        )

                    if show_action:
                        text = font.render(
                            f"Current target, enemy: "
                            f"{lifeform.closest_enemy.id if lifeform.closest_enemy is not None else None}"
                            f", prey: "
                            f"{lifeform.closest_prey.id if lifeform.closest_prey is not None else None}, partner: "
                            f"{lifeform.closest_partner.id if lifeform.closest_partner is not None else None}, is following: "
                            f"{lifeform.closest_follower.id if lifeform.closest_follower is not None else None} ",
                            True,
                            settings.BLACK,
                        )
                        world_surface.blit(
                            text,
                            (int(lifeform.x), int(lifeform.y - 20)),
                        )

                    if lifeform.reproduced_cooldown > 0:
                        lifeform.reproduced_cooldown -= 1

                effects_manager.update(delta_time)
                effects_manager.draw(world_surface)

                stats = stats_system.collect_population_stats(
                    state, formatted_time_passed
                )
                latest_stats = stats
                event_manager.schedule_default_events()
                event_manager.update(
                    pygame.time.get_ticks(),
                    stats,
                    player_controller,
                )
                environment.sync_food_abundance(state)
                environment.sync_moss_growth_speed(state)
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
                screen.blit(
                    reset_label,
                    (reset_button.x + 28, reset_button.y + 6),
                )
                dna_label = font.render("DNA", True, settings.BLACK)
                screen.blit(
                    dna_label,
                    (show_dna_button.right + 8, show_dna_button.y + 4),
                )
                dna_info_label = font.render("Info", True, settings.BLACK)
                screen.blit(
                    dna_info_label,
                    (show_dna_info_button.right + 8, show_dna_info_button.y + 4),
                )

                if latest_stats:
                    draw_stats_panel(screen, font2, font3, latest_stats)

                notification_manager.draw(screen, font)
                player_controller.draw_overlay(screen, font2)
                event_manager.draw(screen, font2)

            if paused:
                screen.blit(world_surface, (0, 0), area=camera.viewport)
            inspector.draw_highlight(screen, camera)
            gameplay_panel.draw(screen)
            inspector.draw(screen)

        pygame.display.flip()

        # Event handling
        for event in pygame.event.get():
            if inspector.handle_event(event):
                continue
            if gameplay_panel.handle_event(event):
                continue
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode(
                            (settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT),
                            pygame.FULLSCREEN,
                        )
                    else:
                        screen = pygame.display.set_mode(
                            (settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT),
                        )
                    panel_rect.x = screen.get_width() - panel_width - panel_margin
                    gameplay_panel = GameplaySettingsPanel(
                        panel_rect,
                        font2,
                        font3,
                        _build_slider_configs(),
                    )
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
                        bootstrap.reset_simulation(
                            state,
                            world,
                            camera,
                            event_manager,
                            player_controller,
                            notification_manager,
                            effects_manager,
                            state.world_type,
                        )
                        inspector.clear()
                        _initialise_population()
                        start_time = datetime.datetime.now()
                        notification_manager.add("Simulatie gestart", settings.GREEN)
                        starting_screen = False
                        paused = False
                        camera.reset()
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
                        bootstrap.reset_simulation(
                            state,
                            world,
                            camera,
                            event_manager,
                            player_controller,
                            notification_manager,
                            effects_manager,
                            state.world_type,
                        )
                        inspector.clear()
                        latest_stats = None
                        notification_manager.add(
                            "Simulatie gereset",
                            settings.BLUE,
                        )
                        starting_screen = True
                        paused = True
                    elif show_dna_button.collidepoint(event.pos):
                        notification_manager.add("DNA-ID overlay gewisseld", settings.SEA)
                        show_dna_id = not show_dna_id
                    elif show_dna_info_button.collidepoint(event.pos):
                        show_dna_info = not show_dna_info
                    else:
                        selected_lifeform = _lifeform_at_screen_pos(event.pos)
                        if selected_lifeform is not None:
                            inspector.select(selected_lifeform)
                        else:
                            inspector.clear()

    pygame.quit()

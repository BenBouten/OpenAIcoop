"""Main pygame simulation loop for the evolution project."""

from __future__ import annotations

import datetime
import logging
import math
import os
import random
from collections import deque
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Deque, Dict, List, Optional, Tuple

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
from pygame.math import Vector2

from ..config import settings
from ..entities import movement
from ..entities.lifeform import Lifeform
from ..rendering.camera import Camera
from ..rendering.draw_lifeform import draw_lifeform, draw_lifeform_vision
from ..rendering.effects import EffectManager
from ..rendering.gameplay_panel import GameplaySettingsPanel, SliderConfig
from ..rendering.lifeform_inspector import LifeformInspector
from ..rendering.tools_panel import EditorTool, ToolsPanel
from ..rendering.stats_window import StatsWindow
from ..physics.test_creatures import TestCreature, build_fin_swimmer_prototype
from ..systems import stats as stats_system
from ..systems.events import EventManager
from ..systems.notifications import NotificationManager
from ..systems.player import PlayerController
from ..world.types import Barrier
from ..world.vegetation import create_cluster_from_brush
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
    "Abyssal Ocean",
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


MODULE_COLORS = {
    "core": (70, 125, 160),
    "head": (235, 232, 198),
    "limb": (120, 200, 220),
    "propulsion": (255, 162, 120),
    "sensor": (214, 235, 255),
}


@dataclass
class PrototypeSwimPreview:
    """Lightweight preview that animates a prototype creature in water."""

    creature: TestCreature
    position: Vector2 = field(default_factory=lambda: Vector2(0.0, 0.0))
    velocity: Vector2 = field(default_factory=lambda: Vector2(70.0, 0.0))
    elapsed: float = 0.0
    bounds: Optional[pygame.Rect] = None
    needs_reset: bool = True
    trail: Deque[Vector2] = field(default_factory=lambda: deque(maxlen=40))
    layout: Dict[str, Vector2] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.layout = self._layout_graph(self.creature.graph)

    @staticmethod
    def _layout_graph(graph) -> Dict[str, Vector2]:
        layout: Dict[str, Vector2] = {}
        queue: List[Tuple[str, float, float]] = [(graph.root_id, 0.0, 0.0)]
        visited: set[str] = set()
        while queue:
            node_id, offset_x, offset_y = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            layout[node_id] = Vector2(offset_x, offset_y)
            children = list(graph.children_of(node_id).keys())
            if not children:
                continue
            spread = max(1, len(children))
            for idx, child_id in enumerate(children):
                child_offset_x = offset_x + 1.0
                child_offset_y = offset_y + (idx - (spread - 1) / 2.0) * 0.8
                queue.append((child_id, child_offset_x, child_offset_y))
        return layout

    def _ensure_bounds(self, rect: pygame.Rect) -> None:
        if (
            self.bounds is None
            or self.needs_reset
            or self.bounds.topleft != rect.topleft
            or self.bounds.size != rect.size
        ):
            self.bounds = rect.copy()
            self.position = Vector2(rect.left + rect.width * 0.2, rect.centery)
            self.velocity = Vector2(85.0, 0.0)
            self.trail.clear()
            self.needs_reset = False

    def update(self, dt: float, rect: pygame.Rect) -> None:
        self._ensure_bounds(rect)
        bounds = self.bounds or rect
        self.elapsed += dt
        thrust_vector = self.creature.step(dt)
        mass = max(1.0, self.creature.physics.mass)
        swim_force = abs(thrust_vector.x)
        acceleration = Vector2((swim_force / mass) * 8.0, 0.0)
        drag = -self.velocity * (0.35 + self.creature.physics.drag_coefficient * 0.05)
        buoyancy = Vector2(0.0, -14.0)
        self.velocity += (acceleration + drag + buoyancy) * dt
        self.velocity.y += math.sin(self.elapsed * 0.9) * 18.0 * dt
        self.velocity.x = max(40.0, min(self.velocity.x, 170.0))
        self.position += self.velocity * dt
        self.position.y += math.sin(self.elapsed * 3.2) * 0.6
        self.trail.appendleft(self.position.copy())
        margin = 30
        min_y = bounds.top + margin
        max_y = bounds.bottom - margin
        if self.position.y < min_y:
            self.position.y = min_y
            self.velocity.y *= -0.35
        elif self.position.y > max_y:
            self.position.y = max_y
            self.velocity.y *= -0.35
        if self.position.x > bounds.right + 120:
            self.position.x = bounds.left - 60
        elif self.position.x < bounds.left - 120:
            self.position.x = bounds.right + 120

    def render(self, surface: pygame.Surface, rect: pygame.Rect, dt: float) -> None:
        self.update(dt, rect)
        self._draw_trail(surface)
        self._draw_creature(surface)

    def _draw_trail(self, surface: pygame.Surface) -> None:
        if not self.trail:
            return
        for idx, point in enumerate(list(self.trail)[:24]):
            fade = max(40, 180 - idx * 6)
            radius = max(1, 5 - idx // 4)
            color = (180 + idx * 2, 240, 255)
            pygame.draw.circle(surface, color, (int(point.x) - idx * 2, int(point.y)), radius)

    def _draw_creature(self, surface: pygame.Surface) -> None:
        if not self.layout:
            return
        scale_x = 70
        scale_y = 45
        positions: Dict[str, Vector2] = {}

        for node_id, offset in self.layout.items():
            base_center = Vector2(
                self.position.x + offset.x * scale_x,
                self.position.y + offset.y * scale_y,
            )
            sway_phase = self.elapsed * 4.6 + offset.x * 0.65
            lateral_sway = math.sin(sway_phase) * (5 + offset.x * 3)
            vertical_sway = math.sin(sway_phase * 0.7 + offset.y) * (4 + abs(offset.y) * 2)
            base_center.x += lateral_sway
            base_center.y += vertical_sway
            positions[node_id] = base_center

        def _vec(point: Vector2) -> Tuple[int, int]:
            return (int(point.x), int(point.y))

        for node_id, node in self.creature.graph.nodes.items():
            parent_id = node.parent
            if not parent_id:
                continue
            if parent_id not in positions or node_id not in positions:
                continue
            start = positions[parent_id]
            end = positions[node_id]
            direction = end - start
            control = (start + end) / 2
            normal = Vector2(-direction.y, direction.x)
            if normal.length_squared() > 1e-3:
                normal = normal.normalize()
                bend = math.sin(self.elapsed * 2.4 + self.layout[node_id].x * 0.8)
                normal *= bend * min(26.0, direction.length() * 0.45)
            control += normal
            width = 6 if node.module.module_type == "core" else 4
            pygame.draw.lines(
                surface,
                (18, 42, 68),
                False,
                [_vec(start), _vec(control), _vec(end)],
                width,
            )

        for node_id, offset in self.layout.items():
            node = self.creature.graph.get_node(node_id)
            module = node.module
            center = positions[node_id]
            length = max(14, int(module.size[2] * 30))
            height = max(12, int(module.size[1] * 28))
            rect = pygame.Rect(0, 0, length, height)
            rect.center = (int(center.x), int(center.y))
            color = MODULE_COLORS.get(module.module_type, (140, 210, 220))
            pygame.draw.ellipse(surface, color, rect)
            pygame.draw.ellipse(surface, (10, 25, 40), rect, 2)
            if module.module_type == "propulsion":
                flame = rect.copy()
                flame.width = max(6, rect.width // 3)
                flame.left = rect.left - flame.width + 4
                pygame.draw.ellipse(surface, (255, 200, 150), flame)
            if module.module_type == "head":
                eye_center = (rect.centerx + rect.width // 4, rect.centery - rect.height // 4)
                pygame.draw.circle(surface, (15, 30, 60), eye_center, 4)


def _draw_vertical_gradient(surface: pygame.Surface, rect: pygame.Rect, top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> None:
    height = rect.height
    if height <= 0:
        return
    for row in range(height):
        ratio = row / max(1, height - 1)
        color = tuple(
            int(top_color[idx] + (bottom_color[idx] - top_color[idx]) * ratio)
            for idx in range(3)
        )
        pygame.draw.line(surface, color, (rect.left, rect.top + row), (rect.right, rect.top + row))

    caustics = pygame.Surface(rect.size, pygame.SRCALPHA)
    for wave in range(4):
        offset = math.sin(pygame.time.get_ticks() / 900.0 + wave) * 18
        arc_rect = pygame.Rect(0, int(wave * rect.height / 4 + offset), rect.width, rect.height // 2)
        pygame.draw.arc(caustics, (255, 255, 255, 32), arc_rect, 0, math.pi, 2)
    surface.blit(caustics, rect.topleft)


def _draw_modular_preview(
    surface: pygame.Surface,
    rect: pygame.Rect,
    preview: Optional[PrototypeSwimPreview],
    info_font: pygame.font.Font,
    delta_time: float,
) -> None:
    if rect.width <= 0 or rect.height <= 0:
        return
    _draw_vertical_gradient(surface, rect, (120, 210, 230), (6, 28, 60))
    if preview is None:
        placeholder = info_font.render(
            "Klik op 'Test prototype' om de zwemtest te zien.",
            True,
            settings.BLACK,
        )
        text_rect = placeholder.get_rect(center=rect.center)
        surface.blit(placeholder, text_rect)
    else:
        preview.render(surface, rect, delta_time)
    pygame.draw.rect(surface, (15, 30, 60), rect, 2)


def _draw_ocean_showcase(
    surface: pygame.Surface,
    preview: Optional[PrototypeSwimPreview],
    info_font: pygame.font.Font,
    delta_time: float,
    *,
    bounds_margin: int = 90,
) -> None:
    ocean_rect = surface.get_rect()
    _draw_vertical_gradient(surface, ocean_rect, (120, 210, 230), (6, 28, 60))
    if preview is not None:
        swim_rect = ocean_rect.inflate(-bounds_margin * 2, -bounds_margin)
        preview.render(surface, swim_rect, delta_time)
    else:
        placeholder = info_font.render("Klik op Start om het testwezen te zien zwemmen.", True, settings.BLACK)
        surface.blit(
            placeholder,
            (
                ocean_rect.centerx - placeholder.get_width() // 2,
                ocean_rect.centery - placeholder.get_height() // 2,
            ),
        )
    pygame.draw.line(
        surface,
        (10, 25, 45),
        (0, bounds_margin // 2),
        (surface.get_width(), bounds_margin // 2),
        3,
    )


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
carcasses: List = state.carcasses

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

    def _run_modular_creature_test() -> Tuple[Dict[str, float], PrototypeSwimPreview]:
        """Build and sample the first modular creature prototype."""

        creature = build_fin_swimmer_prototype()
        aggregation = creature.graph.aggregate_physics_stats()
        dt = 1.0 / 60.0
        samples = []
        for _ in range(180):
            thrust_vector = creature.step(dt)
            samples.append(thrust_vector.length())
        average_thrust = sum(samples) / len(samples) if samples else 0.0
        peak_thrust = max(samples) if samples else 0.0
        report = {
            "name": creature.name,
            "modules": float(len(creature.graph)),
            "mass": creature.physics.mass,
            "drag": creature.physics.drag_coefficient,
            "avg_thrust": average_thrust,
            "peak_thrust": peak_thrust,
            "frontal_area": aggregation.frontal_area,
        }
        return report, PrototypeSwimPreview(creature)

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
        stats_window.clear()

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
    stats_window = StatsWindow(font2, font3)

    def _lifeform_at_screen_pos(position: Tuple[int, int]) -> Optional[Lifeform]:
        if not lifeforms:
            return None
        world_x, world_y = camera.screen_to_world(position)
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
    tools_panel = ToolsPanel(
        font2,
        font3,
        topleft=(24, settings.WINDOW_HEIGHT - 360),
        available_biomes=world.biomes,
    )

    def _screen_to_world(position: Tuple[int, int]) -> Tuple[float, float]:
        return camera.screen_to_world(position)

    def _clamp_rect(rect: pygame.Rect) -> pygame.Rect:
        left = max(0, rect.left)
        top = max(0, rect.top)
        right = min(world.width, rect.right)
        bottom = min(world.height, rect.bottom)
        rect.update(int(left), int(top), max(1, int(right - left)), max(1, int(bottom - top)))
        return rect

    def _world_rect_from_points(
        start: Tuple[float, float], end: Tuple[float, float]
    ) -> pygame.Rect:
        left = min(start[0], end[0])
        top = min(start[1], end[1])
        width = abs(end[0] - start[0])
        height = abs(end[1] - start[1])
        rect = pygame.Rect(int(left), int(top), max(1, int(width)), max(1, int(height)))
        return _clamp_rect(rect)

    def _apply_modifiers_to_cluster(cluster: "MossCluster") -> None:
        abundance = state.environment_modifiers.get("plant_regrowth", 1.0)
        growth = state.environment_modifiers.get("moss_growth_speed", 1.0)
        cluster.set_capacity_multiplier(abundance)
        cluster.set_growth_speed_modifier(growth)

    def _spawn_moss_cluster(
        world_pos: Tuple[float, float], *, notify: bool = True
    ) -> bool:
        cluster = create_cluster_from_brush(
            world,
            world_pos,
            int(tools_panel.brush_size),
            rng=editor_rng,
        )
        if cluster is None:
            if notify:
                notification_manager.add(
                    "Kan hier geen mos plaatsen; ruimte is geblokkeerd.",
                    settings.RED,
                )
            return False
        _apply_modifiers_to_cluster(cluster)
        plants.append(cluster)
        return True

    def _stamp_wall_segment(world_pos: Tuple[float, float]) -> None:
        size = max(8, int(tools_panel.brush_size))
        left = int(world_pos[0]) - size // 2
        top = int(world_pos[1]) - size // 2
        rect = pygame.Rect(left, top, size, size)
        rect = _clamp_rect(rect)
        world.barriers.append(Barrier(rect, (80, 80, 120), "muur"))

    def _paint_biome(world_pos: Tuple[float, float]) -> None:
        template = tools_panel.get_selected_biome()
        if template is None:
            return
        size = max(24, int(tools_panel.brush_size))
        left = int(world_pos[0]) - size // 2
        top = int(world_pos[1]) - size // 2
        rect = pygame.Rect(left, top, size, size)
        rect = _clamp_rect(rect)
        new_biome = replace(
            template,
            rect=rect,
            mask=None,
            mask_offset=(0, 0),
        )
        new_biome.update_weather(pygame.time.get_ticks())
        world.biomes.insert(0, new_biome)

    def _draw_barrier_preview(surface: pygame.Surface, rect: pygame.Rect) -> None:
        if not rect.colliderect(camera.viewport):
            return
        visible = rect.clip(camera.viewport)
        scale_x = surface.get_width() / camera.viewport.width
        scale_y = surface.get_height() / camera.viewport.height
        left = int((visible.left - camera.viewport.left) * scale_x)
        top = int((visible.top - camera.viewport.top) * scale_y)
        width = max(1, int(visible.width * scale_x))
        height = max(1, int(visible.height * scale_y))
        preview = pygame.Rect(left, top, width, height)
        shade = pygame.Surface((preview.width, preview.height), pygame.SRCALPHA)
        shade.fill((220, 140, 90, 60))
        surface.blit(shade, preview.topleft)
        pygame.draw.rect(surface, (220, 140, 90), preview, 2)

    def _draw_world(target: pygame.Surface) -> None:
        view = world_surface.subsurface(camera.viewport)
        pygame.transform.smoothscale(view, target.get_size(), target)

    def _begin_tool_action(position: Tuple[int, int]) -> None:
        nonlocal painting_tool, barrier_drag_start, barrier_preview_rect
        tool = tools_panel.selected_tool
        if tool == EditorTool.INSPECT:
            return
        world_pos = _screen_to_world(position)
        if tool == EditorTool.SPAWN_MOSS:
            _spawn_moss_cluster(world_pos)
        elif tool == EditorTool.PAINT_MOSS:
            painting_tool = EditorTool.PAINT_MOSS
            _spawn_moss_cluster(world_pos, notify=False)
        elif tool == EditorTool.PAINT_WALL:
            painting_tool = EditorTool.PAINT_WALL
            _stamp_wall_segment(world_pos)
        elif tool == EditorTool.PAINT_BIOME:
            painting_tool = EditorTool.PAINT_BIOME
            _paint_biome(world_pos)
        elif tool == EditorTool.DRAW_BARRIER:
            barrier_drag_start = world_pos
            barrier_preview_rect = _world_rect_from_points(world_pos, world_pos)

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
    editor_rng = random.Random()
    legacy_ui_visible = True
    painting_tool: Optional[EditorTool] = None
    barrier_drag_start: Optional[Tuple[float, float]] = None
    barrier_preview_rect: Optional[pygame.Rect] = None
    modular_test_report: Optional[Dict[str, float]] = None
    test_preview: Optional[PrototypeSwimPreview] = None
    ocean_showcase_active = False
    ocean_showcase_preview: Optional[PrototypeSwimPreview] = None

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
        modular_test_button = pygame.Rect(
            start_button.left,
            start_button.bottom + 80,
            start_button.width,
            start_button.height,
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
        legacy_toggle_rect = pygame.Rect(
            panel_rect.left - 150,
            max(16, panel_rect.top - 40),
            140,
            30,
        )
        if tools_panel.selected_tool != EditorTool.DRAW_BARRIER:
            barrier_preview_rect = None
            barrier_drag_start = None
        if (
            painting_tool is not None
            and tools_panel.selected_tool
            not in {EditorTool.PAINT_MOSS, EditorTool.PAINT_WALL, EditorTool.PAINT_BIOME}
        ):
            painting_tool = None

        live_simulation_active = not starting_screen and not ocean_showcase_active

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

            pygame.draw.rect(screen, settings.SEA, modular_test_button)
            pygame.draw.rect(screen, settings.BLACK, modular_test_button, 3)

            test_text = button_font.render("Test prototype", True, settings.BLACK)
            test_rect = test_text.get_rect(center=modular_test_button.center)
            screen.blit(test_text, test_rect)

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

            report_y = modular_test_button.bottom + 20
            report_title = info_font.render(
                "Modulaire creature testresultaat:", True, settings.BLACK
            )
            screen.blit(report_title, (50, report_y))
            report_lines: List[str]
            if modular_test_report is None:
                report_lines = [
                    "Nog niet uitgevoerd. Klik op 'Test prototype' voor een snelle check.",
                ]
            else:
                report_lines = [
                    f"Naam: {modular_test_report['name']}",
                    f"Modules: {int(modular_test_report['modules'])}",
                    f"Massa: {modular_test_report['mass']:.1f}",
                    f"Frontal area: {modular_test_report['frontal_area']:.1f}",
                    f"Drag-coëfficiënt: {modular_test_report['drag']:.2f}",
                    f"Gem. stuwkracht: {modular_test_report['avg_thrust']:.1f}",
                    f"Piek stuwkracht: {modular_test_report['peak_thrust']:.1f}",
                ]
            for idx, line in enumerate(report_lines):
                info_surface = info_font.render(line, True, settings.BLACK)
                screen.blit(info_surface, (50, report_y + 32 + idx * 28))

            preview_height = 220
            preview_width = max(260, panel_rect.left - 120)
            preview_top = report_y + 32 + len(report_lines) * 28 + 20
            preview_rect = pygame.Rect(50, preview_top, preview_width, preview_height)
            _draw_modular_preview(screen, preview_rect, test_preview, info_font, delta_time)

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
            notification_manager.update()
            if legacy_ui_visible:
                gameplay_panel.draw(screen)
                notification_manager.draw(screen, info_font)

        elif ocean_showcase_active:
            info_font = pygame.font.Font(None, 32)
            subtitle_font = pygame.font.Font(None, 26)
            _draw_ocean_showcase(screen, ocean_showcase_preview, info_font, delta_time)
            headline = info_font.render("Diepe oceaantest", True, settings.BLACK)
            screen.blit(headline, (40, 30))
            subtext = subtitle_font.render(
                "Het prototype zwemt vrij rond – druk op Reset om terug te keren.",
                True,
                settings.BLACK,
            )
            screen.blit(subtext, (40, 70))

            pygame.draw.rect(screen, settings.GREEN, reset_button)
            pygame.draw.rect(screen, settings.BLACK, reset_button, 2)
            reset_label = font2.render("Reset", True, settings.BLACK)
            screen.blit(reset_label, (reset_button.x + 32, reset_button.y + 6))
            notification_manager.update()
            notification_manager.draw(screen, subtitle_font)

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

                for carcass in list(carcasses):
                    carcass.update(world, delta_time)
                    if carcass.is_depleted():
                        carcasses.remove(carcass)
                        continue
                    carcass.draw(world_surface)

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
                stats_window.update_stats(stats)
                event_manager.schedule_default_events()
                event_manager.update(
                    pygame.time.get_ticks(),
                    stats,
                    player_controller,
                )
                environment.sync_food_abundance(state)
                environment.sync_moss_growth_speed(state)
                notification_manager.update()

                _draw_world(screen)
                if legacy_ui_visible:
                    world.draw_weather_overview(screen, font2)

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

                    notification_manager.draw(screen, font)
                    player_controller.draw_overlay(screen, font2)
                    event_manager.draw(screen, font2)

        if not starting_screen and not ocean_showcase_active:
            if paused:
                _draw_world(screen)
            inspector.draw_highlight(screen, camera)
            inspector.draw(screen)

        if legacy_ui_visible and not starting_screen and not ocean_showcase_active:
            gameplay_panel.draw(screen)
        if (
            not starting_screen
            and not ocean_showcase_active
            and barrier_preview_rect
            and tools_panel.selected_tool == EditorTool.DRAW_BARRIER
        ):
            _draw_barrier_preview(screen, barrier_preview_rect)
        tools_panel.draw(screen)
        stats_window.draw(screen)
        toggle_label = font2.render(
            "UI verbergen" if legacy_ui_visible else "UI tonen",
            True,
            settings.BLACK,
        )
        pygame.draw.rect(screen, (235, 235, 235), legacy_toggle_rect, border_radius=6)
        pygame.draw.rect(screen, (70, 70, 70), legacy_toggle_rect, 1, border_radius=6)
        screen.blit(
            toggle_label,
            (
                legacy_toggle_rect.centerx - toggle_label.get_width() // 2,
                legacy_toggle_rect.centery - toggle_label.get_height() // 2,
            ),
        )

        pygame.display.flip()

        # Event handling
        for event in pygame.event.get():
            if live_simulation_active and inspector.handle_event(event):
                continue
            if not ocean_showcase_active and tools_panel.handle_event(event):
                continue
            if stats_window.handle_event(event):
                continue
            if live_simulation_active and legacy_ui_visible and gameplay_panel.handle_event(event):
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
                    camera.set_window_size(screen.get_width(), screen.get_height())
                    panel_rect.x = screen.get_width() - panel_width - panel_margin
                    previous_tool = tools_panel.selected_tool
                    previous_brush = tools_panel.brush_size
                    tools_visible = tools_panel.visible
                    gameplay_panel = GameplaySettingsPanel(
                        panel_rect,
                        font2,
                        font3,
                        _build_slider_configs(),
                    )
                    tools_panel = ToolsPanel(
                        font2,
                        font3,
                        topleft=(24, settings.WINDOW_HEIGHT - 360),
                        available_biomes=world.biomes,
                    )
                    tools_panel.selected_tool = previous_tool
                    tools_panel.brush_size = previous_brush
                    tools_panel.visible = tools_visible
                elif event.key == pygame.K_p and live_simulation_active:
                    paused = not paused
                elif event.key == pygame.K_n and live_simulation_active:
                    x = random.randint(0, max(0, world.width - 1))
                    y = random.randint(0, max(0, world.height - 1))
                    generation = 1
                    dna_profile = random.choice(dna_profiles)
                    lifeform = Lifeform(state, x, y, dna_profile, generation)
                    if random.randint(0, 100) < 10:
                        lifeform.is_leader = True
                    lifeforms.append(lifeform)

                elif event.key == pygame.K_b and live_simulation_active:
                    show_debug = not show_debug
                    notification_context.show_debug = show_debug
                elif event.key == pygame.K_l and live_simulation_active:
                    show_leader = not show_leader
                elif event.key == pygame.K_s and live_simulation_active:
                    show_action = not show_action
                    notification_context.show_action = show_action
                elif event.key == pygame.K_v and live_simulation_active:
                    show_vision = not show_vision
                elif event.key == pygame.K_d and live_simulation_active:
                    show_dna_id = not show_dna_id
                elif event.key == pygame.K_m and live_simulation_active:
                    player_controller.toggle_management()
                elif (
                    live_simulation_active
                    and event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS)
                ):
                    mouse_pos = pygame.mouse.get_pos()
                    focus = camera.screen_to_world(mouse_pos)
                    camera.adjust_zoom(1, focus, mouse_pos)
                elif (
                    live_simulation_active
                    and event.key in (pygame.K_MINUS, pygame.K_KP_MINUS)
                ):
                    mouse_pos = pygame.mouse.get_pos()
                    focus = camera.screen_to_world(mouse_pos)
                    camera.adjust_zoom(-1, focus, mouse_pos)
                elif live_simulation_active and player_controller.management_mode:
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
                if live_simulation_active and event.button in (4, 5):
                    mouse_pos = getattr(event, "pos", pygame.mouse.get_pos())
                    focus = camera.screen_to_world(mouse_pos)
                    delta = 1 if event.button == 4 else -1
                    camera.adjust_zoom(delta, focus, mouse_pos)
                    continue
                if event.button == 1 and legacy_toggle_rect.collidepoint(event.pos):
                    legacy_ui_visible = not legacy_ui_visible
                    continue
                if starting_screen:
                    if start_button.collidepoint(event.pos):
                        state.world_type = "Abyssal Ocean"
                        world.set_world_type(state.world_type)
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
                        start_time = datetime.datetime.now()
                        notification_manager.add("Diepe oceaantest gestart", settings.SEA)
                        starting_screen = False
                        paused = False
                        ocean_showcase_active = True
                        ocean_showcase_preview = PrototypeSwimPreview(
                            build_fin_swimmer_prototype()
                        )
                        camera.reset()
                    elif modular_test_button.collidepoint(event.pos):
                        modular_test_report, test_preview = _run_modular_creature_test()
                        notification_manager.add(
                            "Prototype test uitgevoerd", settings.SEA
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
                elif ocean_showcase_active:
                    if event.button == 1 and reset_button.collidepoint(event.pos):
                        ocean_showcase_active = False
                        ocean_showcase_preview = None
                        starting_screen = True
                        paused = True
                        notification_manager.add(
                            "Terug naar het hoofdmenu", settings.BLUE
                        )
                else:
                    if (
                        event.button == 1
                        and legacy_ui_visible
                        and reset_button.collidepoint(event.pos)
                    ):
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
                        stats_window.clear()
                        notification_manager.add(
                            "Simulatie gereset",
                            settings.BLUE,
                        )
                        starting_screen = True
                        paused = True
                    elif (
                        event.button == 1
                        and legacy_ui_visible
                        and show_dna_button.collidepoint(event.pos)
                    ):
                        notification_manager.add("DNA-ID overlay gewisseld", settings.SEA)
                        show_dna_id = not show_dna_id
                    elif (
                        event.button == 1
                        and legacy_ui_visible
                        and show_dna_info_button.collidepoint(event.pos)
                    ):
                        show_dna_info = not show_dna_info
                    else:
                        if event.button == 1 and tools_panel.selected_tool != EditorTool.INSPECT:
                            _begin_tool_action(event.pos)
                            continue
                        selected_lifeform = _lifeform_at_screen_pos(event.pos)
                        if selected_lifeform is not None:
                            inspector.select(selected_lifeform)
                        else:
                            inspector.clear()
            elif event.type == pygame.MOUSEMOTION and live_simulation_active:
                if painting_tool == EditorTool.PAINT_MOSS and event.buttons[0]:
                    _spawn_moss_cluster(_screen_to_world(event.pos), notify=False)
                elif painting_tool == EditorTool.PAINT_WALL and event.buttons[0]:
                    _stamp_wall_segment(_screen_to_world(event.pos))
                elif painting_tool == EditorTool.PAINT_BIOME and event.buttons[0]:
                    _paint_biome(_screen_to_world(event.pos))
                if (
                    tools_panel.selected_tool == EditorTool.DRAW_BARRIER
                    and barrier_drag_start is not None
                    and event.buttons[0]
                ):
                    barrier_preview_rect = _world_rect_from_points(
                        barrier_drag_start,
                        _screen_to_world(event.pos),
                    )
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and live_simulation_active:
                painting_tool = None
                if (
                    barrier_drag_start is not None
                    and barrier_preview_rect is not None
                    and tools_panel.selected_tool == EditorTool.DRAW_BARRIER
                ):
                    if barrier_preview_rect.width > 6 and barrier_preview_rect.height > 6:
                        world.barriers.append(
                            Barrier(barrier_preview_rect.copy(), (80, 80, 120), "muur"),
                        )
                    barrier_drag_start = None
                    barrier_preview_rect = None
            elif event.type == pygame.MOUSEWHEEL and live_simulation_active:
                mouse_pos = pygame.mouse.get_pos()
                focus = camera.screen_to_world(mouse_pos)
                camera.adjust_zoom(event.y, focus, mouse_pos)

    pygame.quit()

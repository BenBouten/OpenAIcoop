"""Main pygame simulation loop for the evolution project."""

from __future__ import annotations

import datetime
import logging
import math
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import Callable, Deque, Dict, List, Optional, Tuple

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

from ..body.attachment import Joint, JointType
from ..config import settings
from ..config.settings import SimulationSettings
from ..entities import movement
from ..entities.lifeform import Lifeform
from ..rendering.camera import Camera
from ..creator import CreatureTemplate, spawn_template
from ..rendering.creature_creator_overlay import CreatureCreatorOverlay, PaletteEntry
from ..rendering.draw_lifeform import draw_lifeform, draw_lifeform_vision
from ..rendering.effects import EffectManager
from ..rendering.gameplay_panel import GameplaySettingsPanel, SliderConfig
from ..rendering.perf_hud import PerfHUD
from ..rendering.lifeform_inspector import LifeformInspector
from ..rendering.modular_palette import (
    BASE_MODULE_ALPHA,
    JOINT_COLORS,
    MODULE_COLORS,
    MODULE_RENDER_STYLES,
    clamp_channel,
    tint_color,
)
from ..rendering.tools_panel import EditorTool, ToolsPanel
from ..rendering.stats_window import StatsWindow
from ..rendering.timers import TimerAggregator
from ..physics.test_creatures import TestCreature, build_fin_swimmer_prototype
from ..systems import stats as stats_system
from ..systems import telemetry
from ..systems.events import EventManager
from ..systems.notifications import NotificationManager
from ..systems.player import PlayerController
from ..systems.spatial_hash import build_spatial_grid
from ..world.types import Barrier
from ..world.vegetation import create_cluster_from_brush
from ..world.world import World
from .world.chunks import ChunkManager
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

if settings.TELEMETRY_ENABLED:
    telemetry.enable_telemetry("all")
    logger.info("Telemetry enabled; writing JSONL samples to %s", settings.LOG_DIRECTORY / "telemetry")
else:
    logger.info("Telemetry disabled; set EVOLUTION_TELEMETRY=1 to capture movement/combat data")

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


LAYER_SUMMARIES: Dict[str, str] = {
    "Surface": "Golfslag, kelpwouden en zonnige caustics.",
    "Sunlit": "Driftzones met plankton en zachte zijstromen.",
    "Twilight": "Radioactieve vents en chemosynthese velden.",
    "Midnight": "Plotselinge stromingswissels testen vinnen en thrusters.",
    "Abyss": "2-bit donkerte met bioluminescente bakens.",
}

START_SCREEN_TIPS: Tuple[str, ...] = (
    "WASD of pijltjestoetsen bewegen de camera; Shift geeft boost.",
    "Muiswiel of +/- zoomt tussen lagen.",
    "M opent management, V toont zichtkegels, B toont debug info.",
)

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
    torso_color: Tuple[int, int, int] = field(init=False)

    def __post_init__(self) -> None:
        self.layout = self._layout_graph(self.creature.graph)
        self.torso_color = self._resolve_torso_color()

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
            joint = self._joint_for_connection(node)
            if joint:
                self._draw_joint_indicator(surface, start, direction, joint)

        for node_id, offset in self.layout.items():
            node = self.creature.graph.get_node(node_id)
            module = node.module
            center = positions[node_id]
            length = max(14, int(module.size[2] * 30))
            height = max(12, int(module.size[1] * 28))
            rect = pygame.Rect(0, 0, length, height)
            rect.center = (int(center.x), int(center.y))
            color, alpha = self._module_visuals(module.module_type)
            module_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
            ellipse_rect = pygame.Rect(0, 0, rect.width, rect.height)
            pygame.draw.ellipse(module_surface, (*color, alpha), ellipse_rect)
            pygame.draw.ellipse(
                module_surface,
                (15, 30, 45, max(alpha, 160)),
                ellipse_rect,
                2,
            )
            surface.blit(module_surface, rect)
            if module.module_type == "propulsion":
                flame = rect.copy()
                flame.width = max(6, rect.width // 3)
                flame.left = rect.left - flame.width + 4
                flame_surface = pygame.Surface(flame.size, pygame.SRCALPHA)
                pygame.draw.ellipse(
                    flame_surface,
                    (255, 200, 150, max(120, alpha - 20)),
                    pygame.Rect(0, 0, flame.width, flame.height),
                )
                surface.blit(flame_surface, flame)
            if module.module_type == "head":
                eye_center = (rect.centerx + rect.width // 4, rect.centery - rect.height // 4)
                pygame.draw.circle(surface, (15, 30, 60), eye_center, 4)
            self._draw_orientation_arrow(surface, node_id, center, positions)

    def _module_visuals(self, module_type: str) -> Tuple[Tuple[int, int, int], int]:
        style = MODULE_RENDER_STYLES.get(module_type, MODULE_RENDER_STYLES["default"])
        tint = style.get("tint", (1.0, 1.0, 1.0))
        tinted = tint_color(self.torso_color, tint)  # type: ignore[arg-type]
        alpha_offset = int(style.get("alpha_offset", 0))
        alpha = max(60, min(255, BASE_MODULE_ALPHA + alpha_offset))
        return tinted, alpha

    def _resolve_torso_color(self) -> Tuple[int, int, int]:
        raw_color = getattr(self.creature, "torso_color", None) or getattr(
            self.creature, "body_color", None
        )
        if raw_color is not None:
            return tuple(clamp_channel(channel) for channel in raw_color)
        base = MODULE_COLORS.get("core", (72, 130, 168))
        seed = abs(hash(self.creature.name))
        jitter = (
            ((seed >> 0) & 0xFF) - 128,
            ((seed >> 8) & 0xFF) - 128,
            ((seed >> 16) & 0xFF) - 128,
        )
        return tuple(
            clamp_channel(base[idx] + jitter[idx] // 6)
            for idx in range(3)
        )

    def _joint_for_connection(self, node) -> Optional[Joint]:
        if node.parent is None or not node.attachment_point:
            return None
        try:
            parent_node = self.creature.graph.get_node(node.parent)
            point = parent_node.module.get_attachment_point(node.attachment_point)
        except KeyError:
            return None
        return point.joint

    def _draw_joint_indicator(
        self, surface: pygame.Surface, position: Vector2, direction: Vector2, joint: Joint
    ) -> None:
        color = JOINT_COLORS.get(joint.joint_type, (220, 220, 220))
        center = (int(position.x), int(position.y))
        pygame.draw.circle(surface, color, center, 6, 2)
        base_angle = math.atan2(direction.y, direction.x) if direction.length_squared() > 1e-4 else 0.0
        if joint.joint_type == JointType.HINGE and joint.swing_limits:
            for limit in joint.swing_limits:
                total_angle = base_angle + math.radians(limit)
                endpoint = (
                    int(position.x + math.cos(total_angle) * 18),
                    int(position.y + math.sin(total_angle) * 18),
                )
                pygame.draw.line(surface, color, center, endpoint, 1)
        elif joint.joint_type == JointType.BALL:
            pygame.draw.circle(surface, color, center, 4)
        elif joint.joint_type == JointType.MUSCLE:
            pygame.draw.circle(surface, color, center, 3)

    def _orientation_vector(self, node_id: str, positions: Dict[str, Vector2]) -> Vector2:
        node = self.creature.graph.get_node(node_id)
        center = positions.get(node_id, Vector2())
        if node.parent and node.parent in positions:
            direction = center - positions[node.parent]
            if direction.length_squared() > 1e-4:
                return direction
        if node.children:
            accum = Vector2()
            count = 0
            for child_id in node.children:
                if child_id in positions:
                    accum += positions[child_id] - center
                    count += 1
            if count and accum.length_squared() > 1e-4:
                return accum / count
        return Vector2(1.0, 0.0)

    def _draw_orientation_arrow(
        self, surface: pygame.Surface, node_id: str, center: Vector2, positions: Dict[str, Vector2]
    ) -> None:
        direction = self._orientation_vector(node_id, positions)
        if direction.length_squared() <= 1e-4:
            return
        direction = direction.normalize()
        module = self.creature.graph.get_node(node_id).module
        arrow_length = max(18, int(module.size[2] * 32))
        start = Vector2(center.x, center.y)
        end = start + direction * arrow_length
        pygame.draw.line(surface, (250, 250, 255), (int(start.x), int(start.y)), (int(end.x), int(end.y)), 2)
        left = end - direction * 4 + direction.rotate(140) * 6
        right = end - direction * 4 + direction.rotate(-140) * 6
        pygame.draw.polygon(
            surface,
            (250, 250, 255),
            [
                (int(end.x), int(end.y)),
                (int(left.x), int(left.y)),
                (int(right.x), int(right.y)),
            ],
        )


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


# ---------------------------------------------------------------------------
# UI toggles
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
chunk_manager: ChunkManager

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

def run(sim_settings: Optional[SimulationSettings] | None = None) -> None:
    """Start de pygame-simulatie."""
    global world, camera, notification_manager, event_manager, player_controller
    global latest_stats, show_debug, show_leader, show_action, show_vision, show_dna_id, show_dna_info
    global start_time, chunk_manager

    # Interaction state placeholders
    painting_tool: Optional[EditorTool] = None
    barrier_preview_rect: Optional[pygame.Rect] = None
    barrier_drag_start: Optional[Tuple[float, float]] = None

    runtime = sim_settings or settings.current_settings()

    pygame.init()
    screen = pygame.display.set_mode(
        (runtime.WINDOW_WIDTH, runtime.WINDOW_HEIGHT),
    )
    pygame.display.set_caption("Evolution Sim")

    view_surface: Optional[pygame.Surface] = None

    font1_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus8-Regular.ttf"
    font2_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus-Bold.ttf"
    font = _load_font(font1_path, 12)
    font2 = _load_font(font1_path, 18)
    font3 = _load_font(font2_path, 22)

    panel_width = 260
    panel_margin = 16
    panel_rect = pygame.Rect(
        runtime.WINDOW_WIDTH - panel_width - panel_margin,
        20,
        panel_width,
        runtime.WINDOW_HEIGHT - 40,
    )

    top_bar_buttons: List[Dict[str, object]] = []
    top_bar_padding = 12

    def _register_top_button(key: str, label: str, toggle: Callable[[], None], *, width: int = 140) -> None:
        x_offset = runtime.WINDOW_WIDTH - top_bar_padding - width
        if top_bar_buttons:
            x_offset = top_bar_buttons[-1]["rect"].left - 12 - width
        rect = pygame.Rect(x_offset, top_bar_padding, width, 30)
        top_bar_buttons.append(
            {
                "key": key,
                "label": label,
                "rect": rect,
                "toggle": toggle,
                "active": False,
            }
        )

    def _set_button_state(key: str, active: bool) -> None:
        for entry in top_bar_buttons:
            if entry["key"] == key:
                entry["active"] = active
                break

    def _set_environment_modifier(key: str, value: float) -> None:
        environment_modifiers[key] = value
        environment.sync_food_abundance(state)
        environment.sync_moss_growth_speed(state)

    def _set_mutation_rate(value: float) -> None:
        settings.MUTATION_CHANCE = int(value)

    def _set_max_lifeforms(value: float) -> None:
        settings.MAX_LIFEFORMS = int(value)

    def _set_reproduction_cooldown(value: float) -> None:
        settings.REPRODUCING_COOLDOWN_VALUE = int(value)

    def _set_energy_recovery(value: float) -> None:
        settings.ENERGY_RECOVERY_PER_SECOND = int(value)

    def _set_age_rate(value: float) -> None:
        settings.AGE_RATE_PER_SECOND = value

    def _set_hunger_penalty(value: float) -> None:
        settings.HUNGER_HEALTH_PENALTY_PER_SECOND = value

    stats_window = StatsWindow(font2, font3)
    inspector = LifeformInspector(state, font2, font3)

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

    # Defer panel instantiation totdat de wereld is gecreëerd, zodat deze biomen kan lezen.
    tools_panel: ToolsPanel
    gameplay_panel: GameplaySettingsPanel
    gameplay_panel_visible = True

    def _toggle_stats() -> None:
        if stats_window.visible:
            stats_window.hide()
        else:
            stats_window.show()
            if latest_stats:
                stats_window.update_stats(latest_stats)

    def _toggle_gameplay() -> None:
        nonlocal gameplay_panel_visible
        gameplay_panel_visible = not gameplay_panel_visible

    def _toggle_tools() -> None:
        tools_panel.visible = not tools_panel.visible

    def _toggle_creator() -> None:
        creature_creator.toggle()

    def _inspector_info() -> None:
        if inspector.visible:
            inspector.clear()
        else:
            notification_manager.add(
                "Klik op een lifeform om details te zien",
                settings.BLUE,
                2000,
            )

    # Register the top bar once; inspector button serves as a hint rather than a toggle.
    for key, label, width, handler in (
        ("stats", "Stats", 110, _toggle_stats),
        ("gameplay", "Gameplay", 140, _toggle_gameplay),
        ("tools", "Tools", 110, _toggle_tools),
        ("creator", "Creator", 130, _toggle_creator),
        ("inspector", "Inspector", 130, _inspector_info),
    ):
        _register_top_button(key, label, handler, width=width)

    def _initialise_population() -> None:
        global latest_stats
        bootstrap.generate_dna_profiles(state, world)
        bootstrap.spawn_lifeforms(state, world)
        bootstrap.seed_vegetation(state, world)
        environment.sync_food_abundance(state)
        environment.sync_moss_growth_speed(state)
        latest_stats = None
        stats_window.clear()

    # Wereld & camera
    world = World(
        runtime.WORLD_WIDTH,
        runtime.WORLD_HEIGHT,
        world_type=state.world_type,
        environment_modifiers=environment_modifiers,
    )
    chunk_manager = ChunkManager()
    perf_hud = PerfHUD()
    render_timers = TimerAggregator(logger)
    camera = Camera(
        runtime.WINDOW_WIDTH,
        runtime.WINDOW_HEIGHT,
        runtime.WORLD_WIDTH,
        runtime.WORLD_HEIGHT,
    )
    camera.center_on(runtime.WORLD_WIDTH / 2, runtime.WORLD_HEIGHT / 2)
    logger.info(
        "Simulation run initialised with world size %sx%s and %s starting lifeforms",
        runtime.WORLD_WIDTH,
        runtime.WORLD_HEIGHT,
        runtime.N_LIFEFORMS,
    )

    notification_manager = notification_context.notification_manager
    event_manager = EventManager(notification_manager, environment_modifiers)
    player_controller = PlayerController(notification_manager, dna_profiles, lifeforms)
    effects_manager = EffectManager()
    effects_manager.set_font(font2)

    render_ms: float = 0.0
    last_entity_blit_warning = -120
    last_rebuild_warning = -120

    palette_entries = [
        PaletteEntry("core", "Core", "Hoofdtorso"),
        PaletteEntry("head", "Head", "Sensor hub"),
        PaletteEntry("fin", "Fin", "Zwemvin"),
        PaletteEntry("thruster", "Thruster", "Stuwkracht"),
        PaletteEntry("sensor", "Sensor", "Detectiemodule"),
    ]

    def _spawn_creature_from_template(template: CreatureTemplate) -> None:
        try:
            spawn_template(state, template, world)
            notification_manager.add(
                f"Template '{template.name}' gespawned in oceaan",
                settings.SEA,
            )
        except Exception as exc:
            notification_manager.add(f"Spawn mislukt: {exc}", settings.RED)

    bootstrap.reset_simulation(
        state,
        world,
        camera,
        event_manager,
        player_controller,
        notification_manager,
        effects_manager,
        on_spawn=_spawn_creature_from_template,
    )
    chunk_manager.build_static_chunks(world)

    def _ensure_view_surface(view_rect: pygame.Rect) -> pygame.Surface:
        nonlocal view_surface
        if view_surface is None or view_surface.get_size() != view_rect.size:
            view_surface = pygame.Surface(view_rect.size).convert()
        return view_surface

    def _render_world_view(render_lifeforms: List[Lifeform]) -> None:
        nonlocal render_ms, last_entity_blit_warning, last_rebuild_warning

        chunk_manager.begin_frame()
        render_start = time.perf_counter()

        viewport_raw = camera.view_rect()
        viewport = pygame.Rect(
            int(viewport_raw.x),
            int(viewport_raw.y),
            int(viewport_raw.width),
            int(viewport_raw.height),
        )
        view = _ensure_view_surface(viewport)
        view.fill(world.background_color)

        chunk_manager.ensure_chunks(viewport, margin=1)
        with render_timers.time("rebuild_chunks"):
            chunk_manager.rebuild_queued()
        chunk_manager.unload_far_chunks(viewport)

        with render_timers.time("get_visible_chunks"):
            visible_chunks = chunk_manager.get_visible_chunks(viewport)

        with render_timers.time("draw_chunks"):
            for chunk in visible_chunks:
                if chunk.surface is None:
                    continue
                dx = int(chunk.rect.x - viewport.x)
                dy = int(chunk.rect.y - viewport.y)
                view.blit(chunk.surface, (dx, dy))

        offset = (int(viewport.x), int(viewport.y))

        with render_timers.time("dynamic_layers"):
            world.draw_dynamic_layers(view, viewport, offset)

        with render_timers.time("entities_index"):
            chunk_manager.update_entity_index(
                plants=plants, carcasses=carcasses, lifeforms=render_lifeforms
            )

        culling_margin = chunk_manager.culling_margin
        visible_bounds = viewport.inflate(culling_margin, culling_margin)
        entities_by_type = chunk_manager.entities_in_rect(visible_bounds)
        entity_blits = 0

        with render_timers.time("draw_entities"):
            for plant in entities_by_type["plants"]:
                if plant.rect.colliderect(visible_bounds):
                    plant.draw(view, offset=offset)
                    entity_blits += 1

            for carcass in entities_by_type["carcasses"]:
                if carcass.rect.colliderect(visible_bounds):
                    carcass.draw(view, offset=offset)
                    entity_blits += 1

            bounds_cache = camera.render_bounds(padding=96) if camera is not None else None
            for lifeform in entities_by_type["lifeforms"]:
                if lifeform.health_now <= 0:
                    continue
                if not lifeform.rect.colliderect(visible_bounds):
                    continue
                draw_lifeform(
                    view,
                    lifeform,
                    settings,
                    camera=camera,
                    render_bounds=bounds_cache,
                    world_height=world.height,
                    offset=offset,
                )
                entity_blits += 1
                if show_vision:
                    draw_lifeform_vision(
                        view,
                        lifeform,
                        settings,
                        camera=camera,
                        render_bounds=bounds_cache,
                        offset=offset,
                    )

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
                    view.blit(
                        text,
                        (int(lifeform.x) - offset[0], int(lifeform.y - 30) - offset[1]),
                    )

                if show_dna_id:
                    text = font2.render(f"{lifeform.dna_id}", True, (0, 0, 0))
                    view.blit(
                        text,
                        (int(lifeform.x) - offset[0], int(lifeform.y - 10) - offset[1]),
                    )

                if show_leader and lifeform.is_leader:
                    text = font.render("L", True, (0, 0, 0))
                    view.blit(
                        text,
                        (int(lifeform.x) - offset[0], int(lifeform.y - 30) - offset[1]),
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
                    view.blit(
                        text,
                        (int(lifeform.x) - offset[0], int(lifeform.y - 20) - offset[1]),
                    )

        effects_manager.draw(view, offset=offset)

        scaled = pygame.transform.smoothscale(
            view, (camera.window_width, camera.window_height)
        )
        screen.blit(scaled, (0, 0))

        render_ms = (time.perf_counter() - render_start) * 1000.0

        metrics = {
            "fps": clock.get_fps(),
            "visible_chunks": len(visible_chunks),
            "chunk_size": chunk_manager.chunk_size,
            "culling_margin": culling_margin,
            "entity_blits": entity_blits,
            "chunk_rebuilds": chunk_manager.rebuilds_this_frame,
            "render_ms": render_ms,
            "streaming": chunk_manager.streaming_enabled,
            "rebuild_queue": chunk_manager.rebuild_queue_size,
        }

        if entity_blits > 1500 and chunk_manager.frame_index - last_entity_blit_warning > 60:
            notification_manager.add("Veel blits deze frame", settings.RED, 1500)
            last_entity_blit_warning = chunk_manager.frame_index
        if (
            chunk_manager.rebuilds_this_frame > 2
            and chunk_manager.frame_index - last_rebuild_warning > 60
        ):
            notification_manager.add("Chunk rebuild limiet overschreden", settings.RED, 1500)
            last_rebuild_warning = chunk_manager.frame_index

        perf_hud.update(metrics)
        perf_hud.draw(screen)

    creature_creator = CreatureCreatorOverlay(
        font2,
        font3,
        palette_entries,
        world,
        on_spawn=_spawn_creature_from_template,
    )

    gameplay_panel = GameplaySettingsPanel(
        panel_rect,
        font2,
        font3,
        _build_slider_configs(),
    )
    tools_panel = ToolsPanel(
        font2,
        font3,
        topleft=(24, runtime.WINDOW_HEIGHT - 360),
        available_biomes=world.biomes,
    )

    def _screen_to_world(position: Tuple[int, int]) -> Tuple[float, float]:
        return camera.screen_to_world(position)

    def _spawn_moss_cluster(world_pos: Tuple[float, float], *, notify: bool = True) -> None:
        brush_radius = max(8, tools_panel.brush_size // 2)
        create_cluster_from_brush(world, world_pos, brush_radius)
        if notify:
            notification_manager.add("Moscluster geplaatst", settings.SEA, 1500)

    def _stamp_wall_segment(world_pos: Tuple[float, float]) -> None:
        brush_radius = max(8, tools_panel.brush_size // 2)
        rect = pygame.Rect(0, 0, brush_radius * 2, brush_radius * 2)
        rect.center = (int(world_pos[0]), int(world_pos[1]))
        world.barriers.append(Barrier(rect, (90, 90, 150), "muur"))
        chunk_manager.mark_region_dirty(rect)

    def _paint_biome(world_pos: Tuple[float, float]) -> None:
        biome = tools_panel.get_selected_biome()
        if biome is None:
            notification_manager.add("Geen biome geselecteerd", settings.ORANGE, 1600)
            return
        brush_radius = max(16, tools_panel.brush_size)
        rect = pygame.Rect(0, 0, brush_radius * 2, brush_radius * 2)
        rect.center = (int(world_pos[0]), int(world_pos[1]))
        world.paint_biome(rect, biome)
        chunk_manager.mark_region_dirty(rect)

    def _begin_tool_action(position: Tuple[int, int]) -> None:
        nonlocal painting_tool, barrier_drag_start
        painting_tool = tools_panel.selected_tool
        world_pos = _screen_to_world(position)
        if painting_tool == EditorTool.SPAWN_MOSS:
            _spawn_moss_cluster(world_pos)
            painting_tool = None
        elif painting_tool == EditorTool.DRAW_BARRIER:
            barrier_drag_start = world_pos
        elif painting_tool == EditorTool.PAINT_MOSS:
            _spawn_moss_cluster(world_pos)
        elif painting_tool == EditorTool.PAINT_WALL:
            _stamp_wall_segment(world_pos)
        elif painting_tool == EditorTool.PAINT_BIOME:
            _paint_biome(world_pos)

    running = True
    starting_screen = True
    paused = True
    fullscreen = False
    show_creator_overlay = False

    modular_test_report: Optional[Dict[str, object]] = None
    test_preview: Optional[PrototypeSwimPreview] = None

    legacy_ui_visible = True

    stats_toggle_button = pygame.Rect(0, 0, 0, 0)
    inspector_toggle_button = pygame.Rect(0, 0, 0, 0)

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

        # Legacy UI toggle remains near the sidebar; other overlays are controlled by the top bar.

        for entry in top_bar_buttons:
            entry['active'] = False
        _set_button_state("stats", stats_window.visible and stats_window._stats is not None)
        _set_button_state("inspector", inspector.visible and inspector.selected is not None)
        _set_button_state("tools", tools_panel.visible)
        _set_button_state("gameplay", gameplay_panel_visible)
        _set_button_state("creator", creature_creator.active)

        if tools_panel.selected_tool != EditorTool.DRAW_BARRIER:
            barrier_preview_rect = None
            barrier_drag_start = None
        if (
            painting_tool is not None
            and tools_panel.selected_tool
            not in {EditorTool.PAINT_MOSS, EditorTool.PAINT_WALL, EditorTool.PAINT_BIOME}
        ):
            painting_tool = None

        live_simulation_active = not starting_screen

        if starting_screen:
            _draw_vertical_gradient(
                screen,
                screen.get_rect(),
                (40, 118, 180),
                (4, 12, 32),
            )
            title_font = pygame.font.Font(None, 56)
            info_font = pygame.font.Font(None, 30)
            small_font = pygame.font.Font(None, 24)
            button_font = pygame.font.Font(None, 34)

            title_surface = title_font.render("Alien Ocean – Evolutie POC", True, settings.WHITE)
            screen.blit(title_surface, (50, 40))
            subtitle = info_font.render(
                "Vijf oceaanlagen met Newtoniaanse physics en modulaire wezens.",
                True,
                settings.WHITE,
            )
            screen.blit(subtitle, (50, 100))

            for idx, tip in enumerate(START_SCREEN_TIPS):
                tip_surface = small_font.render(tip, True, settings.WHITE)
                screen.blit(tip_surface, (50, 150 + idx * 28))

            pygame.draw.rect(screen, settings.GREEN, start_button, border_radius=12)
            pygame.draw.rect(screen, settings.BLACK, start_button, 3, border_radius=12)
            start_text = button_font.render("Start oceaan", True, settings.BLACK)
            screen.blit(start_text, start_text.get_rect(center=start_button.center))

            pygame.draw.rect(screen, settings.SEA, modular_test_button, border_radius=12)
            pygame.draw.rect(screen, settings.BLACK, modular_test_button, 3, border_radius=12)
            test_text = button_font.render("Test prototype", True, settings.BLACK)
            screen.blit(test_text, test_text.get_rect(center=modular_test_button.center))

            layer_panel = pygame.Rect(screen.get_width() - 340, 60, 280, 360)
            panel_surface = pygame.Surface(layer_panel.size, pygame.SRCALPHA)
            panel_surface.fill((5, 12, 24, 210))
            screen.blit(panel_surface, layer_panel.topleft)
            panel_title = small_font.render("Oceaanlagen", True, settings.SEA)
            screen.blit(panel_title, (layer_panel.left + 16, layer_panel.top + 12))
            for idx, layer in enumerate(world.biomes):
                name = layer.name
                summary = LAYER_SUMMARIES.get(name, "Mysterieus ecosysteem")
                swatch = pygame.Rect(layer_panel.left + 16, layer_panel.top + 50 + idx * 58, 28, 28)
                pygame.draw.rect(screen, layer.color, swatch)
                pygame.draw.rect(screen, settings.WHITE, swatch, 1)
                name_surface = small_font.render(name, True, settings.WHITE)
                screen.blit(name_surface, (swatch.right + 10, swatch.top))
                summary_surface = small_font.render(summary, True, settings.WHITE)
                screen.blit(summary_surface, (swatch.right + 10, swatch.top + 22))
            vent_note = small_font.render(
                "Twilight/Midnight: rad vents → mutatie + neon pulsen.",
                True,
                settings.SEA,
            )
            screen.blit(vent_note, (layer_panel.left + 16, layer_panel.bottom - 34))

            report_y = modular_test_button.bottom + 20
            report_title = info_font.render("Prototype stats", True, settings.WHITE)
            screen.blit(report_title, (50, report_y))
            if modular_test_report is None:
                report_lines = [
                    "Nog niet uitgevoerd. Klik op 'Test prototype' voor een snelle check.",
                ]
            else:
                report_lines = [
                    f"Naam: {modular_test_report['name']}",
                    f"Modules: {int(modular_test_report['modules'])}",
                    f"Massa: modular_test_report['mass']:.1f",
                    f"Frontal area: {modular_test_report['frontal_area']:.1f}",
                    f"Drag-coëfficiënt: {modular_test_report['drag']:.2f}",
                    f"Gem. stuwkracht: {modular_test_report['avg_thrust']:.1f}",
                    f"Piek stuwkracht: {modular_test_report['peak_thrust']:.1f}",
                ]
            for idx, line in enumerate(report_lines):
                info_surface = small_font.render(line, True, settings.WHITE)
                screen.blit(info_surface, (50, report_y + 32 + idx * 26))

            preview_height = 220
            preview_width = max(260, panel_rect.left - 120)
            preview_top = report_y + 32 + len(report_lines) * 26 + 20
            preview_rect = pygame.Rect(50, preview_top, preview_width, preview_height)
            _draw_modular_preview(screen, preview_rect, test_preview, small_font, delta_time)

            notification_manager.update()
            notification_manager.draw(screen, small_font)

        else:
            keys = pygame.key.get_pressed()
            horizontal = (keys[pygame.K_d] - keys[pygame.K_a])
            vertical = (keys[pygame.K_s] - keys[pygame.K_w])
            if not player_controller.management_mode:
                horizontal += keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
                vertical += keys[pygame.K_DOWN] - keys[pygame.K_UP]
            boost = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            camera.move(horizontal, vertical, boost)

            lifeform_snapshot = list(lifeforms)
            render_lifeforms = list(lifeform_snapshot)

            if not paused:
                world.update(pygame.time.get_ticks())

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

                for carcass in list(carcasses):
                    carcass.update(world, delta_time)
                    if carcass.is_depleted():
                        carcasses.remove(carcass)

                lifeform_snapshot = list(lifeforms)
                average_maturity = (
                    sum(l.maturity for l in lifeform_snapshot) / len(lifeform_snapshot)
                    if lifeform_snapshot
                    else None
                )

                # Rebuild spatial grid for efficient proximity queries
                state.spatial_grid = build_spatial_grid(lifeform_snapshot, plants, cell_size=200.0)

                updated_lifeforms: List[Lifeform] = []
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

                    updated_lifeforms.append(lifeform)

                    if lifeform.reproduced_cooldown > 0:
                        lifeform.reproduced_cooldown -= 1

                render_lifeforms = updated_lifeforms

                effects_manager.update(delta_time)

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

            _render_world_view(render_lifeforms)
            render_timers.maybe_log()
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

        if not starting_screen:
            inspector.draw_highlight(screen, camera)
            if inspector.visible:
                inspector.draw(screen)
            if creature_creator.active:
                creature_creator.draw(screen)
                paused = True

            if legacy_ui_visible and gameplay_panel_visible:
                gameplay_panel.draw(screen)
            if barrier_preview_rect and tools_panel.selected_tool == EditorTool.DRAW_BARRIER:
                _draw_barrier_preview(screen, barrier_preview_rect)

            if tools_panel.visible:
                tools_panel.draw(screen)
            if stats_window.visible:
                stats_window.draw(screen)

            _draw_top_bar(screen, font2, top_bar_buttons, latest_stats)

        pygame.display.flip()

        # Event handling
        for event in pygame.event.get():
            if creature_creator.handle_event(event):
                continue
            if live_simulation_active and inspector.handle_event(event):
                continue
            if not starting_screen and tools_panel.handle_event(event):
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
                    creature_creator = CreatureCreatorOverlay(
                        font2,
                        font3,
                        palette_entries,
                        world,
                        on_spawn=_spawn_creature_from_template,
                    )
                elif event.key == pygame.K_F3:
                    perf_hud.toggle()
                elif event.key == pygame.K_F5:
                    chunk_manager.streaming_enabled = not chunk_manager.streaming_enabled
                elif event.key == pygame.K_LEFTBRACKET:
                    chunk_manager.set_chunk_size(chunk_manager.chunk_size - 64)
                elif event.key == pygame.K_RIGHTBRACKET:
                    chunk_manager.set_chunk_size(chunk_manager.chunk_size + 64)
                elif event.key == pygame.K_SEMICOLON:
                    chunk_manager.culling_margin = max(0, chunk_manager.culling_margin - 25)
                elif event.key == pygame.K_QUOTE:
                    chunk_manager.culling_margin = min(512, chunk_manager.culling_margin + 25)
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
                elif event.key == pygame.K_c and live_simulation_active:
                    creature_creator.toggle()
                    if not creature_creator.active:
                        creature_creator._selected_node = None
                        creature_creator._selected_module = None
                    paused = creature_creator.active or paused
                    continue
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
                if (
                    event.button == 1
                    and not starting_screen
                    and stats_toggle_button.collidepoint(event.pos)
                ):
                    # Toggle stats window
                    if stats_window._stats is not None:
                        stats_window.clear()
                    else:
                        if latest_stats:
                            stats_window.update_stats(latest_stats)
                    continue
                if (
                    event.button == 1
                    and not starting_screen
                    and inspector_toggle_button.collidepoint(event.pos)
                ):
                    # Toggle inspector - if no selection, notify user
                    if inspector.selected is not None:
                        inspector.clear()
                    else:
                        notification_manager.add(
                            "Klik op een lifeform om te inspecteren",
                            settings.BLUE,
                            2000,
                        )
                    continue
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
                            on_spawn=_spawn_creature_from_template,
                        )
                        chunk_manager.build_static_chunks(world)
                        _initialise_population()
                        inspector.clear()
                        start_time = datetime.datetime.now()
                        notification_manager.add("Alien Ocean simulatie gestart", settings.SEA)
                        starting_screen = False
                        paused = False
                        camera.reset()
                    elif modular_test_button.collidepoint(event.pos):
                        modular_test_report, test_preview = _run_modular_creature_test()
                        notification_manager.add(
                            "Prototype test uitgevoerd", settings.SEA
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
                            on_spawn=_spawn_creature_from_template,
                        )
                        chunk_manager.build_static_chunks(world)
                        _initialise_population()
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
                        chunk_manager.mark_region_dirty(barrier_preview_rect)
                    barrier_drag_start = None
                    barrier_preview_rect = None
            elif event.type == pygame.MOUSEWHEEL and live_simulation_active:
                mouse_pos = pygame.mouse.get_pos()
                focus = camera.screen_to_world(mouse_pos)
                camera.adjust_zoom(event.y, focus, mouse_pos)

    pygame.quit()
    if settings.TELEMETRY_ENABLED:
        telemetry.flush_all()
        logger.info("Telemetry flushed to %s", settings.LOG_DIRECTORY / "telemetry")

def _draw_top_bar(surface: pygame.Surface, font: pygame.font.Font, buttons: List[Dict[str, object]], stats: Optional[Dict[str, object]]) -> None:
    if not buttons:
        return
    background = pygame.Surface((surface.get_width(), 48), pygame.SRCALPHA)
    background.fill((5, 10, 30, 180))
    surface.blit(background, (0, 0))

    count_text = "Lifeforms: --"
    dna_text = "DNA profielen: --"
    if stats:
        count_text = f"Lifeforms: {int(stats.get('lifeform_count', 0))}"
        dna_total = stats.get('dna_count', {})
        dna_text = f"DNA profielen: {len(dna_total) if isinstance(dna_total, dict) else 0}"
    life_label = font.render(count_text, True, (245, 245, 245))
    dna_label = font.render(dna_text, True, (230, 230, 230))
    surface.blit(life_label, (16, 12))
    surface.blit(dna_label, (16, 24))

    for entry in buttons:
        rect: pygame.Rect = entry['rect']
        active = entry.get('active', False)
        color = (60, 130, 210) if active else (200, 200, 200)
        border = (20, 40, 80) if active else (80, 80, 80)
        pygame.draw.rect(surface, color, rect, border_radius=6)
        pygame.draw.rect(surface, border, rect, 1, border_radius=6)
        label_surface = font.render(str(entry['label']), True, (15, 20, 35) if active else (25, 25, 25))
        surface.blit(
            label_surface,
            (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2,
            ),
        )


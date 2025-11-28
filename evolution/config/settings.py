"""Configuration constants for the evolution simulation."""

from __future__ import annotations

import argparse
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import yaml

from .constants import DEFAULTS

_PATH_FIELDS = {"LOG_DIRECTORY"}
_STRING_FIELDS = {"DEBUG_LOG_FILE", "DEBUG_LOG_LEVEL"}
_BOOL_FIELDS = {"TELEMETRY_ENABLED", "USE_BODYGRAPH_SIZE"}
_FLOAT_FIELDS = {
    "BODY_PIXEL_SCALE",
    "MODULE_SPRITE_SCALE",
    "MODULE_SPRITE_MIN_PX",
    "MODULE_SPRITE_MIN_LENGTH",
    "MODULE_SPRITE_MIN_HEIGHT",
    "THRUST_SCALE_EXPONENT",
    "THRUST_BASE_MULTIPLIER",
    "DRAG_COEFFICIENT_MULTIPLIER",
    "REPRODUCTION_DISTANCE_MULTIPLIER",
    "DNA_CHANGE_THRESHOLD",
}

WORLD_WIDTH = DEFAULTS["WORLD_WIDTH"]
WORLD_HEIGHT = DEFAULTS["WORLD_HEIGHT"]
WINDOW_WIDTH = DEFAULTS["WINDOW_WIDTH"]
WINDOW_HEIGHT = DEFAULTS["WINDOW_HEIGHT"]

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (124, 252, 184)
RED = (255, 150, 150)
BLUE = (150, 255, 150)
SEA = (194, 252, 250)
BACKGROUND = WHITE

N_LIFEFORMS = 100
N_VEGETATION = 100
N_DNA_PROFILES = 10
MAX_LIFEFORMS = 150
STARTING_SPECIES_COUNT = 5
STARTER_BASE_FORM_LIMIT = 2
MUTATION_CHANCE = 5
MOSS_MUTATION_CHANCE = 0.2
MOSS_MUTATION_STRENGTH = 0.25
REPRODUCING_COOLDOWN_VALUE = 80
POPULATION_CAP_RETRY_COOLDOWN = 30

DNA_CHANGE_THRESHOLD = 0.1
COLOR_CHANGE_THRESHOLD = 0.1

GROUP_MIN_NEIGHBORS = 3
GROUP_MAX_RADIUS = 120
GROUP_COHESION_THRESHOLD = 0.35
GROUP_PERSISTENCE_FRAMES = 45
GROUP_MATURITY_RATIO = 0.6
BOID_ALIGNMENT_WEIGHT = 0.6
BOID_COHESION_WEIGHT = 0.45
BOID_SEPARATION_WEIGHT = 0.75
BOID_SEPARATION_DISTANCE = 48
BOID_PARTNER_WEIGHT = 0.55

JUVENILE_PARENT_COMFORT_RADIUS = 60
JUVENILE_PARENT_ATTRACTION_RADIUS = 180
JUVENILE_PARENT_ATTRACTION_WEIGHT = 1.2
JUVENILE_SIBLING_COMFORT_RADIUS = 50
JUVENILE_SIBLING_ATTRACTION_RADIUS = 140
JUVENILE_SIBLING_ATTRACTION_WEIGHT = 0.65
JUVENILE_SEPARATION_RADIUS = 24
JUVENILE_SEPARATION_WEIGHT = 0.6
JUVENILE_BEHAVIOUR_MAX_FORCE = 1.5

MAX_WIDTH = 10
MIN_WIDTH = 2
MAX_HEIGHT = 10
MIN_HEIGHT = 2
BODY_PIXEL_SCALE = float(os.getenv("EVOLUTION_BODY_PIXEL_SCALE", "10.0"))
USE_BODYGRAPH_SIZE = os.getenv("EVOLUTION_USE_BODYGRAPH_SIZE", "1") not in {"0", "false", "False"}
MODULE_SPRITE_SCALE = float(os.getenv("EVOLUTION_MODULE_SPRITE_SCALE", "0.22"))
MODULE_SPRITE_MIN_PX = float(os.getenv("EVOLUTION_MODULE_SPRITE_MIN_PX", "6.0"))
MODULE_SPRITE_MIN_LENGTH = float(os.getenv("EVOLUTION_MODULE_SPRITE_MIN_LENGTH", "4.0"))
MODULE_SPRITE_MIN_HEIGHT = float(os.getenv("EVOLUTION_MODULE_SPRITE_MIN_HEIGHT", "4.0"))
THRUST_SCALE_EXPONENT = float(os.getenv("EVOLUTION_THRUST_SCALE_EXPONENT", "0.5"))
THRUST_BASE_MULTIPLIER = float(os.getenv("EVOLUTION_THRUST_BASE_MULTIPLIER", "2.0"))
DRAG_COEFFICIENT_MULTIPLIER = float(os.getenv("EVOLUTION_DRAG_COEFFICIENT_MULTIPLIER", "0.15"))
MIN_MATURITY = 50
MAX_MATURITY = 150
VISION_MIN = 10
VISION_MAX = 300
DEGRADE_TIPPING = 3000

MEMORY_MAX_VISITED = 120
MEMORY_MAX_FOOD = 16
MEMORY_MAX_THREATS = 12
MEMORY_MAX_PARTNERS = 10
MEMORY_DECAY_MS = 45000
RECENT_VISIT_MEMORY_MS = 6000

HUNGER_SEEK_THRESHOLD = 250
HUNGER_RELAX_THRESHOLD = -100
HUNGER_SATIATED_THRESHOLD = 0
FEEDING_ACTIVITY_MEMORY_MS = 1800
HUNGER_MINIMUM = -150
HUNGER_CRITICAL_THRESHOLD = 520
ENERGY_REPRODUCTION_THRESHOLD = 0.68
PLANT_BITE_NUTRITION_TARGET = 18.0
PLANT_HUNGER_SATIATION_PER_NUTRITION = 2.4
REPRODUCTION_DISTANCE_MULTIPLIER = float(os.getenv("EVOLUTION_REPRODUCTION_DISTANCE_MULTIPLIER", "2.5"))

WANDER_JITTER_DEGREES = 28
WANDER_INTERVAL_MS = 700

STUCK_FRAMES_THRESHOLD = 18
ESCAPE_OVERRIDE_FRAMES = 24
ESCAPE_FORCE = 1.8
OBSTACLE_LOOKAHEAD_BASE = 40
OBSTACLE_LOOKAHEAD_FACTOR = 6.0
OBSTACLE_AVOID_FORCE = 1.6
BOUNDARY_REPULSION_MARGIN = 80
BOUNDARY_REPULSION_WEIGHT = 1.25

FPS = 30

AGE_RATE_PER_SECOND = 5.0
HUNGER_RATE_PER_SECOND = 3.5
ENERGY_RECOVERY_PER_SECOND = 18.0
WOUND_HEAL_PER_SECOND = 30.0
LONGEVITY_HEALTH_DECAY_PER_SECOND = 24.0
EXTREME_LONGEVITY_DECAY_PER_SECOND = 2400.0
HUNGER_HEALTH_PENALTY_PER_SECOND = 2.0
EXTREME_HUNGER_HEALTH_PENALTY_PER_SECOND = 20.0

CONFIG_ENV_VAR = "EVOLUTION_CONFIG_FILE"
DEFAULT_CONFIG_FILE = Path("configs/default.yaml")
LOG_DIRECTORY = Path(os.getenv("EVOLUTION_LOG_DIR", "logs"))
DEBUG_LOG_FILE = os.getenv("EVOLUTION_DEBUG_LOG", "simulation_debug.log")
DEBUG_LOG_LEVEL = os.getenv("EVOLUTION_DEBUG_LOG_LEVEL", "INFO")
TELEMETRY_ENABLED = os.getenv("EVOLUTION_TELEMETRY", "1") in {"1", "true", "True"}

CREATURE_TEMPLATE_DIR = Path(os.getenv("EVOLUTION_TEMPLATE_DIR", "creature_templates"))


@dataclass(frozen=True)
class SimulationSettings:
    WORLD_WIDTH: int = WORLD_WIDTH
    WORLD_HEIGHT: int = WORLD_HEIGHT
    WINDOW_WIDTH: int = WINDOW_WIDTH
    WINDOW_HEIGHT: int = WINDOW_HEIGHT
    N_LIFEFORMS: int = N_LIFEFORMS
    MAX_LIFEFORMS: int = MAX_LIFEFORMS
    MUTATION_CHANCE: int = MUTATION_CHANCE
    FPS: int = FPS
    LOG_DIRECTORY: Path = LOG_DIRECTORY
    DEBUG_LOG_FILE: str = DEBUG_LOG_FILE
    DEBUG_LOG_LEVEL: str = DEBUG_LOG_LEVEL
    TELEMETRY_ENABLED: bool = TELEMETRY_ENABLED
    BODY_PIXEL_SCALE: float = BODY_PIXEL_SCALE
    USE_BODYGRAPH_SIZE: bool = USE_BODYGRAPH_SIZE
    MODULE_SPRITE_SCALE: float = MODULE_SPRITE_SCALE
    MODULE_SPRITE_MIN_PX: float = MODULE_SPRITE_MIN_PX
    MODULE_SPRITE_MIN_LENGTH: float = MODULE_SPRITE_MIN_LENGTH
    MODULE_SPRITE_MIN_HEIGHT: float = MODULE_SPRITE_MIN_HEIGHT
    THRUST_SCALE_EXPONENT: float = THRUST_SCALE_EXPONENT
    THRUST_BASE_MULTIPLIER: float = THRUST_BASE_MULTIPLIER
    DRAG_COEFFICIENT_MULTIPLIER: float = DRAG_COEFFICIENT_MULTIPLIER
    MIN_MATURITY: int = MIN_MATURITY
    MAX_MATURITY: int = MAX_MATURITY
    VISION_MIN: int = VISION_MIN
    VISION_MAX: int = VISION_MAX
    REPRODUCTION_DISTANCE_MULTIPLIER: float = REPRODUCTION_DISTANCE_MULTIPLIER
    DNA_CHANGE_THRESHOLD: float = DNA_CHANGE_THRESHOLD

    def with_updates(self, overrides: Dict[str, Any]) -> "SimulationSettings":
        merged = asdict(self)
        merged.update(overrides)
        _validate_settings_dict(merged)
        return SimulationSettings(**merged)


_ACTIVE_SETTINGS = SimulationSettings()
_ENV_VARS: Dict[str, str] = {
    "WORLD_WIDTH": "EVOLUTION_WORLD_WIDTH",
    "WORLD_HEIGHT": "EVOLUTION_WORLD_HEIGHT",
    "WINDOW_WIDTH": "EVOLUTION_WINDOW_WIDTH",
    "WINDOW_HEIGHT": "EVOLUTION_WINDOW_HEIGHT",
    "N_LIFEFORMS": "EVOLUTION_N_LIFEFORMS",
    "MAX_LIFEFORMS": "EVOLUTION_MAX_LIFEFORMS",
    "MUTATION_CHANCE": "EVOLUTION_MUTATION_CHANCE",
    "FPS": "EVOLUTION_FPS",
    "TELEMETRY_ENABLED": "EVOLUTION_TELEMETRY",
    "BODY_PIXEL_SCALE": "EVOLUTION_BODY_PIXEL_SCALE",
    "USE_BODYGRAPH_SIZE": "EVOLUTION_USE_BODYGRAPH_SIZE",
    "MODULE_SPRITE_SCALE": "EVOLUTION_MODULE_SPRITE_SCALE",
    "MODULE_SPRITE_MIN_PX": "EVOLUTION_MODULE_SPRITE_MIN_PX",
    "MODULE_SPRITE_MIN_LENGTH": "EVOLUTION_MODULE_SPRITE_MIN_LENGTH",
    "MODULE_SPRITE_MIN_HEIGHT": "EVOLUTION_MODULE_SPRITE_MIN_HEIGHT",
    "THRUST_SCALE_EXPONENT": "EVOLUTION_THRUST_SCALE_EXPONENT",
    "THRUST_BASE_MULTIPLIER": "EVOLUTION_THRUST_BASE_MULTIPLIER",
    "DRAG_COEFFICIENT_MULTIPLIER": "EVOLUTION_DRAG_COEFFICIENT_MULTIPLIER",
    "REPRODUCTION_DISTANCE_MULTIPLIER": "EVOLUTION_REPRODUCTION_DISTANCE_MULTIPLIER",
}


def _coerce(value: str, field: str) -> Any:
    if field in {"LOG_DIRECTORY"}:
        return Path(value)
    if field in {"DEBUG_LOG_FILE", "DEBUG_LOG_LEVEL"}:
        return value
    if field == "TELEMETRY_ENABLED":
        return value in {"1", "true", "True"}
    if field == "USE_BODYGRAPH_SIZE":
        return value in {"1", "true", "True"}
    if field == "BODY_PIXEL_SCALE":
        return float(value)
    if field in {
        "MODULE_SPRITE_SCALE",
        "MODULE_SPRITE_MIN_PX",
        "MODULE_SPRITE_MIN_LENGTH",
        "MODULE_SPRITE_MIN_HEIGHT",
        "THRUST_SCALE_EXPONENT",
        "THRUST_BASE_MULTIPLIER",
        "DRAG_COEFFICIENT_MULTIPLIER",
        "REPRODUCTION_DISTANCE_MULTIPLIER",
        "DNA_CHANGE_THRESHOLD",
    }:
        return float(value)
    return int(value)


def _collect_env_overrides(env: Mapping[str, str]) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for field, env_name in _ENV_VARS.items():
        raw = env.get(env_name)
        if raw is not None:
            overrides[field] = _coerce(raw, field)
    return overrides


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value in {"1", "true", "True", "TRUE"}
    if isinstance(value, (int, float)):
        return bool(value)
    raise ValueError("Invalid boolean value in config")


def _normalize_numeric(value: Any, caster: type[float | int]) -> float | int:
    if isinstance(value, (int, float)):
        return caster(value)
    if isinstance(value, str):
        return caster(float(value) if caster is float else int(float(value)))
    raise ValueError("Invalid numeric value in config")


def _normalize_config_value(field: str, value: Any) -> Any:
    if field in _PATH_FIELDS:
        if isinstance(value, Path):
            return value
        if isinstance(value, str):
            return Path(value)
        raise ValueError(f"Field {field} must be a path or string")
    if field in _STRING_FIELDS:
        if isinstance(value, str):
            return value
        raise ValueError(f"Field {field} must be a string")
    if field in _BOOL_FIELDS:
        return _normalize_bool(value)
    if field in _FLOAT_FIELDS:
        return float(_normalize_numeric(value, float))
    return int(_normalize_numeric(value, int))


_NUMERIC_BOUNDS: Dict[str, tuple[float, float]] = {
    "WORLD_WIDTH": (500, 20000),
    "WORLD_HEIGHT": (500, 20000),
    "WINDOW_WIDTH": (200, 7680),
    "WINDOW_HEIGHT": (200, 4320),
    "N_LIFEFORMS": (1, 2000),
    "MAX_LIFEFORMS": (50, 4000),
    "MUTATION_CHANCE": (0, 100),
    "FPS": (1, 360),
    "BODY_PIXEL_SCALE": (1.0, 50.0),
    "MODULE_SPRITE_SCALE": (0.05, 2.0),
    "MODULE_SPRITE_MIN_PX": (1.0, 64.0),
    "MODULE_SPRITE_MIN_LENGTH": (1.0, 128.0),
    "MODULE_SPRITE_MIN_HEIGHT": (1.0, 128.0),
    "THRUST_SCALE_EXPONENT": (0.1, 2.0),
    "THRUST_BASE_MULTIPLIER": (0.1, 100.0),
    "DRAG_COEFFICIENT_MULTIPLIER": (0.01, 10.0),
    "DNA_CHANGE_THRESHOLD": (0.0, 1.0),
    "MIN_MATURITY": (1, 200),
    "MAX_MATURITY": (1, 400),
    "VISION_MIN": (1, 1000),
    "VISION_MAX": (1, 2000),
}

_CHOICE_FIELDS: Dict[str, set[str]] = {
    "DEBUG_LOG_LEVEL": {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
}


def _validate_settings_dict(values: Dict[str, Any]) -> None:
    for field, (lower, upper) in _NUMERIC_BOUNDS.items():
        current = values.get(field)
        if current is None:
            continue
        if not (lower <= current <= upper):
            raise ValueError(f"{field} must be between {lower} and {upper}, got {current}")
    for field, choices in _CHOICE_FIELDS.items():
        current = values.get(field)
        if current is None:
            continue
        if isinstance(current, str) and current.upper() in choices:
            values[field] = current.upper()
            continue
        raise ValueError(f"{field} must be one of {sorted(choices)} (got {current})")
    _validate_relationships(values)


def _validate_relationships(values: Mapping[str, Any]) -> None:
    world_width = values.get("WORLD_WIDTH")
    window_width = values.get("WINDOW_WIDTH")
    if world_width and window_width and window_width > world_width * 1.5:
        raise ValueError("WINDOW_WIDTH cannot exceed WORLD_WIDTH by more than 50%")
    world_height = values.get("WORLD_HEIGHT")
    window_height = values.get("WINDOW_HEIGHT")
    if world_height and window_height and window_height > world_height * 1.5:
        raise ValueError("WINDOW_HEIGHT cannot exceed WORLD_HEIGHT by more than 50%")
    n_lifeforms = values.get("N_LIFEFORMS")
    max_lifeforms = values.get("MAX_LIFEFORMS")
    if n_lifeforms and max_lifeforms and n_lifeforms > max_lifeforms:
        raise ValueError("N_LIFEFORMS cannot exceed MAX_LIFEFORMS")
    min_maturity = values.get("MIN_MATURITY")
    max_maturity = values.get("MAX_MATURITY")
    if min_maturity and max_maturity and min_maturity > max_maturity:
        raise ValueError("MIN_MATURITY cannot exceed MAX_MATURITY")
    vision_min = values.get("VISION_MIN")
    vision_max = values.get("VISION_MAX")
    if vision_min and vision_max and vision_min > vision_max:
        raise ValueError("VISION_MIN cannot exceed VISION_MAX")


def _load_config_overrides(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle) or {}
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid YAML in config file {path}") from error
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must define a mapping")
    valid_fields = set(SimulationSettings.__dataclass_fields__.keys())
    overrides: Dict[str, Any] = {}
    for raw_key, value in data.items():
        key = str(raw_key).upper()
        if key not in valid_fields:
            raise ValueError(f"Unknown config field: {raw_key}")
        overrides[key] = _normalize_config_value(key, value)
    return overrides


def _resolve_config_path(cli_value: str | None, env: Mapping[str, str]) -> Path | None:
    candidate_strings = [cli_value, env.get(CONFIG_ENV_VAR)]
    for candidate in candidate_strings:
        if not candidate:
            continue
        path = Path(candidate).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return path
    if DEFAULT_CONFIG_FILE.exists():
        return DEFAULT_CONFIG_FILE
    return None


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the evolution simulation with runtime overrides")
    parser.add_argument("--config", type=str, help="Path to a YAML config file with runtime settings")
    parser.add_argument("--world-width", type=int, help="Width of the simulation world")
    parser.add_argument("--world-height", type=int, help="Height of the simulation world")
    parser.add_argument("--window-width", type=int, help="Viewport width")
    parser.add_argument("--window-height", type=int, help="Viewport height")
    parser.add_argument("--n-lifeforms", type=int, help="Initial lifeform count")
    parser.add_argument("--max-lifeforms", type=int, help="Population cap")
    parser.add_argument("--mutation-chance", type=int, help="Mutation percentage")
    parser.add_argument("--fps", type=int, help="Target frames per second")
    parser.add_argument("--telemetry-enabled", type=int, help="Enable telemetry (1 or 0)")
    parser.add_argument("--body-pixel-scale", type=float, help="Pixels per simulated meter for body geometry")
    parser.add_argument("--module-sprite-scale", type=float, help="Multiplier for modular sprite size")
    parser.add_argument("--module-sprite-min-px", type=float, help="Minimum pixel span for module sprites")
    parser.add_argument("--module-sprite-min-length", type=float, help="Minimum pixel length for modules")
    parser.add_argument("--module-sprite-min-height", type=float, help="Minimum pixel height for modules")
    parser.add_argument("--thrust-scale-exponent", type=float, help="Exponent for scaling thrust with size")
    parser.add_argument("--thrust-base-multiplier", type=float, help="Base multiplier for thrust")
    parser.add_argument("--drag-coefficient-multiplier", type=float, help="Multiplier for drag coefficient")
    parser.add_argument("--reproduction-distance-multiplier", type=float, help="Multiplier for reproduction distance threshold")
    parser.add_argument("--dna-change-threshold", type=float, help="Threshold for creating new DNA ID")
    parser.add_argument(
        "--use-bodygraph-size",
        dest="use_bodygraph_size",
        action="store_true",
        help="Derive width/height from BodyGraph geometry",
    )
    parser.add_argument(
        "--no-bodygraph-size",
        dest="use_bodygraph_size",
        action="store_false",
        help="Disable BodyGraph-derived sizing and fall back to legacy sprites",
    )
    parser.set_defaults(use_bodygraph_size=None)
    return parser


def load_runtime_settings(args: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> SimulationSettings:
    env_mapping = env or os.environ
    parser = _build_arg_parser()
    parsed = parser.parse_args(args=args)
    overrides: Dict[str, Any] = {}
    config_path = _resolve_config_path(parsed.config, env_mapping)
    if config_path is not None:
        overrides.update(_load_config_overrides(config_path))
    overrides.update(_collect_env_overrides(env_mapping))
    cli_mapping = {
        "WORLD_WIDTH": parsed.world_width,
        "WORLD_HEIGHT": parsed.world_height,
        "WINDOW_WIDTH": parsed.window_width,
        "WINDOW_HEIGHT": parsed.window_height,
        "N_LIFEFORMS": parsed.n_lifeforms,
        "MAX_LIFEFORMS": parsed.max_lifeforms,
        "MUTATION_CHANCE": parsed.mutation_chance,
        "FPS": parsed.fps,
        "TELEMETRY_ENABLED": None if parsed.telemetry_enabled is None else bool(parsed.telemetry_enabled),
        "BODY_PIXEL_SCALE": parsed.body_pixel_scale,
        "USE_BODYGRAPH_SIZE": parsed.use_bodygraph_size,
        "MODULE_SPRITE_SCALE": parsed.module_sprite_scale,
        "MODULE_SPRITE_MIN_PX": parsed.module_sprite_min_px,
        "MODULE_SPRITE_MIN_LENGTH": parsed.module_sprite_min_length,
        "MODULE_SPRITE_MIN_HEIGHT": parsed.module_sprite_min_height,
        "THRUST_SCALE_EXPONENT": parsed.thrust_scale_exponent,
        "THRUST_BASE_MULTIPLIER": parsed.thrust_base_multiplier,
        "DRAG_COEFFICIENT_MULTIPLIER": parsed.drag_coefficient_multiplier,
        "REPRODUCTION_DISTANCE_MULTIPLIER": parsed.reproduction_distance_multiplier,
        "DNA_CHANGE_THRESHOLD": parsed.dna_change_threshold,
    }
    overrides.update({k: v for k, v in cli_mapping.items() if v is not None})
    return _ACTIVE_SETTINGS.with_updates(overrides)


def apply_runtime_settings(new_settings: SimulationSettings) -> SimulationSettings:
    global _ACTIVE_SETTINGS
    global WORLD_WIDTH, WORLD_HEIGHT, WINDOW_WIDTH, WINDOW_HEIGHT
    global N_LIFEFORMS, MAX_LIFEFORMS, MUTATION_CHANCE, FPS
    global LOG_DIRECTORY, DEBUG_LOG_FILE, DEBUG_LOG_LEVEL, TELEMETRY_ENABLED
    global BODY_PIXEL_SCALE, USE_BODYGRAPH_SIZE
    global MODULE_SPRITE_SCALE, MODULE_SPRITE_MIN_PX, MODULE_SPRITE_MIN_LENGTH, MODULE_SPRITE_MIN_HEIGHT
    global THRUST_SCALE_EXPONENT, THRUST_BASE_MULTIPLIER, DRAG_COEFFICIENT_MULTIPLIER
    global REPRODUCTION_DISTANCE_MULTIPLIER, DNA_CHANGE_THRESHOLD

    _ACTIVE_SETTINGS = new_settings
    WORLD_WIDTH = new_settings.WORLD_WIDTH
    WORLD_HEIGHT = new_settings.WORLD_HEIGHT
    WINDOW_WIDTH = new_settings.WINDOW_WIDTH
    WINDOW_HEIGHT = new_settings.WINDOW_HEIGHT
    N_LIFEFORMS = new_settings.N_LIFEFORMS
    MAX_LIFEFORMS = new_settings.MAX_LIFEFORMS
    MUTATION_CHANCE = new_settings.MUTATION_CHANCE
    FPS = new_settings.FPS
    LOG_DIRECTORY = new_settings.LOG_DIRECTORY
    DEBUG_LOG_FILE = new_settings.DEBUG_LOG_FILE
    DEBUG_LOG_LEVEL = new_settings.DEBUG_LOG_LEVEL
    TELEMETRY_ENABLED = new_settings.TELEMETRY_ENABLED
    BODY_PIXEL_SCALE = new_settings.BODY_PIXEL_SCALE
    USE_BODYGRAPH_SIZE = new_settings.USE_BODYGRAPH_SIZE
    MODULE_SPRITE_SCALE = new_settings.MODULE_SPRITE_SCALE
    MODULE_SPRITE_MIN_PX = new_settings.MODULE_SPRITE_MIN_PX
    MODULE_SPRITE_MIN_LENGTH = new_settings.MODULE_SPRITE_MIN_LENGTH
    MODULE_SPRITE_MIN_HEIGHT = new_settings.MODULE_SPRITE_MIN_HEIGHT
    THRUST_SCALE_EXPONENT = new_settings.THRUST_SCALE_EXPONENT
    THRUST_BASE_MULTIPLIER = new_settings.THRUST_BASE_MULTIPLIER
    DRAG_COEFFICIENT_MULTIPLIER = new_settings.DRAG_COEFFICIENT_MULTIPLIER
    REPRODUCTION_DISTANCE_MULTIPLIER = new_settings.REPRODUCTION_DISTANCE_MULTIPLIER
    DNA_CHANGE_THRESHOLD = new_settings.DNA_CHANGE_THRESHOLD
    return _ACTIVE_SETTINGS


def current_settings() -> SimulationSettings:
    return _ACTIVE_SETTINGS

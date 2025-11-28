"""Neural-behaviour controller for lifeforms.

This module replaces the hand-written steering logic with a small
feedforward neural controller whose parameters live in DNA. The
network reads local sensory features and emits thruster/actuator
commands that downstream physics code can consume.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Iterable, List, Optional, Tuple, TYPE_CHECKING

from pygame.math import Vector2

from .neural_controller import (
    INPUT_KEYS,
    OUTPUT_KEYS,
    NeuralController,
    expected_weight_count,
    initialize_brain_weights,
)
if TYPE_CHECKING:
    from .lifeform import Lifeform
    from ..simulation.state import SimulationState

logger = logging.getLogger("evolution.ai")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def update_brain(lifeform: "Lifeform", state: "SimulationState", dt: float) -> None:
    """Update the neural controller and translate outputs into actions.

    The controller only emits actuator commands: thrust intents, bite
    probability and luminescence tweaks. It does *not* set absolute
    positions or choose global targets; movement still flows through the
    physics layer.
    """

    controller = _ensure_controller(lifeform)
    inputs = _gather_inputs(lifeform, state)
    outputs = controller.forward(inputs)
    commands = _interpret_outputs(outputs)

    lifeform.neural_commands = commands
    lifeform.tail_thrust = commands["tail_thrust"]
    lifeform.left_fin_thrust = commands["left_fin_thrust"]
    lifeform.right_fin_thrust = commands["right_fin_thrust"]
    lifeform.vertical_thrust = commands["vertical_thrust"]
    lifeform.bite_intent = commands["bite_intent"]
    lifeform.lum_intensity = commands["lum_intensity"]
    lifeform.lum_pattern_mod = commands["lum_pattern_mod"]
    lifeform.neural_thrust_ratio = commands["thrust_ratio"]

    forward = _forward_vector(lifeform)
    turn_bias = commands["right_fin_thrust"] - commands["left_fin_thrust"]
    heading = forward.rotate(turn_bias * 45.0)
    thrust_scalar = max(0.05, abs(commands["tail_thrust"]) + abs(turn_bias) * 0.25)
    desired = heading * thrust_scalar
    desired.y += commands["vertical_thrust"]

    if desired.length_squared() == 0:
        desired = forward
    desired = desired.normalize()

    lifeform.wander_direction = desired
    lifeform.x_direction = desired.x
    lifeform.y_direction = desired.y
    lifeform.current_behavior_mode = "neural"


# ---------------------------------------------------------------------------
# Threat hooks
# ---------------------------------------------------------------------------

def register_threat(lifeform: "Lifeform", threat: "Lifeform", timestamp: int) -> None:
    """Force the lifeform to recognize a threat (e.g. after taking damage)."""

    if not threat or threat.health_now <= 0:
        return

    _remember(lifeform, "threats", (threat.x, threat.y), timestamp, weight=5.0)
    lifeform.last_attacker = threat


# ---------------------------------------------------------------------------
# Neural helpers
# ---------------------------------------------------------------------------

def _ensure_controller(lifeform: "Lifeform") -> NeuralController:
    controller: Optional[NeuralController] = getattr(lifeform, "_neural_controller", None)
    weights = getattr(lifeform, "brain_weights", None)
    if not weights or len(weights) != expected_weight_count():
        weights = initialize_brain_weights()
        lifeform.brain_weights = list(weights)
    if controller is None:
        controller = NeuralController(weights)
        lifeform._neural_controller = controller
    else:
        controller.weights = list(weights)
    return controller


def _gather_inputs(lifeform: "Lifeform", state: "SimulationState") -> List[float]:
    forward = _forward_vector(lifeform)
    food_forward, food_left, food_right = _sense_food_density(lifeform, state, forward)
    neighbor_density = _neighbor_density(lifeform, state)
    depth_norm = _depth_ratio(lifeform, state)
    energy_ratio = max(0.0, min(1.0, lifeform.energy_now / max(1.0, lifeform.energy)))
    vertical_velocity = max(
        -1.0, min(1.0, lifeform.velocity.y / max(1.0, lifeform.max_swim_speed))
    )
    speed = max(0.0, min(1.0, lifeform.velocity.length() / max(1.0, lifeform.max_swim_speed)))
    buoyancy_offsets = getattr(lifeform, "buoyancy_offsets", (0.0, 0.0))
    buoyancy_bias = max(-1.0, min(1.0, (buoyancy_offsets[0] - buoyancy_offsets[1]) * 0.25))

    inputs: List[float] = [
        food_forward,
        food_left,
        food_right,
        depth_norm,
        energy_ratio,
        neighbor_density,
        vertical_velocity,
        speed,
        random.uniform(-1.0, 1.0),
        buoyancy_bias,
    ]
    if len(inputs) != len(INPUT_KEYS):
        logger.debug("Unexpected input size: %s", len(inputs))
    return inputs


def _interpret_outputs(outputs: Iterable[float]) -> dict:
    values = list(outputs)
    if len(values) != len(OUTPUT_KEYS):
        logger.debug("Unexpected output size: %s", len(values))
    tail, left, right, vertical, bite, lum, pattern = (values + [0.0] * len(OUTPUT_KEYS))[: len(OUTPUT_KEYS)]
    thrust_ratio = max(0.0, min(1.5, abs(tail) + (abs(left) + abs(right)) * 0.35))
    return {
        "tail_thrust": max(-1.0, min(1.0, tail)),
        "left_fin_thrust": max(-1.0, min(1.0, left)),
        "right_fin_thrust": max(-1.0, min(1.0, right)),
        "vertical_thrust": max(-1.0, min(1.0, vertical)),
        "bite_intent": max(0.0, min(1.0, (bite + 1.0) * 0.5)),
        "lum_intensity": max(0.0, min(1.0, (lum + 1.0) * 0.5)),
        "lum_pattern_mod": max(-1.0, min(1.0, pattern)),
        "thrust_ratio": thrust_ratio,
    }


def _forward_vector(lifeform: "Lifeform") -> Vector2:
    forward = Vector2(lifeform.velocity)
    if forward.length_squared() < 1e-4:
        forward = Vector2(lifeform.x_direction, lifeform.y_direction)
    if forward.length_squared() == 0:
        forward = Vector2(1, 0)
    return forward.normalize()


def _depth_ratio(lifeform: "Lifeform", state: "SimulationState") -> float:
    world_height = getattr(state.world, "height", 1.0)
    return max(0.0, min(1.0, lifeform.y / max(1.0, world_height)))


def _sense_food_density(
    lifeform: "Lifeform", state: "SimulationState", forward: Vector2
) -> Tuple[float, float, float]:
    radius = max(12.0, lifeform.vision * 0.6)
    radius_sq = radius * radius
    pos = Vector2(lifeform.x, lifeform.y)
    def _score(target_pos: Vector2) -> Tuple[float, float, float]:
        delta = target_pos - pos
        dist_sq = delta.length_squared()
        if dist_sq > radius_sq or dist_sq == 0:
            return (0.0, 0.0, 0.0)
        aligned = delta.normalize()
        forward_score = max(0.0, forward.dot(aligned))
        lateral = forward.cross(aligned)
        base = forward_score * (1.0 / (1.0 + math.sqrt(dist_sq)))
        if lateral > 0.05:
            return (0.0, base, 0.0)
        if lateral < -0.05:
            return (0.0, 0.0, base)
        return (base, 0.0, 0.0)

    forward_density = 0.0
    left_density = 0.0
    right_density = 0.0

    targets: List[Tuple[float, float, float]] = []
    if lifeform.prefers_plants():
        for plant in getattr(state, "plants", []):
            target_pos = Vector2(plant.x + plant.width / 2, plant.y + plant.height / 2)
            targets.append(_score(target_pos))
    if lifeform.prefers_meat():
        for carcass in getattr(state, "carcasses", []):
            target_pos = Vector2(carcass.rect.centerx, carcass.rect.centery)
            targets.append(_score(target_pos))
        for other in getattr(state, "lifeforms", []):
            if other is lifeform or other.health_now <= 0:
                continue
            target_pos = Vector2(other.rect.centerx, other.rect.centery)
            targets.append(_score(target_pos))

    for fwd, left, right in targets:
        forward_density += fwd
        left_density += left
        right_density += right

    scale = 1.2
    return (
        max(0.0, min(1.0, forward_density * scale)),
        max(0.0, min(1.0, left_density * scale)),
        max(0.0, min(1.0, right_density * scale)),
    )


def _neighbor_density(lifeform: "Lifeform", state: "SimulationState") -> float:
    radius = 64.0
    radius_sq = radius * radius
    pos = Vector2(lifeform.x, lifeform.y)
    count = 0
    for other in getattr(state, "lifeforms", []):
        if other is lifeform or other.health_now <= 0:
            continue
        if (Vector2(other.rect.center) - pos).length_squared() <= radius_sq:
            count += 1
    return max(0.0, min(1.0, count / 12.0))


# ---------------------------------------------------------------------------
# Memory helpers (kept minimal for threat responses)
# ---------------------------------------------------------------------------

def _remember(
    lifeform: "Lifeform",
    kind: str,
    position: Tuple[float, float],
    timestamp: int,
    weight: float = 1.0,
) -> None:
    if kind not in lifeform.memory:
        return
    entry = {"pos": position, "time": timestamp, "weight": float(weight)}
    lifeform.memory[kind].append(entry)

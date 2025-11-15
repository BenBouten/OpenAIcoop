"""AI / behaviour helpers for lifeforms."""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING, List, Optional, Tuple

import pygame
from pygame.math import Vector2

from ..config import settings

if TYPE_CHECKING:
    from .lifeform import Lifeform
    from ..simulation.state import SimulationState

logger = logging.getLogger("evolution.ai")

CLOSE_FOOD_RADIUS = 6.0
MAX_FEEDING_FRAMES = 180  # ~3 seconden bij 60 FPS
COMFORT_HUNGER_LEVEL = settings.HUNGER_SATIATED_THRESHOLD

_WANDER_CIRCLE_DISTANCE = 1.6
_WANDER_CIRCLE_RADIUS = 1.2
_WANDER_DRIFT_SPEED = 0.45  # rad/s
_WANDER_DRIFT_STRENGTH = 0.35
_WANDER_MOVE_MIN_DURATION = 0.8
_WANDER_MOVE_MAX_DURATION = 2.6
_WANDER_PAUSE_MIN_DURATION = 0.35
_WANDER_PAUSE_MAX_DURATION = 1.8
_PAUSE_TURN_SPEED_BASE = 1.15  # rad/s
_PAUSE_SWAY_AMPLITUDE = 0.32  # rad
_PAUSE_SWAY_FREQUENCY = 1.4
_SEARCH_PROXIMITY_RADIUS = 8.0
_SPEED_DRIFT_INTERVAL = 2.4
_SPEED_DRIFT_LERP_RATE = 0.45

# ---------------------------------------------------------
# Public entry point
# ---------------------------------------------------------
def update_brain(lifeform: "Lifeform", state: "SimulationState", dt: float) -> None:
    """
    Centrale AI-update:
    - geheugen updaten
    - targets & observaties bijwerken
    - dreiging / voedsel / partner / groep / geheugen combineren
    - boundary repulsion + obstacle avoidance toepassen
    - escape override respecteren
    - uiteindelijke richting in lifeform.x_direction / y_direction zetten
    """

    now = pygame.time.get_ticks()
    _ensure_speed_tracking(lifeform)

    # ⬇️ NIEUW: als we in escape-modus zitten, NIETS anders doen
    if lifeform._escape_timer > 0 and lifeform._escape_vector.length_squared() > 0:
        _reset_speed_to_base(lifeform)
        escape_dir = lifeform._escape_vector.normalize()
        lifeform.x_direction = escape_dir.x
        lifeform.y_direction = escape_dir.y
        lifeform.wander_direction = escape_dir
        lifeform._escape_timer -= 1
        return  # ⬅️ heel belangrijk: alle normale gedrag wordt tijdelijk overgeslagen

    _cleanup_memory(lifeform, now)
    _remember(lifeform, "visited", (lifeform.x, lifeform.y), now, weight=1.0)

    # Target detection (zit nog in Lifeform.update_targets)
    lifeform.update_targets()
    _record_current_observations(lifeform, now)

    desired = Vector2()

    # 1) Dreiging eerst
    threat_vector = _compute_threat_vector(lifeform, now)
    if threat_vector.length_squared() > 0:
        desired += threat_vector
    else:
        # 2) Voedsel / partner
        pursuit_vector = _compute_pursuit_vector(lifeform, now)
        desired += pursuit_vector

        # 3) Geheugen als fallback
        if pursuit_vector.length_squared() == 0:
            desired += _memory_target_vector(lifeform, now)

    # 3b) Jongeren blijven dicht bij familie
    desired += _juvenile_family_vector(lifeform)

    # 4) Groepsgedrag en "laatste posities vermijden" en boundary repulsion
    desired += _group_behavior_vector(lifeform)
    desired += _avoid_recent_positions(lifeform, now)
    desired += _boundary_repulsion_vector(lifeform)

    # 5) Obstakel ontwijken
    avoidance = _obstacle_avoidance_vector(lifeform, desired)
    if avoidance.length_squared() > 0:
        desired += avoidance

    # 6) Escape override (stuck/boundary collision)
    if lifeform._escape_timer > 0 and lifeform._escape_vector.length_squared() > 0:
        desired += lifeform._escape_vector * settings.ESCAPE_FORCE
        lifeform._escape_timer -= 1
    else:
        lifeform._escape_timer = 0

    # 7) Fallback naar wander / huidige richting
    if desired.length_squared() == 0:
        desired = _wander_vector(lifeform, now, dt)
        lifeform.search = True
    else:
        lifeform.search = False

    if lifeform.search and _search_mode_active(lifeform):
        _apply_speed_drift(lifeform, dt)
    else:
        _reset_speed_to_base(lifeform)

    if desired.length_squared() == 0:
        desired = Vector2(lifeform.x_direction, lifeform.y_direction)
        if desired.length_squared() == 0:
            desired = Vector2(1, 0)

    desired = desired.normalize()

    current = Vector2(lifeform.x_direction, lifeform.y_direction)
    if current.length_squared() == 0:
        current = desired
    turn_rate = max(0.05, min(1.0, getattr(lifeform, "turn_rate", 0.5)))
    blended = current.lerp(desired, turn_rate)
    if blended.length_squared() == 0:
        blended = desired
    else:
        blended = blended.normalize()

    lifeform.wander_direction = blended
    lifeform.x_direction = blended.x
    lifeform.y_direction = blended.y


# ---------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------
def _cleanup_memory(lifeform: "Lifeform", timestamp: int) -> None:
    for key, buffer in lifeform.memory.items():
        while buffer and timestamp - buffer[0]["time"] > settings.MEMORY_DECAY_MS:
            buffer.popleft()


def _remember(
    lifeform: "Lifeform",
    kind: str,
    position: Tuple[float, float],
    timestamp: int,
    weight: float = 1.0,
    *,
    tag: Optional[str] = None,
) -> None:
    if kind not in lifeform.memory:
        return
    entry = {"pos": position, "time": timestamp, "weight": float(weight)}
    if tag:
        entry["tag"] = tag
    lifeform.memory[kind].append(entry)
    if tag and kind == "food" and logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "Lifeform %s onthoudt %s (%s) op %s met gewicht %.1f",
            lifeform.id,
            kind,
            tag,
            position,
            entry["weight"],
        )


def _recall(
    lifeform: "Lifeform",
    kind: str,
    timestamp: int,
    *,
    preferred_tag: Optional[str] = None,
) -> Optional[Tuple[float, float]]:
    buffer = lifeform.memory.get(kind)
    if not buffer:
        return None

    primary: List[Tuple[float, Tuple[float, float]]] = []
    secondary: List[Tuple[float, Tuple[float, float]]] = []
    for entry in buffer:
        age = timestamp - entry["time"]
        if age > settings.MEMORY_DECAY_MS:
            continue
        decay_factor = max(0.0, 1.0 - age / settings.MEMORY_DECAY_MS)
        weight = entry.get("weight", 1.0) * (0.5 + 0.5 * decay_factor)
        if kind == "food":
            urgency = max(0.0, lifeform.hunger - settings.HUNGER_SEEK_THRESHOLD)
            weight *= 1.0 + urgency / 120.0

        candidate = (weight, entry["pos"])
        tag = entry.get("tag")
        if preferred_tag is not None and tag != preferred_tag:
            secondary.append(candidate)
        else:
            primary.append(candidate)

    candidates = primary if primary else secondary

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _record_current_observations(lifeform: "Lifeform", timestamp: int) -> None:
    # Dreigingen
    if lifeform.closest_enemy and lifeform.closest_enemy.health_now > 0:
        _remember(
            lifeform,
            "threats",
            (lifeform.closest_enemy.x, lifeform.closest_enemy.y),
            timestamp,
            weight=1.0 + (1.0 - lifeform.risk_tolerance),
        )

    # Prooi (vlees)
    if (
        lifeform.closest_prey
        and lifeform.closest_prey.health_now > 0
        and lifeform.prefers_meat()
    ):
        weight = max(20.0, lifeform.attack_power_now + lifeform.hunger)
        _remember(
            lifeform,
            "food",
            (lifeform.closest_prey.x, lifeform.closest_prey.y),
            timestamp,
            weight=weight,
            tag="meat",
        )

    # Plantfood
    if (
        lifeform.closest_plant
        and lifeform.closest_plant.resource > 0
        and lifeform.prefers_plants()
    ):
        weight = lifeform.closest_plant.resource + max(0, lifeform.hunger - 50)
        _remember(
            lifeform,
            "food",
            _plant_center(lifeform),
            timestamp,
            weight=weight,
            tag="plant",
        )

    # Partnerlocaties
    if lifeform.closest_partner and lifeform.closest_partner.health_now > 0:
        partner_weight = 1.0 + lifeform.social_tendency
        _remember(
            lifeform,
            "partner",
            (lifeform.closest_partner.x, lifeform.closest_partner.y),
            timestamp,
            weight=partner_weight,
        )


# ---------------------------------------------------------
# Behaviour vectors
# ---------------------------------------------------------
def _compute_threat_vector(lifeform: "Lifeform", timestamp: int) -> Vector2:
    # Directe vijand
    if lifeform.closest_enemy and lifeform.closest_enemy.health_now > 0:
        direction, distance = lifeform._direction_to_lifeform(lifeform.closest_enemy)
        if distance > 0:
            strength = max(0.2, 1.0 - lifeform.risk_tolerance * 0.8)
            return direction * -strength

    # Onthouden dreigingen
    remembered_threat = _recall(lifeform, "threats", timestamp)
    if remembered_threat:
        direction, distance = lifeform._direction_to_point(remembered_threat)
        if distance > 0:
            strength = max(0.1, 1.0 - lifeform.risk_tolerance)
            return direction * -strength

    return Vector2()


def _compute_pursuit_vector(lifeform: "Lifeform", timestamp: int) -> Vector2:
    desired = Vector2()

    if lifeform.should_seek_food():
        food_vector = _immediate_food_vector(lifeform)
        if food_vector.length_squared() == 0:
            preferred_tag = None
            if lifeform.prefers_plants():
                preferred_tag = "plant"
            elif lifeform.prefers_meat():
                preferred_tag = "meat"
            remembered_food = _recall(
                lifeform, "food", timestamp, preferred_tag=preferred_tag
            )
            if remembered_food:
                direction, _ = lifeform._direction_to_point(remembered_food)
                desired += direction
        else:
            desired += food_vector
    else:
        desired += _opportunistic_food_vector(lifeform)

    if desired.length_squared() == 0 and lifeform.can_reproduce():
        if lifeform.closest_partner and lifeform.closest_partner.health_now > 0:
            direction, _ = lifeform._direction_to_lifeform(lifeform.closest_partner)
            desired += direction
        else:
            remembered_partner = _recall(lifeform, "partner", timestamp)
            if remembered_partner:
                direction, _ = lifeform._direction_to_point(remembered_partner)
                desired += direction

    return desired


def _juvenile_family_vector(lifeform: "Lifeform") -> Vector2:
    if lifeform.is_adult():
        return Vector2()

    desired = Vector2()
    parent_force = Vector2()
    has_active_parent = False

    comfort_parent = settings.JUVENILE_PARENT_COMFORT_RADIUS
    parent_radius = max(
        comfort_parent + 1,
        settings.JUVENILE_PARENT_ATTRACTION_RADIUS,
    )

    separation_radius = max(1.0, settings.JUVENILE_SEPARATION_RADIUS)

    for parent_id in getattr(lifeform, "parent_ids", tuple()):
        parent = next(
            (
                candidate
                for candidate in lifeform.state.lifeforms
                if candidate.id == parent_id and candidate.health_now > 0
            ),
            None,
        )
        if not parent:
            continue

        has_active_parent = True
        offset = Vector2(parent.x - lifeform.x, parent.y - lifeform.y)
        distance = offset.length()
        if distance == 0:
            continue

        direction = offset.normalize()
        if distance > comfort_parent:
            distance_factor = min(1.0, (distance - comfort_parent) / (parent_radius - comfort_parent))
            parent_force += (
                direction
                * distance_factor
                * settings.JUVENILE_PARENT_ATTRACTION_WEIGHT
            )
        elif distance < separation_radius:
            separation_factor = (separation_radius - distance) / separation_radius
            parent_force -= (
                direction
                * separation_factor
                * settings.JUVENILE_SEPARATION_WEIGHT
            )

    sibling_force = Vector2()
    family_signature = getattr(lifeform, "family_signature", tuple())
    comfort_sibling = settings.JUVENILE_SIBLING_COMFORT_RADIUS
    sibling_radius = max(
        comfort_sibling + 1,
        settings.JUVENILE_SIBLING_ATTRACTION_RADIUS,
    )

    if family_signature:
        for other in lifeform.state.lifeforms:
            if other is lifeform or other.health_now <= 0:
                continue
            if getattr(other, "family_signature", tuple()) != family_signature:
                continue
            if other.is_adult():
                continue

            offset = Vector2(other.x - lifeform.x, other.y - lifeform.y)
            distance = offset.length()
            if distance == 0:
                continue

            direction = offset.normalize()
            if distance > comfort_sibling:
                distance_factor = min(
                    1.0,
                    (distance - comfort_sibling) / (sibling_radius - comfort_sibling),
                )
                sibling_force += (
                    direction
                    * distance_factor
                    * settings.JUVENILE_SIBLING_ATTRACTION_WEIGHT
                )
            elif distance < separation_radius:
                separation_factor = (separation_radius - distance) / separation_radius
                sibling_force -= (
                    direction
                    * separation_factor
                    * settings.JUVENILE_SEPARATION_WEIGHT
                    * 0.5
                )

    desired += parent_force
    if has_active_parent:
        desired += sibling_force * 0.5
    else:
        desired += sibling_force

    if desired.length_squared() == 0:
        return desired

    max_force = max(0.1, settings.JUVENILE_BEHAVIOUR_MAX_FORCE)
    if desired.length() > max_force:
        desired = desired.normalize() * max_force

    return desired


def _memory_target_vector(lifeform: "Lifeform", timestamp: int) -> Vector2:
    target = None

    if lifeform.can_reproduce():
        target = _recall(lifeform, "partner", timestamp)

    if target is None and lifeform.should_seek_food():
        preferred_tag = None
        if lifeform.prefers_plants():
            preferred_tag = "plant"
        elif lifeform.prefers_meat():
            preferred_tag = "meat"
        target = _recall(lifeform, "food", timestamp, preferred_tag=preferred_tag)

    if target is None:
        return Vector2()

    direction, _ = lifeform._direction_to_point(target)
    return direction


def _group_behavior_vector(lifeform: "Lifeform") -> Vector2:
    if not lifeform.in_group or not lifeform.group_neighbors:
        return Vector2()

    alignment = Vector2()
    cohesion_positions = Vector2()
    separation = Vector2()
    active_neighbors = 0

    for neighbor in lifeform.group_neighbors:
        if neighbor.health_now <= 0:
            continue

        alignment += Vector2(neighbor.x_direction, neighbor.y_direction)
        cohesion_positions += Vector2(neighbor.x, neighbor.y)

        offset = Vector2(lifeform.x - neighbor.x, lifeform.y - neighbor.y)
        distance = offset.length()
        if 0 < distance < settings.BOID_SEPARATION_DISTANCE:
            separation += offset.normalize() * (1.0 - distance / settings.BOID_SEPARATION_DISTANCE)

        active_neighbors += 1

    if active_neighbors == 0:
        return Vector2()

    if alignment.length_squared() > 0:
        alignment = alignment.normalize()

    cohesion = (cohesion_positions / active_neighbors) - Vector2(lifeform.x, lifeform.y)
    if cohesion.length_squared() > 0:
        cohesion = cohesion.normalize()

    if separation.length_squared() > 0:
        separation = separation.normalize()

    influence = Vector2()
    influence += alignment * settings.BOID_ALIGNMENT_WEIGHT * lifeform.social_tendency
    influence += cohesion * settings.BOID_COHESION_WEIGHT * lifeform.social_tendency
    influence += separation * settings.BOID_SEPARATION_WEIGHT

    if lifeform.closest_follower and not lifeform.is_leader and lifeform.closest_follower.health_now > 0:
        follow_direction, _ = lifeform._direction_to_lifeform(lifeform.closest_follower)
        influence += follow_direction * 0.35 * lifeform.social_tendency

    return influence


def _avoid_recent_positions(lifeform: "Lifeform", timestamp: int) -> Vector2:
    buffer = lifeform.memory.get("visited")
    if not buffer:
        return Vector2()

    repulsion = Vector2()
    for entry in buffer:
        age = timestamp - entry["time"]
        if age > settings.RECENT_VISIT_MEMORY_MS:
            continue

        offset = Vector2(lifeform.x - entry["pos"][0], lifeform.y - entry["pos"][1])
        distance_sq = offset.length_squared()
        if distance_sq == 0:
            continue

        repulsion += offset / (distance_sq + 1)

    if repulsion.length_squared() == 0:
        return Vector2()

    return repulsion.normalize() * 0.4


def _ensure_wander_state(lifeform: "Lifeform") -> None:
    if not hasattr(lifeform, "_wander_phase"):
        lifeform._wander_phase = "move"
        lifeform._wander_phase_timer = 0.0
        lifeform._wander_phase_duration = _choose_wander_duration(lifeform, "move")
        lifeform._wander_pause_speed_factor = 1.0
        lifeform._voluntary_pause = False
    elif lifeform._wander_phase_duration <= 0:
        lifeform._wander_phase_duration = _choose_wander_duration(
            lifeform, lifeform._wander_phase
        )


def _update_wander_phase(lifeform: "Lifeform", dt: float) -> None:
    lifeform._wander_phase_timer += dt
    if lifeform._wander_phase_timer < lifeform._wander_phase_duration:
        return

    next_phase = "pause" if lifeform._wander_phase == "move" else "move"
    _set_wander_phase(lifeform, next_phase)


def _set_wander_phase(lifeform: "Lifeform", phase: str) -> None:
    lifeform._wander_phase = phase
    lifeform._wander_phase_timer = 0.0
    lifeform._wander_phase_duration = _choose_wander_duration(lifeform, phase)

    if phase == "pause":
        lifeform._wander_pause_speed_factor = _compute_pause_speed_factor(
            lifeform, initial=True
        )
        lifeform._voluntary_pause = True
    else:
        lifeform._wander_pause_speed_factor = 1.0
        lifeform._voluntary_pause = False
        _apply_move_reorientation(lifeform)


def _choose_wander_duration(lifeform: "Lifeform", phase: str) -> float:
    restlessness = float(getattr(lifeform, "restlessness", 0.5))
    restlessness = max(0.0, min(1.0, restlessness))
    calmness = 1.0 - restlessness

    if phase == "pause":
        base = random.uniform(_WANDER_PAUSE_MIN_DURATION, _WANDER_PAUSE_MAX_DURATION)
        modifier = 0.45 + calmness * 1.35
        return max(_WANDER_PAUSE_MIN_DURATION * 0.5, base * modifier)

    base = random.uniform(_WANDER_MOVE_MIN_DURATION, _WANDER_MOVE_MAX_DURATION)
    modifier = 0.65 + calmness * 0.95
    return max(_WANDER_MOVE_MIN_DURATION * 0.6, base * modifier)


def _compute_pause_speed_factor(lifeform: "Lifeform", *, initial: bool = False) -> float:
    restlessness = float(getattr(lifeform, "restlessness", 0.5))
    restlessness = max(0.0, min(1.0, restlessness))
    min_factor = max(0.05, 0.08 + restlessness * 0.24)
    max_factor = min(0.65, 0.32 + restlessness * 0.4)
    if initial:
        return max(0.05, max_factor)

    duration = max(0.001, getattr(lifeform, "_wander_phase_duration", 0.001))
    progress = min(1.0, getattr(lifeform, "_wander_phase_timer", 0.0) / duration)
    factor = max_factor * (1.0 - progress) + min_factor * progress
    return max(0.05, factor)


def _apply_move_reorientation(lifeform: "Lifeform") -> None:
    restlessness = float(getattr(lifeform, "restlessness", 0.5))
    restlessness = max(0.0, min(1.0, restlessness))
    spread = 35.0 + 70.0 * restlessness
    delta = math.radians(random.uniform(-spread, spread))

    base_vector = Vector2(lifeform.wander_direction)
    if base_vector.length_squared() == 0:
        base_vector = Vector2(math.cos(lifeform._wander_theta), math.sin(lifeform._wander_theta))
    if base_vector.length_squared() == 0:
        base_vector = Vector2(1, 0)

    heading = math.atan2(base_vector.y, base_vector.x)
    lifeform._wander_theta = (heading + delta) % math.tau


def _wander_vector(lifeform: "Lifeform", timestamp: int, dt: float) -> Vector2:
    if not hasattr(lifeform, "_wander_theta"):
        lifeform._wander_theta = random.uniform(0.0, math.tau)
    if not hasattr(lifeform, "_wander_drift_time"):
        lifeform._wander_drift_time = random.uniform(0.0, math.tau)

    _ensure_wander_state(lifeform)
    _update_wander_phase(lifeform, dt)

    restlessness = float(getattr(lifeform, "restlessness", 0.5))
    restlessness = max(0.0, min(1.0, restlessness))
    interval_scale = 1.2 - restlessness * 0.6

    if timestamp - lifeform.last_wander_update > settings.WANDER_INTERVAL_MS * interval_scale:
        jitter_range = settings.WANDER_JITTER_DEGREES * (0.55 + restlessness * 1.05)
        jitter = math.radians(random.uniform(-jitter_range, jitter_range))
        lifeform._wander_theta = (lifeform._wander_theta + jitter) % math.tau
        lifeform.last_wander_update = timestamp

    if lifeform._wander_phase == "pause":
        lifeform._wander_pause_speed_factor = _compute_pause_speed_factor(lifeform)
        lifeform._voluntary_pause = True
        turn_rate = _PAUSE_TURN_SPEED_BASE * (0.65 + restlessness * 1.1)
        lifeform._wander_theta = (lifeform._wander_theta + dt * turn_rate) % math.tau
        sway = math.sin(
            lifeform._wander_phase_timer * (_PAUSE_SWAY_FREQUENCY + restlessness * 0.6)
        ) * _PAUSE_SWAY_AMPLITUDE
        heading = lifeform._wander_theta + sway
        look = Vector2(math.cos(heading), math.sin(heading))
        if look.length_squared() == 0:
            look = Vector2(1, 0)
        return look.normalize()

    lifeform._wander_pause_speed_factor = 1.0
    lifeform._voluntary_pause = False

    forward = Vector2(lifeform.x_direction, lifeform.y_direction)
    if forward.length_squared() == 0:
        forward = Vector2(lifeform.wander_direction)
    if forward.length_squared() == 0:
        forward = Vector2(1, 0)
    forward = forward.normalize()

    circle_center = forward * _WANDER_CIRCLE_DISTANCE
    wander_offset = Vector2(
        math.cos(lifeform._wander_theta), math.sin(lifeform._wander_theta)
    ) * _WANDER_CIRCLE_RADIUS

    drift_speed = _WANDER_DRIFT_SPEED * (0.65 + restlessness * 1.05)
    drift_strength = _WANDER_DRIFT_STRENGTH * (0.6 + restlessness * 0.85)

    lifeform._wander_drift_time += dt * drift_speed
    drift = Vector2(
        math.cos(lifeform._wander_drift_time),
        math.sin(lifeform._wander_drift_time),
    ) * drift_strength

    wander = circle_center + wander_offset + drift
    if wander.length_squared() == 0:
        wander = forward

    return wander.normalize()


# ---------------------------------------------------------
# Search-mode helpers
# ---------------------------------------------------------
def _ensure_speed_tracking(lifeform: "Lifeform") -> None:
    pause_factor = getattr(lifeform, "_wander_pause_speed_factor", 1.0) or 1.0
    base_speed = float(lifeform.speed)
    if pause_factor > 0:
        base_speed /= pause_factor
    lifeform._dna_speed_reference = base_speed
    if not hasattr(lifeform, "_speed_drift_value"):
        lifeform._speed_drift_value = base_speed
        lifeform._speed_drift_target = base_speed
        lifeform._speed_drift_timer = 0.0


def _search_mode_active(lifeform: "Lifeform") -> bool:
    if not lifeform.search:
        return False

    if lifeform.closest_enemy and lifeform.closest_enemy.health_now > 0:
        if lifeform.distance_to(lifeform.closest_enemy) <= _SEARCH_PROXIMITY_RADIUS:
            return False

    if lifeform.closest_prey and lifeform.closest_prey.health_now > 0:
        if lifeform.distance_to(lifeform.closest_prey) <= _SEARCH_PROXIMITY_RADIUS:
            return False

    if lifeform.closest_partner and lifeform.closest_partner.health_now > 0:
        if lifeform.distance_to(lifeform.closest_partner) <= _SEARCH_PROXIMITY_RADIUS:
            return False

    if lifeform.closest_plant and getattr(lifeform.closest_plant, "resource", 0) > 0:
        center = _plant_center(lifeform)
        offset = Vector2(center[0] - lifeform.x, center[1] - lifeform.y)
        if offset.length() <= _SEARCH_PROXIMITY_RADIUS:
            return False

    return True


def _apply_speed_drift(lifeform: "Lifeform", dt: float) -> None:
    base = getattr(lifeform, "_dna_speed_reference", lifeform.speed)
    min_speed = base * 0.85
    max_speed = base * 1.15

    lifeform._speed_drift_timer += dt
    if lifeform._speed_drift_timer >= _SPEED_DRIFT_INTERVAL:
        lifeform._speed_drift_timer = 0.0
        lifeform._speed_drift_target = random.uniform(min_speed, max_speed)

    lifeform._speed_drift_target = max(
        min_speed, min(max_speed, lifeform._speed_drift_target)
    )

    lerp_factor = min(1.0, dt * _SPEED_DRIFT_LERP_RATE)
    lifeform._speed_drift_value += (
        lifeform._speed_drift_target - lifeform._speed_drift_value
    ) * lerp_factor

    drifted = max(min_speed, min(max_speed, lifeform._speed_drift_value))
    pause_factor = getattr(lifeform, "_wander_pause_speed_factor", 1.0) or 1.0
    adjusted = max(0.05, min(14.0, drifted * pause_factor))
    lifeform.speed = adjusted


def _reset_speed_to_base(lifeform: "Lifeform") -> None:
    base = getattr(lifeform, "_dna_speed_reference", lifeform.speed)
    pause_factor = getattr(lifeform, "_wander_pause_speed_factor", 1.0) or 1.0
    lifeform.speed = max(0.05, min(14.0, base * pause_factor))
    if hasattr(lifeform, "_speed_drift_value"):
        lifeform._speed_drift_value = base
        lifeform._speed_drift_target = base
        lifeform._speed_drift_timer = 0.0


# ---------------------------------------------------------
# Obstacle & boundary
# ---------------------------------------------------------
def _boundary_repulsion_vector(lifeform: "Lifeform") -> Vector2:
    margin = settings.BOUNDARY_REPULSION_MARGIN
    force = Vector2()
    world = lifeform.state.world

    left_distance = margin - lifeform.x
    if left_distance > 0:
        force.x += left_distance / margin

    right_distance = margin - (world.width - (lifeform.x + lifeform.width))
    if right_distance > 0:
        force.x -= right_distance / margin

    top_distance = margin - lifeform.y
    if top_distance > 0:
        force.y += top_distance / margin

    bottom_distance = margin - (world.height - (lifeform.y + lifeform.height))
    if bottom_distance > 0:
        force.y -= bottom_distance / margin

    if force.length_squared() == 0:
        return Vector2()

    return force.normalize() * settings.BOUNDARY_REPULSION_WEIGHT


def _obstacle_avoidance_vector(lifeform: "Lifeform", desired: Vector2) -> Vector2:
    """
    Berekent een stuurvector om obstakels te ontwijken.
    Let op: world-randen laten we over aan _boundary_repulsion_vector;
    hier kijken we vooral naar echte obstakels in world.is_blocked().
    """
    world = lifeform.state.world
    world_rect = pygame.Rect(0, 0, world.width, world.height)

    base = Vector2(desired)
    if base.length_squared() == 0:
        base = Vector2(lifeform.x_direction, lifeform.y_direction)
    if base.length_squared() == 0:
        base = Vector2(lifeform.wander_direction)
    if base.length_squared() == 0:
        return Vector2()

    forward = base.normalize()
    look_ahead = max(
        settings.OBSTACLE_LOOKAHEAD_BASE,
        lifeform.speed * settings.OBSTACLE_LOOKAHEAD_FACTOR,
    )

    inflated = lifeform.rect.inflate(8, 8)
    check_rect = inflated.copy()
    check_rect.x = int(lifeform.rect.x + forward.x * look_ahead)
    check_rect.y = int(lifeform.rect.y + forward.y * look_ahead)

    # Buiten de wereld? Laat boundary repulsion dat doen, hier geen obstakel
    if not world_rect.colliderect(check_rect):
        return Vector2()

    if not world.is_blocked(check_rect):
        return Vector2()

    logger.debug(
        "Lifeform %s predicted obstacle ahead; searching alternative path",
        lifeform.id,
    )

    angles = [
        20, -20,
        35, -35,
        50, -50,
        65, -65,
        90, -90,
        120, -120,
        150, -150,
        180,
    ]

    for angle in angles:
        candidate = forward.rotate(angle)
        if candidate.length_squared() == 0:
            continue

        candidate_rect = inflated.copy()
        candidate_rect.x = int(lifeform.rect.x + candidate.x * look_ahead)
        candidate_rect.y = int(lifeform.rect.y + candidate.y * look_ahead)

        if not world_rect.colliderect(candidate_rect):
            continue

        if not world.is_blocked(candidate_rect):
            return candidate.normalize() * settings.OBSTACLE_AVOID_FORCE

    # Geen goede uitweg → beetje terug duwen
    return (-forward) * (settings.OBSTACLE_AVOID_FORCE * 0.5)


def _immediate_food_vector(lifeform: "Lifeform") -> Vector2:
    candidates: List[Tuple[float, Vector2]] = []

    if (
        lifeform.closest_plant
        and lifeform.prefers_plants()
        and lifeform.closest_plant.resource > 0
        and lifeform.closest_enemy is None
    ):
        direction, distance = lifeform.direction_to_plant(lifeform.closest_plant)
        if distance > 0:
            weight = lifeform.closest_plant.resource + max(0, lifeform.hunger - 80)
            score = weight / (distance + 1)
            candidates.append((score, direction))

    if (
        lifeform.closest_prey
        and lifeform.prefers_meat()
        and lifeform.closest_prey.health_now > 0
        and lifeform.closest_enemy is None
    ):
        direction, distance = lifeform._direction_to_lifeform(lifeform.closest_prey)
        if distance > 0:
            weight = lifeform.attack_power_now + max(30, lifeform.hunger)
            score = weight / (distance + 1)
            candidates.append((score, direction))

    if not candidates:
        return Vector2()

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _opportunistic_food_vector(lifeform: "Lifeform") -> Vector2:
    if (
        lifeform.closest_prey
        and lifeform.prefers_meat()
        and lifeform.closest_enemy is None
    ):
        direction, distance = lifeform._direction_to_lifeform(lifeform.closest_prey)
        if distance > 0 and distance < max(12, lifeform.vision * 0.6):
            return direction

    if (
        lifeform.closest_plant
        and lifeform.prefers_plants()
        and lifeform.closest_enemy is None
    ):
        direction, distance = lifeform.direction_to_plant(lifeform.closest_plant)
        if distance > 0 and distance < max(10, lifeform.vision * 0.5):
            return direction

    return Vector2()

def _close_to_food_target(lifeform: "Lifeform") -> bool:
    """
    True = blijf even stilstaan bij voedsel (niet jitteren).
    False = AI mag weer normale steering doen.

    Ze gaan weer weg als:
    - er een vijand is
    - ze niet meer actief voedsel zoeken
    - de plant leeg is
    - ze buiten de radius lopen
    - ze lang genoeg hebben staan eten
    - hun honger laag genoeg is
    """
    # Dreiging? Altijd prioriteit boven eten.
    if lifeform.closest_enemy and lifeform.closest_enemy.health_now > 0:
        lifeform._feeding_frames = 0
        return False

    # Dit gedrag alleen voor planteters / omnivoren.
    if not lifeform.prefers_plants():
        lifeform._feeding_frames = 0
        return False

    # Als we niet eens in "ik moet eten"-modus zijn, niet blijven hangen.
    if not lifeform.should_seek_food():
        lifeform._feeding_frames = 0
        return False

    plant = lifeform.closest_plant
    if plant is None or plant.resource <= 0:
        lifeform._feeding_frames = 0
        return False

    distance = lifeform.distance_to_plant(plant)

    # Buiten de “eet cirkel”? Dan gewoon normale navigatie.
    if distance > CLOSE_FOOD_RADIUS:
        lifeform._feeding_frames = 0
        return False

    # Binnen eet-radius, actief op zoek naar eten, plant heeft nog resource:
    lifeform._feeding_frames += 1

    # 1) Hij is alweer behoorlijk "comfortabel" → weg bij de plant
    if lifeform.hunger < COMFORT_HUNGER_LEVEL:
        lifeform._feeding_frames = 0
        return False

    # 2) Te lang blijven hangen? Toch weer doorlopen:
    if lifeform._feeding_frames > MAX_FEEDING_FRAMES:
        lifeform._feeding_frames = 0
        return False

    # Anders: blijf hier even staan en eet.
    return True



def _plant_center(lifeform: "Lifeform") -> Tuple[float, float]:
    plant = lifeform.closest_plant
    if plant is None:
        return (float(lifeform.rect.centerx), float(lifeform.rect.centery))
    return lifeform.plant_contact_point(plant)

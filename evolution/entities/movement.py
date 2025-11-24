"""Generic movement & collision handling for Lifeforms.

Deze module:
- roept het AI-brein (ai.update_brain) aan om x/y richting te bepalen
- berekent verplaatsing op basis van richting & speed
- lost collisions & boundaries op via state.world.resolve_entity_movement(...)
- houdt bij of een lifeform 'vastzit' of langs de rand schuurt
- triggert escape manoeuvres (via Lifeform._trigger_escape_manoeuvre)
 - roept combat.resolve_close_interactions aan voor gevechten/eten/paren

In latere fases kun je combat naar een aparte module verplaatsen.
"""

from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING

import pygame
from pygame.math import Vector2

from ..config import settings
from ..physics.physics_body import PhysicsBody
from ..systems import telemetry

from . import ai, combat  # Gebruik aparte modules voor gedrag en interacties

logger = logging.getLogger("evolution.movement")

_MAX_THRUST_BEHAVIOUR_SPEED = 8.0
_MAX_FREQUENCY_BEHAVIOUR_SPEED = 14.0


def _ensure_search_vector(lifeform: "Lifeform") -> Vector2:
    vector = getattr(lifeform, "_search_vector", None)
    timer = getattr(lifeform, "_search_vector_timer", 0)
    if not vector or timer <= 0:
        angle = random.uniform(-math.pi, math.pi)
        vector = Vector2(math.cos(angle), math.sin(angle)) or Vector2(1.0, 0.0)
        vector = vector.normalize()
        lifeform._search_vector = vector
        lifeform._search_vector_timer = random.randint(45, 140)
    else:
        lifeform._search_vector_timer = timer - 1
    return lifeform._search_vector


def _apply_environment_bias(
    lifeform: "Lifeform",
    desired: Vector2,
    state: "SimulationState",
) -> Vector2:
    world = getattr(state, "world", None)
    if world is None:
        return desired

    vertical_adjust = 0.0
    depth = float(lifeform.y)
    world_height = float(getattr(world, "height", 0.0))
    rel_buoyancy = float(getattr(lifeform, "relative_buoyancy", 0.0))

    if rel_buoyancy > 0.08:
        vertical_adjust += 0.35
    elif rel_buoyancy < -0.08:
        vertical_adjust -= 0.35

    hunger = float(getattr(lifeform, "hunger", 0.0))
    if hunger > settings.HUNGER_SEEK_THRESHOLD and not (
        lifeform.closest_plant or lifeform.closest_prey
    ):
        vertical_adjust += 0.25
    elif hunger < settings.HUNGER_RELAX_THRESHOLD:
        vertical_adjust -= 0.15

    margin = 150.0
    if depth < margin:
        vertical_adjust += 0.2
    elif depth > world_height - lifeform.height - margin:
        vertical_adjust -= 0.2

    behavior = getattr(lifeform, "current_behavior_mode", "idle")
    if behavior == "flee":
        vertical_adjust -= 0.2
    elif behavior == "hunt":
        vertical_adjust += 0.2

    if vertical_adjust:
        adjusted = Vector2(desired.x, desired.y + vertical_adjust)
        if adjusted.length_squared() > 0:
            desired = adjusted.normalize()

    return desired


def _behavioral_thrust_ratio(lifeform: "Lifeform") -> float:
    """Return how aggressively a lifeform wants to swim (0-1.4)."""
    mode = getattr(lifeform, "current_behavior_mode", "idle")
    hunger = float(getattr(lifeform, "hunger", 0.0))
    restlessness = max(0.0, min(1.0, getattr(lifeform, "restlessness", 0.5)))

    base = 0.3
    if mode == "flee":
        base = 1.35
    elif mode == "hunt":
        base = 1.05
    elif mode == "mate":
        base = 0.9
    elif mode == "search":
        base = 0.78
    elif mode == "flock":
        base = 0.65
    elif mode == "interact":
        base = 0.45

    if lifeform.should_seek_food():
        hunger_boost = max(0.0, hunger - settings.HUNGER_SATIATED_THRESHOLD) / 320.0
        base *= 1.0 + min(0.32, hunger_boost)

    base *= 1.0 + restlessness * 0.12
    return min(1.4, base)


def _behavioral_frequency_ratio(lifeform: "Lifeform") -> float:
    mode = getattr(lifeform, "current_behavior_mode", "idle")
    hunger = float(getattr(lifeform, "hunger", 0.0))

    base = 0.2
    if mode == "flee":
        base = 1.15
    elif mode == "hunt":
        base = 0.9
    elif mode == "mate":
        base = 0.72
    elif mode == "search":
        base = 0.62
    elif mode == "flock":
        base = 0.52
    elif mode == "interact":
        base = 0.32

    if lifeform.should_seek_food():
        base += min(0.2, max(0.0, hunger - settings.HUNGER_SATIATED_THRESHOLD) / 450.0)

    return min(1.4, base)


def _target_swim_speed(lifeform: "Lifeform", thrust_ratio: float) -> float:
    max_swim_speed = max(10.0, float(getattr(lifeform, "max_swim_speed", 80.0)))
    adrenaline_boost = 1.0 + getattr(lifeform, "adrenaline_factor", 0.0) * 0.4
    desired = max_swim_speed * thrust_ratio * adrenaline_boost
    return min(max_swim_speed * 1.2, desired)


def _compute_thrust_effort(
    lifeform: "Lifeform",
    current_speed: float,
    thrust_ratio: float,
) -> float:
    target_speed = _target_swim_speed(lifeform, thrust_ratio)
    speed_error = target_speed - current_speed
    response_band = max(4.0, float(getattr(lifeform, "max_swim_speed", 80.0)) * 0.35)
    correction = speed_error / response_band
    propulsion_eff = float(getattr(lifeform, "propulsion_efficiency", 1.0))
    base_push = thrust_ratio * 0.2 * propulsion_eff
    effort = correction * 0.7 + base_push
    if speed_error < 0:
        effort *= 0.65
    else:
        effort += thrust_ratio * 0.15 * propulsion_eff
    return effort


def _compose_steering_thrust(
    lifeform: "Lifeform",
    physics_body: PhysicsBody,
    desired: Vector2,
    propulsion_acceleration: float,
) -> Vector2:
    """Blend thrust across control surfaces to allow asymmetric steering."""

    surfaces = getattr(physics_body, "steering_surfaces", ())
    if not surfaces:
        return desired * propulsion_acceleration

    facing = desired
    if lifeform.velocity.length_squared() > 0.2:
        facing = lifeform.velocity.normalize()

    # Signed turn demand: positive means rotate left, negative rotate right
    steering_error = facing.cross(desired)
    bias = max(-1.0, min(1.0, steering_error * 2.2))
    vectoring_limit = max(0.0, float(getattr(physics_body, "vectoring_limit", 0.0)))

    thrust_vector = Vector2()
    total_weight = 0.0
    for surface in surfaces:
        leverage = max(0.1, float(getattr(surface, "leverage", 0.0)))
        side = int(getattr(surface, "side", 0))
        base_power = float(getattr(surface, "thrust", 0.0))
        lift_power = float(getattr(surface, "lift", 0.0))
        if lift_power > 0.0:
            base_power += lift_power * max(0.8, getattr(physics_body, "lift_per_fin", 0.0))
        if base_power <= 0.0:
            base_power = physics_body.max_thrust * 0.08

        oscillation = 0.85 + 0.25 * math.sin(lifeform.thrust_phase + surface.phase_offset)
        side_gain = 1.0 + bias * leverage * 0.55 * side
        weight = max(0.05, base_power * side_gain * oscillation)
        total_weight += weight

        vectoring = bias * side * vectoring_limit
        directed = desired.rotate(vectoring)
        thrust_vector += directed * weight

    if thrust_vector.length_squared() == 0 or total_weight <= 0.0:
        return desired * propulsion_acceleration

    averaged = thrust_vector / total_weight
    if averaged.length_squared() == 0:
        return desired * propulsion_acceleration

    return averaged.normalize() * propulsion_acceleration


def _blend_desired_with_velocity(lifeform: "Lifeform", desired: Vector2) -> Vector2:
    """Blend steering with current velocity to avoid abrupt turns."""
    current_vel = lifeform.velocity
    if desired.length_squared() == 0:
        return desired
    if current_vel.length_squared() < 0.25:
        return desired

    current_dir = current_vel.normalize()
    fin_count = float(getattr(lifeform, "fin_count", 0.0))
    control_authority = min(0.95, 0.2 + fin_count * 0.05)
    if getattr(lifeform, "adrenaline_factor", 0.0) > 0.4:
        control_authority = min(0.98, control_authority + 0.12)

    blended = current_dir.lerp(desired, control_authority)
    if blended.length_squared() == 0:
        blended = desired
    else:
        blended = blended.normalize()

    forward_mag = current_vel.dot(blended)
    forward_component = blended * forward_mag
    lateral_component = current_vel - forward_component
    lateral_damping = min(0.85, 0.15 + control_authority * 0.5)
    adjusted_velocity = forward_component + lateral_component * (1.0 - lateral_damping)
    lifeform.velocity = adjusted_velocity
    return blended


def update_movement(lifeform: "Lifeform", state: "SimulationState", dt: float) -> None:
    """Hoofdfunctie voor movement.

    Stappen:
    1. AI / brein updaten → bepaalt gewenste richting (ai.update_brain)
    2. Poging doen om te bewegen op basis van speed & richting
    3. Collisions / boundaries oplossen
    4. Positie & rect bijwerken
    5. Stuck-detectie
    6. Debug-notificaties + short-range interacties
    """

    # --------------------------------------------------
    # 1. Gedrag / AI update (FASE 6)
    # --------------------------------------------------
    ai.update_brain(lifeform, state, dt)

    previous_position = (lifeform.x, lifeform.y)
    now_ms = pygame.time.get_ticks()

    desired = Vector2(lifeform.x_direction, lifeform.y_direction)
    if desired.length_squared() == 0:
        desired = Vector2(1.0, 0.0)
    else:
        desired = desired.normalize()

    desired = _apply_environment_bias(lifeform, desired, state)

    plant_viable = lifeform.closest_plant if lifeform.prefers_plants() else None
    prey_viable = lifeform.closest_prey if lifeform.prefers_meat() else None
    carrion_viable = (
        getattr(lifeform, "closest_carcass", None)
        if lifeform.prefers_meat()
        else None
    )

    if lifeform.should_seek_food() and not (
        plant_viable or prey_viable or carrion_viable
    ):
        search_vec = _ensure_search_vector(lifeform)
        desired = desired.lerp(search_vec, 0.35)
        if desired.length_squared() == 0:
            desired = search_vec
        desired = desired.normalize()
    elif (
        lifeform.should_seek_partner()
        and not lifeform.closest_partner
        and not getattr(lifeform, "_search_partner_vector", None)
    ):
        search_vec = _ensure_search_vector(lifeform)
        desired = desired.lerp(search_vec, 0.3)
        if desired.length_squared() == 0:
            desired = search_vec
        desired = desired.normalize()
    else:
        lifeform._search_vector_timer = 0

    locomotion = getattr(lifeform, "locomotion_profile", None)

    physics_body: PhysicsBody | None = getattr(lifeform, "physics_body", None)
    if physics_body is None:
        logger.warning("Lifeform %s missing physics_body; skipping movement", lifeform.id)
        return

    max_swim_speed = max(1.0, getattr(lifeform, "max_swim_speed", 120.0))

    drift_bias = getattr(lifeform, "drift_preference", 0.0)
    if drift_bias > 0 and lifeform.last_fluid_properties is not None:
        current = lifeform.last_fluid_properties.current
        if current.length_squared() > 0:
            desired = desired.lerp(current.normalize(), min(0.95, drift_bias))

    # --------------------------------------------------
    # Physics & Thrust Calculation
    # --------------------------------------------------

    command_ratio = _behavioral_thrust_ratio(lifeform)
    frequency_ratio = _behavioral_frequency_ratio(lifeform)
    current_speed = lifeform.velocity.length()

    # Update thrust phase for oscillation
    # Frequency depends op gedragssnelheid
    base_freq = 3.0
    frequency = base_freq + frequency_ratio * 5.0

    # Adrenaline boost (FLEE/HUNT)
    target_adrenaline = 0.0
    mode = getattr(lifeform, "current_behavior_mode", "idle")
    if mode in ("flee", "hunt"):
        target_adrenaline = 1.0
        frequency *= 1.45

    # Smoothly interpolate adrenaline
    current_adrenaline = getattr(lifeform, "adrenaline_factor", 0.0)
    lifeform.adrenaline_factor = current_adrenaline * 0.8 + target_adrenaline * 0.2

    lifeform.thrust_phase += frequency * dt
    if lifeform.thrust_phase > 6.28318:
        lifeform.thrust_phase -= 6.28318

    # Oscillating thrust:
    # - Normal: varies between 0.6 and 1.4
    # - Adrenaline: varies between 0.4 and 2.2 (explosive bursts)
    oscillation = math.sin(lifeform.thrust_phase)
    burst_intensity = 0.4 + lifeform.adrenaline_factor * 0.6
    thrust_mod = 1.0 + oscillation * burst_intensity

    # Fin damping (stability)
    fin_count = getattr(lifeform, "fin_count", 0)
    stability = 0.85 + min(0.14, fin_count * 0.02)

    # Apply thrust
    base_effort = _compute_thrust_effort(lifeform, current_speed, command_ratio)
    effort = base_effort * thrust_mod

    # Burst logic from locomotion profile (superimposed on oscillation)
    if locomotion and locomotion.burst_force > 1.0:
        if lifeform._burst_timer > 0:
            effort *= locomotion.burst_force
            lifeform._burst_timer -= 1
        elif lifeform._burst_cooldown > 0:
            lifeform._burst_cooldown -= 1
        else:
            should_burst = (
                lifeform.closest_enemy
                or lifeform.closest_prey
                or lifeform.should_seek_food()
                or mode == "flee"
            )
            if should_burst and lifeform.energy_now > 20.0:
                # Only trigger burst if we are in the positive phase of oscillation
                if oscillation > 0.3:
                    lifeform._burst_timer = max(5, locomotion.burst_duration + 1)
                    lifeform._burst_cooldown = max(22, int(locomotion.burst_cooldown * 0.75))
                    effort *= locomotion.burst_force

    clamped_effort = max(-1.0, min(2.0, effort)) # Allow bursting > 1.0
    propulsion_acceleration = physics_body.propulsion_acceleration(min(1.0, clamped_effort)) * max(1.0, clamped_effort)
    propulsion_force = physics_body.max_thrust * clamped_effort

    desired = _blend_desired_with_velocity(lifeform, desired)
    thrust_vector = _compose_steering_thrust(lifeform, physics_body, desired, propulsion_acceleration)
    telemetry.movement_sample(
        tick=now_ms,
        lifeform=lifeform,
        desired=desired,
        thrust=propulsion_acceleration,
        effort=clamped_effort,
    )
    attempted_position, fluid = state.world.apply_fluid_dynamics(
        lifeform,
        thrust_vector,
        dt,
        max_speed=max_swim_speed,
    )
    if fluid is not None:
        lifeform.last_fluid_properties = fluid
        if getattr(lifeform, "locomotion_strategy", "") == "tentacle_walker":
            stick = min(0.9, getattr(lifeform, "grip_strength", 1.0) * 0.4)
            lifeform.velocity -= fluid.current * stick * 0.015

    effort_magnitude = abs(clamped_effort)
    motion_cost = getattr(lifeform, "motion_energy_cost", 1.0)
    energy_spent = (
        (physics_body.energy_cost * 0.01 + physics_body.power_output * 0.002)
        * effort_magnitude
        * motion_cost
        * max(0.016, dt)
        + abs(propulsion_force) * 0.0004
    )
    if clamped_effort > 1.0:
        energy_spent *= clamped_effort * 1.1
    if drift_bias > 0.5:
        energy_spent *= 0.6
    lifeform.energy_now = max(0.0, lifeform.energy_now - energy_spent)
    attempted_x = float(attempted_position.x)
    attempted_y = float(attempted_position.y)

    candidate_rect = lifeform.rect.copy()
    candidate_rect.update(
        int(attempted_x),
        int(attempted_y),
        lifeform.width,
        lifeform.height,
    )

    # --------------------------------------------------
    # 2. Movement-resolutie via de wereld
    # --------------------------------------------------
    (
        resolved_x,
        resolved_y,
        hit_boundary_x,
        hit_boundary_y,
        collided,
    ) = state.world.resolve_entity_movement(
        candidate_rect,
        previous_position,
        (attempted_x, attempted_y),
    )

    # --------------------------------------------------
    # 3. Collisions / boundaries / escape-logica
    # --------------------------------------------------
    if collided:
        grip = max(0.5, getattr(lifeform, "grip_strength", 1.0))
        lifeform.velocity *= -0.2 / grip
        lifeform.x_direction = -lifeform.x_direction
        lifeform.y_direction = -lifeform.y_direction

        # ⬇️ NIEUW: alleen een nieuwe escape starten als we NIET al in escape-modus zitten
        if lifeform._escape_timer == 0:
            logger.warning(
                "Lifeform %s collided with obstacle at (%.1f, %.1f)",
                lifeform.id,
                resolved_x,
                resolved_y,
            )
            lifeform._trigger_escape_manoeuvre("collision")
            lifeform._boundary_contact_frames = 0

    else:
        grip = max(0.5, getattr(lifeform, "grip_strength", 1.0))
        if hit_boundary_x:
            lifeform.x_direction = -lifeform.x_direction
            lifeform.velocity.x *= -0.25 / grip
        if hit_boundary_y:
            lifeform.y_direction = -lifeform.y_direction
            lifeform.velocity.y *= -0.25 / grip

        if hit_boundary_x or hit_boundary_y:
            lifeform._boundary_contact_frames += 1
            if lifeform._boundary_contact_frames >= settings.STUCK_FRAMES_THRESHOLD:
                logger.info(
                    "Lifeform %s hugging boundary at (%.1f, %.1f) for %s frames",
                    lifeform.id,
                    resolved_x,
                    resolved_y,
                    lifeform._boundary_contact_frames,
                )
                lifeform._trigger_escape_manoeuvre("boundary")
        else:
            lifeform._boundary_contact_frames = 0

    # --------------------------------------------------
    # 4. Positie & rect bijwerken
    # --------------------------------------------------
    if getattr(lifeform, "locomotion_strategy", "") == "benthic_crawler":
        resolved_x, resolved_y = _anchor_benthic_crawler(lifeform, state, resolved_x, resolved_y)
    lifeform.x = resolved_x
    lifeform.y = resolved_y
    lifeform.rect.update(
        int(lifeform.x),
        int(lifeform.y),
        lifeform.width,
        lifeform.height,
    )

    # --------------------------------------------------
    # 5. Stuck-detectie
    # --------------------------------------------------
    displacement = Vector2(
        lifeform.x - previous_position[0],
        lifeform.y - previous_position[1],
    )

    if getattr(lifeform, "_voluntary_pause", False):
        lifeform._stuck_frames = 0
    elif displacement.length() < 0.05:
        lifeform._stuck_frames += 1
        if lifeform._stuck_frames == settings.STUCK_FRAMES_THRESHOLD:
            logger.warning(
                "Lifeform %s stuck near (%.1f, %.1f); triggering escape",
                lifeform.id,
                lifeform.x,
                lifeform.y,
            )
            lifeform._trigger_escape_manoeuvre("stuck")
    else:
        lifeform._stuck_frames = 0

    # --------------------------------------------------
    # 6. Debug-notificaties & korte-afstand interacties
    # --------------------------------------------------
    context = lifeform.notification_context

    if context:
        if lifeform.closest_enemy:
            context.debug(f"{lifeform.id} ziet vijand {lifeform.closest_enemy.id}")
        if lifeform.closest_prey:
            context.debug(f"{lifeform.id} heeft prooi {lifeform.closest_prey.id}")
        if lifeform.closest_partner:
            context.debug(f"{lifeform.id} heeft partner {lifeform.closest_partner.id}")

    # FASE 7: korte-afstand interacties
    combat.resolve_close_interactions(lifeform)


def _anchor_benthic_crawler(
    lifeform: "Lifeform", state: "SimulationState", resolved_x: float, resolved_y: float
) -> tuple[float, float]:
    """Let benthic crawlers stick to nearby rock faces and the seafloor."""

    world = state.world
    anchor_range = max(18, int(lifeform.height * 0.8))
    candidate_rect = lifeform.rect.copy()
    candidate_rect.update(int(resolved_x), int(resolved_y), lifeform.width, lifeform.height)

    best_gap = anchor_range + 1
    best_axis: str | None = None
    best_target = 0.0

    seafloor = world.height - lifeform.height - 2
    floor_gap = abs(seafloor - resolved_y)
    if floor_gap < best_gap:
        best_gap = floor_gap
        best_axis = "floor"
        best_target = float(seafloor)

    for barrier in world.barriers:
        vertical_overlap = not (
            candidate_rect.bottom < barrier.rect.top - anchor_range
            or candidate_rect.top > barrier.rect.bottom + anchor_range
        )
        horizontal_overlap = not (
            candidate_rect.right < barrier.rect.left - anchor_range
            or candidate_rect.left > barrier.rect.right + anchor_range
        )

        if vertical_overlap:
            if candidate_rect.left >= barrier.rect.right:
                gap = candidate_rect.left - barrier.rect.right
                if gap < best_gap:
                    best_gap = gap
                    best_axis = "left"
                    best_target = float(barrier.rect.right + 1)
            if candidate_rect.right <= barrier.rect.left:
                gap = barrier.rect.left - candidate_rect.right
                if gap < best_gap:
                    best_gap = gap
                    best_axis = "right"
                    best_target = float(barrier.rect.left - lifeform.width - 1)

        if horizontal_overlap and candidate_rect.top >= barrier.rect.bottom:
            gap = candidate_rect.top - barrier.rect.bottom
            if gap < best_gap:
                best_gap = gap
                best_axis = "ceiling"
                best_target = float(barrier.rect.bottom + 1)

    anchor = min(0.92, lifeform.grip_strength * 0.35)
    if best_axis == "floor":
        resolved_y = resolved_y * (1.0 - anchor) + best_target * anchor
    elif best_axis == "left":
        resolved_x = resolved_x * (1.0 - anchor) + best_target * anchor
    elif best_axis == "right":
        resolved_x = resolved_x * (1.0 - anchor) + best_target * anchor
    elif best_axis == "ceiling":
        resolved_y = resolved_y * (1.0 - anchor * 0.8) + best_target * anchor * 0.8

    return resolved_x, resolved_y

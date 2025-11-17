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
from typing import TYPE_CHECKING

from pygame.math import Vector2

from ..config import settings
from ..physics.physics_body import PhysicsBody
from . import ai, combat  # Gebruik aparte modules voor gedrag en interacties

logger = logging.getLogger("evolution.movement")

if TYPE_CHECKING:
    from .lifeform import Lifeform
    from evolution.simulation.state import SimulationState


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

    desired = Vector2(lifeform.x_direction, lifeform.y_direction)
    if desired.length_squared() == 0:
        desired = Vector2(1.0, 0.0)
    else:
        desired = desired.normalize()

    locomotion = getattr(lifeform, "locomotion_profile", None)

    physics_body: PhysicsBody | None = getattr(lifeform, "physics_body", None)
    if physics_body is None:
        logger.warning("Lifeform %s missing physics_body; skipping movement", lifeform.id)
        return

    drift_bias = getattr(lifeform, "drift_preference", 0.0)
    if drift_bias > 0 and lifeform.last_fluid_properties is not None:
        current = lifeform.last_fluid_properties.current
        if current.length_squared() > 0:
            desired = desired.lerp(current.normalize(), min(0.95, drift_bias))

    thrust_multiplier = 1.0
    if locomotion and locomotion.burst_force > 1.0:
        if lifeform._burst_timer > 0:
            thrust_multiplier = locomotion.burst_force
            lifeform._burst_timer -= 1
        elif lifeform._burst_cooldown > 0:
            lifeform._burst_cooldown -= 1
        else:
            should_burst = (
                lifeform.closest_enemy
                or lifeform.closest_prey
                or lifeform.should_seek_food()
            )
            energy_threshold = max(
                5.0,
                getattr(lifeform, "motion_energy_cost", 1.0)
                * max(1.5, locomotion.burst_force),
            )
            has_energy = lifeform.energy_now > energy_threshold and not getattr(
                lifeform, "_energy_starved", False
            )
            if should_burst and has_energy:
                lifeform._burst_timer = max(4, locomotion.burst_duration)
                lifeform._burst_cooldown = max(30, locomotion.burst_cooldown)
                thrust_multiplier = locomotion.burst_force
    elif getattr(lifeform, "_burst_cooldown", 0) > 0:
        lifeform._burst_cooldown -= 1

    base_speed = getattr(lifeform, "speed", 0.0)
    max_speed = max(1.0, getattr(lifeform, "max_swim_speed", 120.0))
    speed_ratio = max(0.0, min(1.0, base_speed / max_speed))
    base_effort = speed_ratio * getattr(lifeform, "propulsion_efficiency", 1.0)
    effort = base_effort * thrust_multiplier
    clamped_effort = max(-1.0, min(1.0, effort))
    propulsion_force = physics_body.max_thrust * clamped_effort
    propulsion_acceleration = physics_body.propulsion_acceleration(clamped_effort)
    thrust = desired * propulsion_acceleration
    attempted_position, fluid = state.world.apply_fluid_dynamics(
        lifeform,
        thrust,
        dt,
        max_speed=max_speed,
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
    if thrust_multiplier > 1.0:
        energy_spent *= thrust_multiplier * 1.1
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

    collision_type = None
    if collided:
        collision_type = "world"

    if not collided:
        plant_rect = lifeform.rect.copy()
        plant_rect.update(int(resolved_x), int(resolved_y), lifeform.width, lifeform.height)
        for plant in state.plants:
            if plant.blocks_rect(plant_rect):
                collided = True
                resolved_x, resolved_y = previous_position
                collision_type = "plant"
                break

    # --------------------------------------------------
    # 3. Collisions / boundaries / escape-logica
    # --------------------------------------------------
    blocked_by_plant = collision_type == "plant"

    if collided:
        grip = max(0.5, getattr(lifeform, "grip_strength", 1.0))
        lifeform.velocity *= -0.2 / grip
        if blocked_by_plant:
            # Zacht tegen een plant botsen: blijf staan zodat eten mogelijk is,
            # maar zie de plant wél als obstakel zodat we er niet doorheen lopen.
            lifeform._stuck_frames = 0
        else:
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
        seafloor = state.world.height - lifeform.height - 2
        if seafloor >= 0:
            anchor = min(0.9, lifeform.grip_strength * 0.35)
            resolved_y = resolved_y * (1.0 - anchor) + seafloor * anchor
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

    if getattr(lifeform, "_voluntary_pause", False) or blocked_by_plant:
        lifeform._stuck_frames = 0
    elif displacement.length() < 0.25:
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

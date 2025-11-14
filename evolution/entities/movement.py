"""Generic movement & collision handling for Lifeforms.

Deze module:
- roept het AI-brein (ai.update_brain) aan om x/y richting te bepalen
- berekent verplaatsing op basis van richting & speed
- lost collisions & boundaries op via state.world.resolve_entity_movement(...)
- houdt bij of een lifeform 'vastzit' of langs de rand schuurt
- triggert escape manoeuvres (via Lifeform._trigger_escape_manoeuvre)
- laat Lifeform zelf close-combat / eten / paren doen (_handle_close_interactions)

In latere fases kun je combat naar een aparte module verplaatsen.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pygame.math import Vector2

from ..config import settings
from . import ai  # ⬅️ nieuw: gebruik de AI-module

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

    dx = lifeform.x_direction
    dy = lifeform.y_direction

    # Safety fallback
    if dx == 0 and dy == 0:
        dx, dy = 1.0, 0.0

    speed = lifeform.speed
    if getattr(lifeform, "behaviour_phase", "") == ai.PHASE_RETURN_HOME:
        multiplier = float(
            state.gameplay_settings.get(
                "home_return_speed_multiplier", settings.HOME_RETURN_SPEED_MULTIPLIER
            )
        )
        speed *= multiplier

    attempted_x = lifeform.x + dx * speed
    attempted_y = lifeform.y + dy * speed

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

    if not collided:
        plant_rect = lifeform.rect.copy()
        plant_rect.update(int(resolved_x), int(resolved_y), lifeform.width, lifeform.height)
        for plant in state.plants:
            if plant.blocks_rect(plant_rect):
                collided = True
                resolved_x, resolved_y = previous_position
                break

    # --------------------------------------------------
    # 3. Collisions / boundaries / escape-logica
    # --------------------------------------------------
    if collided:
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
        if hit_boundary_x:
            lifeform.x_direction = -lifeform.x_direction
        if hit_boundary_y:
            lifeform.y_direction = -lifeform.y_direction

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

    if displacement.length() < 0.25:
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

    # FASE 7: hier kun je later combat.update_combat(lifeform, state, dt) van maken
    lifeform._handle_close_interactions()

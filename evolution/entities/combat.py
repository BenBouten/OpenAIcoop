"""Close-range interaction helpers for lifeforms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import settings
from . import feeding

if TYPE_CHECKING:
    from .lifeform import Lifeform


def resolve_close_interactions(lifeform: "Lifeform") -> None:
    """Handle biomass biting and reproduction."""

    feeding.resolve_biomass_bites(lifeform)

    effects = lifeform.effects_manager

    partner = lifeform.closest_partner
    partner_range = max(10.0, lifeform.reach * settings.REPRODUCTION_DISTANCE_MULTIPLIER)
    
    reproduce_intent = getattr(lifeform, "reproduce_intent", 0.0)

    if lifeform.can_reproduce():
        # Sexual reproduction
        if (
            reproduce_intent > settings.REPRODUCTION_INTENT_THRESHOLD
            and partner
            and partner.health_now > 0
            and partner.hunger < settings.HUNGER_CRITICAL_THRESHOLD
            and lifeform.distance_to(partner) < partner_range
        ):
            reproduced = lifeform.reproduce(partner)
            if reproduced and effects:
                midpoint_x = (
                    lifeform.x + lifeform.width / 2 + partner.x + partner.width / 2
                ) / 2
                midpoint_y = (lifeform.y + partner.y) / 2 - 14
                effects.spawn_woohoo((midpoint_x, midpoint_y))
        
        # Asexual reproduction (high intent, no partner needed)
        elif reproduce_intent > settings.REPRODUCTION_INTENT_THRESHOLD:
            lifeform.reproduce_asexual()


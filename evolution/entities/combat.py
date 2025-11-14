"""Close-range interaction helpers for lifeforms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import settings

if TYPE_CHECKING:  # pragma: no cover - only for type checkers
    from .lifeform import Lifeform


def resolve_close_interactions(lifeform: "Lifeform") -> None:
    """Handle melee combat, feeding, and reproduction for a lifeform."""

    context = lifeform.notification_context

    enemy = lifeform.closest_enemy
    if enemy and enemy.health_now > 0 and lifeform.distance_to(enemy) < 5:
        damage = max(1, lifeform.attack_power_now - enemy.defence_power_now / 2)
        enemy.health_now -= damage
        enemy.wounded += 2

    prey = lifeform.closest_prey
    if (
        prey
        and prey.health_now > 0
        and lifeform.closest_enemy is None
        and lifeform.prefers_meat()
        and lifeform.distance_to(prey) < 5
    ):
        damage = max(1, lifeform.attack_power_now - prey.defence_power_now / 2)
        prey.health_now -= damage
        prey.wounded += 3
        lifeform.hunger = max(0, lifeform.hunger - 40)
        if context:
            context.action(f"{lifeform.id} valt {prey.id} aan")

    partner = lifeform.closest_partner
    if (
        partner
        and partner.health_now > 0
        and partner.hunger < settings.HUNGER_CRITICAL_THRESHOLD
        and lifeform.can_reproduce()
        and lifeform.distance_to(partner) < 3
    ):
        lifeform.reproduce(partner)

    plant = lifeform.closest_plant
    if (
        plant
        and lifeform.closest_enemy is None
        and lifeform.prefers_plants()
        and plant.resource > 10
        and lifeform.distance_to(plant) < 3
    ):
        if context:
            context.action(f"{lifeform.id} eet van een plant")
        consumption = plant.decrement_resource(
            settings.PLANT_BITE_NUTRITION_TARGET, eater=lifeform
        )
        if consumption:
            satiety_bonus = plant.apply_effect(lifeform, consumption)
            total_nutrition = sum(sample.nutrition for sample in consumption)
            hunger_reduction = (
                total_nutrition * settings.PLANT_HUNGER_SATIATION_PER_NUTRITION + satiety_bonus
            )
            lifeform.hunger = max(0.0, lifeform.hunger - hunger_reduction)

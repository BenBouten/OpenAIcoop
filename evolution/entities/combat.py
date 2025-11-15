"""Close-range interaction helpers for lifeforms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import settings

if TYPE_CHECKING:  # pragma: no cover - only for type checkers
    from .lifeform import Lifeform


def resolve_close_interactions(lifeform: "Lifeform") -> None:
    """Handle melee combat, feeding, and reproduction for a lifeform."""

    context = lifeform.notification_context
    effects = lifeform.effects_manager

    def _lifeform_anchor(entity: "Lifeform") -> tuple[float, float]:
        return (entity.x + entity.width / 2, entity.y - 10)

    enemy = lifeform.closest_enemy
    if enemy and enemy.health_now > 0 and lifeform.distance_to(enemy) < 5:
        damage = max(1, lifeform.attack_power_now - enemy.defence_power_now / 2)
        enemy.health_now -= damage
        enemy.wounded += 2
        if effects:
            enemy_anchor = _lifeform_anchor(enemy)
            lifeform_anchor = _lifeform_anchor(lifeform)
            effects.spawn_damage_label(enemy_anchor, damage)
            effects.spawn_status_label(
                lifeform_anchor,
                "Chomp!",
                color=(255, 180, 120),
            )
            effects.spawn_confetti(
                lifeform_anchor,
                palette=[(255, 180, 120), (255, 210, 150), (255, 150, 150)],
                count=10,
                strength=18,
            )
            if enemy.health_now <= 0:
                effects.spawn_status_label(
                    enemy_anchor,
                    "KO!",
                    color=(255, 220, 120),
                )

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
        if effects:
            prey_anchor = _lifeform_anchor(prey)
            lifeform_anchor = _lifeform_anchor(lifeform)
            effects.spawn_damage_label(prey_anchor, damage)
            effects.spawn_status_label(
                lifeform_anchor,
                "Chomp!",
                color=(255, 200, 160),
            )
            effects.spawn_confetti(
                lifeform_anchor,
                palette=[(255, 200, 160), (255, 220, 190), (255, 160, 120)],
                count=12,
                strength=20,
            )
            if prey.health_now <= 0:
                effects.spawn_status_label(
                    prey_anchor,
                    "KO!",
                    color=(255, 240, 150),
                )

    partner = lifeform.closest_partner
    if (
        partner
        and partner.health_now > 0
        and partner.hunger < settings.HUNGER_CRITICAL_THRESHOLD
        and lifeform.can_reproduce()
        and lifeform.distance_to(partner) < 3
    ):
        reproduced = lifeform.reproduce(partner)
        if reproduced and effects:
            midpoint_x = (
                lifeform.x + lifeform.width / 2 + partner.x + partner.width / 2
            ) / 2
            midpoint_y = (lifeform.y + partner.y) / 2 - 14
            effects.spawn_woohoo((midpoint_x, midpoint_y))

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
            if effects:
                anchor = _lifeform_anchor(lifeform)
                bite_text = f"+{int(round(hunger_reduction))}"
                effects.spawn_status_label(anchor, bite_text, color=(120, 220, 160))
                plant_center = (
                    plant.x + plant.width / 2,
                    plant.y + plant.height / 2,
                )
                effects.spawn_confetti(
                    plant_center,
                    palette=[
                        (120, 220, 160),
                        (180, 255, 200),
                        (120, 200, 255),
                    ],
                    count=10,
                    strength=18,
                )

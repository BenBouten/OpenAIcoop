"""Close-range interaction helpers for lifeforms."""

from __future__ import annotations

import pygame

from typing import TYPE_CHECKING
from ..config import settings
from ..systems import telemetry
from . import ai

if TYPE_CHECKING:
    from .lifeform import Lifeform


def resolve_close_interactions(lifeform: "Lifeform") -> None:
    """Handle melee combat, predation, plant-feeding, reproduction."""

    context = lifeform.notification_context
    effects = lifeform.effects_manager

    def _lifeform_anchor(entity: "Lifeform") -> tuple[float, float]:
        return (entity.x + entity.width / 2, entity.y - 10)

    enemy = lifeform.closest_enemy
    base_size = max(lifeform.width, lifeform.height)
    enemy_reach = max(3.5, lifeform.reach + base_size * 0.25)
    if enemy and enemy.health_now > 0 and lifeform.distance_to(enemy) < enemy_reach:
        damage = max(1, lifeform.attack_power_now - enemy.defence_power_now / 2)
        enemy.health_now -= damage
        telemetry.combat_sample(
            tick=pygame.time.get_ticks(),
            attacker=lifeform,
            defender=enemy,
            damage=damage,
        )
        enemy.wounded += 2
        lifeform.record_activity(
            "Valt vijand aan",
            doel=getattr(enemy, "id", None),
            schade=damage,
        )
        if hasattr(enemy, "record_activity"):
            enemy.record_activity(
                "Wordt aangevallen",
                aanvaller=getattr(lifeform, "id", None),
                schade=damage,
            )
        
        # Force threat recognition (pain response)
        ai.register_threat(enemy, lifeform, pygame.time.get_ticks())

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
            effects.spawn_bite_label(
                lifeform_anchor,
                "Chomp!",
                color=(255, 180, 120),
            )
            if enemy.health_now <= 0:
                effects.spawn_status_label(
                    enemy_anchor,
                    "KO!",
                    color=(255, 220, 120),
                )
                effects.spawn_bite_label(
                    enemy_anchor,
                    "KO!",
                    color=(255, 220, 120),
                )

    prey = lifeform.closest_prey
    prey_reach = max(4.0, lifeform.reach + base_size * 0.35)
    if (
        prey
        and prey.health_now > 0
        and lifeform.closest_enemy is None
        and lifeform.prefers_meat()
        and lifeform.distance_to(prey) < prey_reach
    ):
        damage = max(1, lifeform.attack_power_now - prey.defence_power_now / 2)
        prey.health_now -= damage
        telemetry.combat_sample(
            tick=pygame.time.get_ticks(),
            attacker=lifeform,
            defender=prey,
            damage=damage,
        )
        prey.wounded += 3
        lifeform.hunger = max(settings.HUNGER_MINIMUM, lifeform.hunger - 40)
        if context:
            context.action(f"{lifeform.id} valt {prey.id} aan")
        lifeform.record_activity(
            "Aanvallen prooi",
            doel=getattr(prey, "id", None),
            schade=damage,
        )
        if hasattr(prey, "record_activity"):
            prey.record_activity(
                "Wordt opgejaagd",
                aanvaller=getattr(lifeform, "id", None),
                schade=damage,
            )
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
            effects.spawn_bite_label(
                lifeform_anchor,
                "Chomp!",
                color=(255, 200, 160),
            )
            if prey.health_now <= 0:
                effects.spawn_status_label(
                    prey_anchor,
                    "KO!",
                    color=(255, 240, 150),
                )
                effects.spawn_bite_label(
                    prey_anchor,
                    "KO!",
                    color=(255, 240, 150),
                )

    carcass = getattr(lifeform, "closest_carcass", None)
    carrion_range = max(5.0, lifeform.reach * 0.8 + base_size * 0.4)
    if (
        carcass
        and lifeform.prefers_meat()
        and lifeform.closest_enemy is None
        and getattr(carcass, "resource", 0) > 0
        and lifeform.distance_to_carcass(carcass) < carrion_range
    ):
        bite = carcass.consume(settings.PLANT_BITE_NUTRITION_TARGET * 1.2)
        if bite > 0:
            carcass.apply_effect(lifeform, bite)
            lifeform.record_activity("Eet aas", voeding=bite)
            if effects:
                anchor = _lifeform_anchor(lifeform)
                effects.spawn_status_label(anchor, "Carrion", color=(220, 200, 160))
            if getattr(carcass, "is_depleted", lambda: False)():
                if carcass in getattr(lifeform.state, "carcasses", []):
                    lifeform.state.carcasses.remove(carcass)

    partner = lifeform.closest_partner
    partner_range = max(3.0, lifeform.reach * 0.6)
    if (
        partner
        and partner.health_now > 0
        and partner.hunger < settings.HUNGER_CRITICAL_THRESHOLD
        and lifeform.can_reproduce()
        and lifeform.distance_to(partner) < partner_range
    ):
        reproduced = lifeform.reproduce(partner)
        if reproduced and effects:
            midpoint_x = (
                lifeform.x + lifeform.width / 2 + partner.x + partner.width / 2
            ) / 2
            midpoint_y = (lifeform.y + partner.y) / 2 - 14
            effects.spawn_woohoo((midpoint_x, midpoint_y))

    plant = lifeform.closest_plant
    plant_range = max(4.5, lifeform.reach * 0.7 + base_size * 0.4)
    if (
        plant
        and lifeform.closest_enemy is None
        and lifeform.prefers_plants()
        and plant.resource > 0
        and lifeform.distance_to_plant(plant) < plant_range
    ):
        if context:
            context.action(f"{lifeform.id} eet van een plant")
        consumption = plant.decrement_resource(
            settings.PLANT_BITE_NUTRITION_TARGET, eater=lifeform
        )
        if consumption:
            outcome = plant.apply_effect(lifeform, consumption)
            total_nutrition = sum(sample.nutrition for sample in consumption)
            hunger_reduction = (
                total_nutrition * settings.PLANT_HUNGER_SATIATION_PER_NUTRITION
                + outcome.satiety_bonus
            )
            lifeform.hunger = max(
                settings.HUNGER_MINIMUM, lifeform.hunger - hunger_reduction
            )
            lifeform.record_activity(
                "Eet plant",
                voeding=total_nutrition,
                positie=(plant.x, plant.y),
            )
            if effects:
                anchor = _lifeform_anchor(lifeform)
                hunger_amount = int(round(hunger_reduction))
                hunger_prefix = "+" if hunger_amount >= 0 else ""
                hunger_text = f"{hunger_prefix}{hunger_amount} honger"
                effects.spawn_status_label(anchor, hunger_text, color=(120, 220, 160))

                plant_center = (
                    plant.x + plant.width / 2,
                    plant.y + plant.height / 2,
                )
                effects.spawn_bite_label(
                    plant_center,
                    "Munch!",
                    color=(120, 220, 160),
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

                if outcome.health_delta >= 0.5:
                    heal_text = f"+{int(round(outcome.health_delta))} leven"
                    effects.spawn_status_label(anchor, heal_text, color=(170, 240, 190))
                elif outcome.health_delta <= -0.5:
                    damage_text = f"-{int(round(-outcome.health_delta))} leven"
                    effects.spawn_status_label(anchor, damage_text, color=(255, 140, 180))

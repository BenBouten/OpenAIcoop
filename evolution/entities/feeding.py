"""Generic biomass interaction helpers.

This module exposes a small BiomassTarget abstraction so that any
lifeform can bite or eat "stuff" in reach without hard-coded predator or
prey roles. The controller only has to raise ``bite_intent`` and the
system handles energy transfer, wounds, and hunger reduction according
to the target type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

import pygame

from ..config import settings
from . import ai


@dataclass(slots=True)
class BiomassTarget:
    target: object
    tag: str  # "plant" or "meat"
    position: Tuple[float, float]
    distance: float
    hardness: float = 0.0
    is_lifeform: bool = False
    is_dead: bool = False


def _lifeform_anchor(entity) -> tuple[float, float]:
    return (entity.x + entity.width / 2, entity.y - 10)


def _reachable_targets(lifeform) -> List[BiomassTarget]:
    candidates: List[BiomassTarget] = []

    plant = getattr(lifeform, "closest_plant", None)
    if plant is not None and plant.resource > 0:
        distance = lifeform.distance_to_plant(plant)
        position = (plant.rect.centerx, plant.rect.centery)
        hardness = max(0.1, getattr(plant, "density", 0.2))
        candidates.append(
            BiomassTarget(
                target=plant,
                tag="plant",
                position=position,
                distance=distance,
                hardness=hardness,
                is_dead=False,
            )
        )

    carcass = getattr(lifeform, "closest_carcass", None)
    if carcass is not None and getattr(carcass, "resource", 0) > 0:
        distance = lifeform.distance_to_carcass(carcass)
        position = (carcass.rect.centerx, carcass.rect.centery)
        hardness = max(0.05, getattr(carcass, "body_density", 0.2))
        candidates.append(
            BiomassTarget(
                target=carcass,
                tag="meat",
                position=position,
                distance=distance,
                hardness=hardness,
                is_dead=True,
            )
        )

    creature_targets: Iterable[Optional[object]] = (
        getattr(lifeform, "closest_enemy", None),
        getattr(lifeform, "closest_prey", None),
        getattr(lifeform, "closest_partner", None),
    )
    seen: set[int] = set()
    for creature in creature_targets:
        if creature is None or creature.health_now <= 0:
            continue
        if id(creature) in seen:
            continue
        seen.add(id(creature))
        distance = lifeform.distance_to(creature)
        position = (creature.rect.centerx, creature.rect.centery)
        hardness = float(getattr(creature, "tissue_hardness", 0.6))
        candidates.append(
            BiomassTarget(
                target=creature,
                tag="meat",
                position=position,
                distance=distance,
                hardness=hardness,
                is_lifeform=True,
                is_dead=False,
            )
        )

    candidates.sort(key=lambda item: item.distance)
    return candidates


def _apply_plant_bite(lifeform, target: BiomassTarget, bite_strength: float) -> bool:
    plant = target.target
    feeding_radius = lifeform._plant_feeding_radius(plant)
    if target.distance > feeding_radius:
        return False

    consumption = plant.decrement_resource(bite_strength, eater=lifeform)
    if not consumption:
        return False

    digest = float(getattr(lifeform, "digest_efficiency_plants", 1.0))
    outcome = plant.apply_effect(lifeform, consumption, digest_multiplier=digest)
    total_nutrition = sum(sample.nutrition for sample in consumption)
    hunger_reduction = (
        total_nutrition * settings.PLANT_HUNGER_SATIATION_PER_NUTRITION + outcome.satiety_bonus
    ) * digest
    lifeform.hunger = max(settings.HUNGER_MINIMUM, lifeform.hunger - hunger_reduction)

    effects = lifeform.effects_manager
    if effects:
        anchor = _lifeform_anchor(lifeform)
        effects.spawn_bite_label(anchor, "Munch!", color=(120, 220, 160))
    lifeform.record_activity("Bite biomass", doel="plant", voeding=total_nutrition)
    return True


def _apply_carcass_bite(lifeform, target: BiomassTarget, bite_strength: float) -> bool:
    carcass = target.target
    reach = max(5.0, lifeform.reach * 0.8 + max(lifeform.width, lifeform.height) * 0.4)
    if target.distance > reach:
        return False

    nutrition = carcass.consume(bite_strength)
    if nutrition <= 0:
        return False

    digest = float(getattr(lifeform, "digest_efficiency_meat", 1.0))
    carcass.apply_effect(lifeform, nutrition, digest_multiplier=digest)
    lifeform.record_activity("Bite biomass", doel="carrion", voeding=nutrition)

    if getattr(carcass, "is_depleted", lambda: False)():
        if carcass in getattr(lifeform.state, "carcasses", []):
            lifeform.state.carcasses.remove(carcass)

    effects = lifeform.effects_manager
    if effects:
        anchor = _lifeform_anchor(lifeform)
        effects.spawn_bite_label(anchor, "Carrion", color=(220, 200, 160))
    return True


def _apply_creature_bite(lifeform, target: BiomassTarget, bite_strength: float) -> bool:
    other = target.target
    reach = max(4.0, lifeform.reach + max(lifeform.width, lifeform.height) * 0.25)
    if target.distance > reach:
        return False

    resistance = target.hardness * 0.6
    effective_bite = max(0.0, bite_strength - resistance)
    if effective_bite <= 0:
        return False

    other.health_now -= effective_bite
    other.wounded += effective_bite * 0.6
    digest = float(getattr(lifeform, "digest_efficiency_meat", 1.0))
    energy_gain = effective_bite * 0.7 * digest
    lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + energy_gain)
    lifeform.hunger = max(
        settings.HUNGER_MINIMUM,
        lifeform.hunger - effective_bite * digest,
    )

    timestamp = pygame.time.get_ticks()
    ai.register_threat(other, lifeform, timestamp)

    if hasattr(other, "record_activity"):
        other.record_activity("Wordt gebeten", aanvaller=getattr(lifeform, "id", None))
    lifeform.record_activity(
        "Bite biomass",
        doel=getattr(other, "id", None),
        schade=effective_bite,
        voeding=energy_gain,
    )

    effects = lifeform.effects_manager
    if effects:
        enemy_anchor = _lifeform_anchor(other)
        lifeform_anchor = _lifeform_anchor(lifeform)
        effects.spawn_damage_label(enemy_anchor, effective_bite)
        effects.spawn_bite_label(lifeform_anchor, "Chomp!", color=(255, 200, 160))
    return True


def resolve_biomass_bites(lifeform) -> None:
    bite_intent = max(0.0, min(1.0, getattr(lifeform, "bite_intent", 0.0)))
    bite_force = float(getattr(lifeform, "bite_force", 0.0))
    if bite_intent <= 0 or bite_force <= 0:
        return

    attack_component = max(0.0, getattr(lifeform, "attack_power_now", 0.0)) * 0.35
    bite_strength = (bite_force + attack_component) * bite_intent
    bite_strength = max(2.5, min(bite_strength, settings.PLANT_BITE_NUTRITION_TARGET * 2.5))

    for biomass in _reachable_targets(lifeform):
        if biomass.tag == "plant":
            if _apply_plant_bite(lifeform, biomass, bite_strength):
                return
        elif biomass.is_lifeform:
            if _apply_creature_bite(lifeform, biomass, bite_strength):
                return
        else:
            if _apply_carcass_bite(lifeform, biomass, bite_strength):
                return

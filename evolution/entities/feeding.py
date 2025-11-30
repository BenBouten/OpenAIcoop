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
    state = getattr(lifeform, "state", None)
    if state is None:
        return candidates

    position = pygame.math.Vector2(lifeform.x, lifeform.y)
    vision_sq = float(lifeform.vision) * float(lifeform.vision)

    for plant in getattr(state, "plants", []):
        if getattr(plant, "resource", 0) <= 0:
            continue
        center = pygame.math.Vector2(plant.rect.center)
        distance_sq = (center - position).length_squared()
        if distance_sq > vision_sq:
            continue
        distance = distance_sq ** 0.5
        hardness = max(0.1, getattr(plant, "density", 0.2))
        candidates.append(
            BiomassTarget(
                target=plant,
                tag="plant",
                position=(center.x, center.y),
                distance=distance,
                hardness=hardness,
                is_dead=False,
            )
        )

    for carcass in getattr(state, "carcasses", []):
        if getattr(carcass, "resource", 0) <= 0:
            continue
        center = pygame.math.Vector2(carcass.rect.center)
        distance_sq = (center - position).length_squared()
        if distance_sq > vision_sq:
            continue
        distance = distance_sq ** 0.5
        hardness = max(0.05, getattr(carcass, "body_density", 0.2))
        candidates.append(
            BiomassTarget(
                target=carcass,
                tag="meat",
                position=(center.x, center.y),
                distance=distance,
                hardness=hardness,
                is_dead=True,
            )
        )

    for creature in getattr(state, "lifeforms", []):
        if creature is lifeform or creature.health_now <= 0:
            continue
        center = pygame.math.Vector2(creature.rect.center)
        distance_sq = (center - position).length_squared()
        if distance_sq > vision_sq:
            continue
        distance = distance_sq ** 0.5
        hardness = float(getattr(creature, "tissue_hardness", 0.6))
        candidates.append(
            BiomassTarget(
                target=creature,
                tag="meat",
                position=(center.x, center.y),
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
    
    # DEBUG: Log successful plant bite
    try:
        with open("feeding_events.csv", "a") as f:
            f.write(f"{pygame.time.get_ticks()},{getattr(lifeform, 'id', 'unknown')},plant,{total_nutrition:.2f},{bite_strength:.2f}\n")
    except Exception:
        pass

    return True


def _apply_carcass_bite(lifeform, target: BiomassTarget, bite_strength: float) -> bool:
    carcass = target.target
    reach = max(5.0, lifeform.reach * 0.8 + max(lifeform.width, lifeform.height) * 0.4)
    if target.distance > reach:
        return False

    # Check for module-based consumption
    if hasattr(carcass, "consume_module") and hasattr(carcass, "body_graph") and carcass.body_graph:
        # Find an available module to eat
        # Ideally we would pick the closest one, but for now random/first available is fine
        available_modules = []
        consumed = getattr(carcass, "consumed_modules", set())
        
        for node_id in carcass.body_graph.nodes:
            if node_id not in consumed:
                available_modules.append(node_id)
        
        if available_modules:
            # Pick a random module to simulate "biting a chunk"
            import random
            target_module = random.choice(available_modules)
            nutrition = carcass.consume_module(target_module)
        else:
            # No modules left? Fallback to generic consume if implemented, or 0
            nutrition = carcass.consume(bite_strength) if hasattr(carcass, "consume") else 0.0
    else:
        # Legacy carcass
        nutrition = carcass.consume(bite_strength)

    if nutrition <= 0:
        return False

    digest = float(getattr(lifeform, "digest_efficiency_meat", 1.0))
    if hasattr(carcass, "apply_effect"):
        carcass.apply_effect(lifeform, nutrition, digest_multiplier=digest)
    
    lifeform.record_activity("Bite biomass", doel="carrion", voeding=nutrition)

    # DEBUG: Log successful carcass bite
    try:
        with open("feeding_events.csv", "a") as f:
            f.write(f"{pygame.time.get_ticks()},{getattr(lifeform, 'id', 'unknown')},carcass,{nutrition:.2f},{bite_strength:.2f}\n")
    except Exception:
        pass

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
    # Scale damage and energy by victim's growth factor (protect babies)
    growth_factor = getattr(other, "growth_factor", 1.0)
    
    # Small creatures take less damage (harder to hit / glancing blows)
    # But ensure at least some damage (min 20% effectiveness)
    damage_scale = max(0.2, growth_factor)
    effective_bite = max(0.0, bite_strength - resistance) * damage_scale
    
    if effective_bite <= 0:
        return False

    other.health_now -= effective_bite
    other.wounded += effective_bite * 0.6
    digest = float(getattr(lifeform, "digest_efficiency_meat", 1.0))
    
    # Cap energy gain by victim's mass to prevent infinite energy from small prey
    max_energy_gain = getattr(other, "mass", 1.0) * 2.5
    
    # Further reduce energy gain from young creatures (low nutritional density)
    nutrition_scale = max(0.1, growth_factor)
    raw_gain = effective_bite * 0.7 * digest * nutrition_scale
    
    energy_gain = min(raw_gain, max_energy_gain)
    
    lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + energy_gain)
    lifeform.hunger = max(
        settings.HUNGER_MINIMUM,
        lifeform.hunger - effective_bite * digest * nutrition_scale,
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
    bite_force = float(getattr(lifeform, "bite_force", 0.0))
    bite_damage = float(getattr(lifeform, "bite_damage", 0.0))
    
    # Must have either innate bite force or a mouth (bite_damage) to eat
    
    # Must have a mouth (bite_damage > 0) to eat.
    # Innate bite_force alone is not enough - you need a mouth module.
    
    # DEBUG: Log feeding attempts
    if bite_intent > 0.1:
        try:
            with open("feeding_debug.csv", "a") as f:
                f.write(f"{pygame.time.get_ticks()},{getattr(lifeform, 'id', 'unknown')},{bite_intent:.2f},{bite_force:.2f},{bite_damage:.2f}\n")
        except Exception:
            pass

    if bite_intent <= 0 or bite_damage <= 0:
        return

    attack_component = max(0.0, getattr(lifeform, "attack_power_now", 0.0)) * 0.35
    
    # Scale bite strength by energy (exhausted creatures cannot bite hard)
    max_energy = max(1.0, getattr(lifeform, "energy", 100.0))
    current_energy = max(0.0, getattr(lifeform, "energy_now", 0.0))
    energy_factor = max(0.1, current_energy / max_energy)
    
    bite_strength = (bite_force + attack_component) * bite_intent * energy_factor
    bite_strength = max(2.5 * energy_factor, min(bite_strength, settings.PLANT_BITE_NUTRITION_TARGET * 2.5))

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

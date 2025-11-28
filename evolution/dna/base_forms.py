"""Marine base form definitions for future evolution paths.

This module encodes a structured description of the five marine archetypes
requested for the new evolution layer.  It provides deterministic, repeatable
values for DNA, behaviour, mutation tendencies, and integration hooks without
changing runtime selection logic yet.

The helpers at the bottom of the file expose a small registry interface so the
rest of the codebase does not need to know about the internal dict structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple

__all__ = [
    "DNAProfile",
    "BehaviourIdentity",
    "EvolutionRules",
    "SystemInterfaces",
    "BaseForm",
    "BASE_FORMS",
    "EVOLUTION_MATRIX",
    "get_base_form",
    "base_form_keys",
]


@dataclass(frozen=True)
class DNAProfile:
    movement_style: str
    base_speed: float
    agility: float
    defense_bias: float
    attack_bias: float
    sensory_range: float
    metabolism_rate: float
    reproduction_style: str


@dataclass(frozen=True)
class BehaviourIdentity:
    default_state_machine: Tuple[str, ...]
    preferred_depth_layer: str
    energy_strategy: str
    interaction_priority: Tuple[str, ...]


@dataclass(frozen=True)
class EvolutionRules:
    mutation_tendencies: Mapping[str, str]
    evolution_constraints: Tuple[str, ...]
    specialization_directions: Tuple[str, ...]


@dataclass(frozen=True)
class SystemInterfaces:
    """Describe where the base form touches the simulation systems."""

    lifeform_init: str
    ai_bias: str
    movement_style: str
    reproduction: str


@dataclass(frozen=True)
class BaseForm:
    key: str
    label: str
    dna: DNAProfile
    behaviour: BehaviourIdentity
    evolution: EvolutionRules
    interfaces: SystemInterfaces


BASE_FORMS: Dict[str, BaseForm] = {
    "starter_swimmer": BaseForm(
        key="starter_swimmer",
        label="Starter Swimmer",
        dna=DNAProfile(
            movement_style="glide",
            base_speed=0.5,
            agility=0.6,
            defense_bias=0.2,
            attack_bias=0.3,
            sensory_range=30.0,
            metabolism_rate=0.4,
            reproduction_style="egg_cloud",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "flee"),
            preferred_depth_layer="open_water_shallow",
            energy_strategy="balanced",
            interaction_priority=("food", "threat", "mate"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "speed": "moderate",
                "agility": "moderate",
            },
            evolution_constraints=(),
            specialization_directions=(),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="simple fish-like starter",
            ai_bias="balanced",
            movement_style="glide",
            reproduction="standard",
        ),
    ),
    "starter_drifter": BaseForm(
        key="starter_drifter",
        label="Starter Drifter",
        dna=DNAProfile(
            movement_style="pulse",
            base_speed=0.2,
            agility=0.2,
            defense_bias=0.1,
            attack_bias=0.1,
            sensory_range=25.0,
            metabolism_rate=0.3,
            reproduction_style="broadcast_spawn",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "flee"),
            preferred_depth_layer="open_water_shallow",
            energy_strategy="efficient",
            interaction_priority=("food", "threat"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "sensory_range": "moderate",
            },
            evolution_constraints=(),
            specialization_directions=(),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="simple jellyfish-like starter",
            ai_bias="passive",
            movement_style="pulse",
            reproduction="standard",
        ),
    ),
}



EVOLUTION_MATRIX: Dict[str, Mapping[str, str]] = {
    "drifter": {
        "swarm": "Increase pulse efficiency, reduce attack ceiling",
        "lure_predator": "Boost bioluminescent sensors and venom payloads",
        "signal_broadcaster": "Extend sensory_range, add communication traits",
    },
    "burrower": {
        "ambush_predator": "Raise attack_bias, trigger camouflaged strike patterns",
        "trap_layer": "Add mucus net modifiers and territory priority",
        "detritivore_swarm": "Lower attack_bias, raise metabolism efficiency",
    },
    "streamliner": {
        "pack_hunter": "Coordination buffs, moderate defense to sustain",
        "solo_sprinter": "Spike speed/agility, reduce defence_margin",
        "scout_explorer": "Expand sensory_range, favour low drag morphs",
    },
    "tentacle_core": {
        "tool_user": "Add manipulation stats, keep agility ceiling high",
        "ink_striker": "Enable ink cloud cooldowns and burst jets",
        "reef_engineer": "Increase territory priority and grip strength",
    },
    "bastion": {
        "tank": "Stack defense_bias and shell_density, lower speed",
        "living_wall": "Anchor to terrain, expand territorial range",
        "slow_grazer": "Metabolism minimisation, broaden detritus diet",
    },
}


def get_base_form(key: str) -> BaseForm:
    """Return a base form by key, raising ``KeyError`` when unknown.

    This helper provides a narrow interface for callers so that any future
    refactors of ``BASE_FORMS`` do not require touching call sites.
    """

    return BASE_FORMS[key]


def base_form_keys() -> Tuple[str, ...]:
    """Expose the available base form keys as an immutable tuple.

    The tuple is safe to reuse in validation logic or UI selection lists
    without risking accidental mutation of the underlying registry.
    """

    return tuple(BASE_FORMS.keys())

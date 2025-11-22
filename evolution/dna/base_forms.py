"""Marine base form definitions for future evolution paths.

This module encodes a structured description of the five marine archetypes
requested for the new evolution layer.  It provides deterministic, repeatable
values for DNA, behaviour, mutation tendencies, and integration hooks without
changing runtime selection logic yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


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
    "drifter": BaseForm(
        key="drifter",
        label="Drifter (Jelly / Qual)",
        dna=DNAProfile(
            movement_style="pulse",
            base_speed=0.35,
            agility=0.25,
            defense_bias=0.3,
            attack_bias=0.15,
            sensory_range=38.0,
            metabolism_rate=0.5,
            reproduction_style="broadcast_spawn",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "flee"),
            preferred_depth_layer="sunlit_midwater",
            energy_strategy="efficient",
            interaction_priority=("threat", "food", "territory", "mate"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "sensory_range": "fast",
                "metabolism_rate": "slow",
                "defense_bias": "slow",
                "attack_bias": "slow",
            },
            evolution_constraints=("cannot_gain_heavy_armor", "no_hard_limb_growth"),
            specialization_directions=("swarm", "lure_predator", "signal_broadcaster"),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="seed buoyant physics defaults and bell core modules",
            ai_bias="high threat aversion, avoid pursuit loops",
            movement_style="map pulse locomotion to soft-drag physics",
            reproduction="compatible with broadcast and drift-fertilisation",
        ),
    ),
    "burrower": BaseForm(
        key="burrower",
        label="Burrower (Sea Worm)",
        dna=DNAProfile(
            movement_style="slither",
            base_speed=0.25,
            agility=0.3,
            defense_bias=0.45,
            attack_bias=0.25,
            sensory_range=30.0,
            metabolism_rate=0.35,
            reproduction_style="egg_cluster",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "flee", "hunt"),
            preferred_depth_layer="benthic_silt",
            energy_strategy="efficient",
            interaction_priority=("food", "threat", "territory", "mate"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "defense_bias": "fast",
                "burrow_depth": "fast",
                "agility": "moderate",
                "attack_bias": "slow",
            },
            evolution_constraints=("no_open_water_charge", "cannot_add_buoyant_sails"),
            specialization_directions=("ambush_predator", "trap_layer", "detritivore_swarm"),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="bias towards trench biomes and sediment grip",
            ai_bias="prefers ambush flags and hiding behaviour tree nodes",
            movement_style="use slither locomotion with high grip and drag",
            reproduction="compatible with egg cluster and paired burrow spawns",
        ),
    ),
    "streamliner": BaseForm(
        key="streamliner",
        label="Streamliner (Fish-like)",
        dna=DNAProfile(
            movement_style="glide",
            base_speed=0.6,
            agility=0.55,
            defense_bias=0.35,
            attack_bias=0.45,
            sensory_range=45.0,
            metabolism_rate=0.65,
            reproduction_style="egg_cloud",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "hunt", "flee"),
            preferred_depth_layer="open_water_mid",
            energy_strategy="aggressive",
            interaction_priority=("food", "threat", "mate", "territory"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "speed": "fast",
                "agility": "fast",
                "attack_bias": "moderate",
                "defense_bias": "slow",
            },
            evolution_constraints=("cannot_gain_anchor_limbs", "no_full_shell"),
            specialization_directions=("pack_hunter", "solo_sprinter", "scout_explorer"),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="initialize higher thrust and fin modules",
            ai_bias="balanced threat assessment with active pursuit",
            movement_style="glide and burst mapped to hydrodynamic drag curves",
            reproduction="compatible with cloud spawning and roaming pairs",
        ),
    ),
    "tentacle_core": BaseForm(
        key="tentacle_core",
        label="Tentacle Core (Octopus-like)",
        dna=DNAProfile(
            movement_style="jet",
            base_speed=0.45,
            agility=0.7,
            defense_bias=0.4,
            attack_bias=0.5,
            sensory_range=50.0,
            metabolism_rate=0.7,
            reproduction_style="brooded_clusters",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "hunt", "flee"),
            preferred_depth_layer="reef_crevices",
            energy_strategy="aggressive",
            interaction_priority=("threat", "food", "territory", "mate"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "agility": "fast",
                "attack_bias": "fast",
                "manipulation": "fast",
                "defense_bias": "moderate",
            },
            evolution_constraints=("no_rigid_shell", "cannot_reduce_arm_count_below_four"),
            specialization_directions=("tool_user", "ink_striker", "reef_engineer"),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="inject tentacle limb modules and flexible physics joints",
            ai_bias="high curiosity and short-term memory bias",
            movement_style="jet bursts combined with grip-based climbing",
            reproduction="compatible with brooding and den-guarding logic",
        ),
    ),
    "bastion": BaseForm(
        key="bastion",
        label="Bastion (Shell / Armored)",
        dna=DNAProfile(
            movement_style="crawl",
            base_speed=0.18,
            agility=0.2,
            defense_bias=0.75,
            attack_bias=0.35,
            sensory_range=28.0,
            metabolism_rate=0.4,
            reproduction_style="plated_broadcast",
        ),
        behaviour=BehaviourIdentity(
            default_state_machine=("idle", "forage", "flee"),
            preferred_depth_layer="benthic_rocky",
            energy_strategy="passive",
            interaction_priority=("threat", "territory", "food", "mate"),
        ),
        evolution=EvolutionRules(
            mutation_tendencies={
                "defense_bias": "fast",
                "shell_density": "fast",
                "metabolism_rate": "slow",
                "speed": "slow",
            },
            evolution_constraints=("cannot_adopt_jet", "limited_joint_range"),
            specialization_directions=("tank", "living_wall", "slow_grazer"),
        ),
        interfaces=SystemInterfaces(
            lifeform_init="prefers heavy physics bodies and shell modules",
            ai_bias="holds position, low pursuit likelihood",
            movement_style="crawl locomotion with high drag and grip",
            reproduction="compatible with slow broadcast and guarded nests",
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

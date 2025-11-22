"""Helpers to assemble DNA blueprints for modular body graphs."""
from __future__ import annotations

import math
import random
from typing import Dict, Iterable, Mapping, Optional, Sequence

from .genes import Genome, GenomeConstraints, ModuleGene

__all__ = ["generate_modular_blueprint"]

_SENSOR_SPECTRUMS: Mapping[str, Sequence[Sequence[str]]] = {
    "herbivore": (
        ("light", "colour"),
        ("electro",),
        ("pheromone",),
    ),
    "omnivore": (
        ("light", "colour"),
        ("sonar",),
        ("bioelectric",),
    ),
    "carnivore": (
        ("sonar",),
        ("bioelectric",),
        ("thermal",),
    ),
}

_DEFAULT_CONSTRAINTS = GenomeConstraints(max_mass=240.0, nerve_capacity=36.0)

_MODULE_NERVE_LOAD = {
    "core": 5.0,
    "head": 3.0,
    "limb": 1.8,
    "propulsion": 2.5,
    "sensor": 0.8,
}


def _next_gene_id(base: str, existing: Iterable[str]) -> str:
    used = set(existing)
    if base not in used:
        return base
    index = 2
    while f"{base}_{index}" in used:
        index += 1
    return f"{base}_{index}"


def _sensor_parameters(spectrum: Sequence[str]) -> Dict[str, object]:
    return {"spectrum": list(spectrum)}


def _select_spectrum(diet: str, rng: random.Random) -> Sequence[str]:
    options = _SENSOR_SPECTRUMS.get(diet, _SENSOR_SPECTRUMS["omnivore"])
    return rng.choice(tuple(options))


_MIN_ATTACHMENTS = {
    "core": ("head_socket", "ventral_core"),
}

_DIET_MODULE_POOLS: Dict[str, Dict[str, Sequence[str]]] = {
    "herbivore": {
        "core": ("head", "thruster", "fin_left", "fin_right", "sensor"),
        "head": ("sensor", "limb"),
    },
    "carnivore": {
        "core": ("head", "thruster", "limb", "limb", "sensor", "sensor"),
        "head": ("sensor", "sensor"),
    },
    "omnivore": {
        "core": ("head", "thruster", "limb", "sensor"),
        "head": ("sensor", "limb"),
    },
}

_SLOT_PRIORITY = {
    "head": ["head_socket", "cranial_sensor"],
    "thruster": ["ventral_core", "tail_sensors"],
    # Limbs only mount to core sockets initially; chained segments use "proximal_joint"
    "limb": ["lateral_mount_left", "lateral_mount_right"],
    "sensor": ["cranial_sensor", "dorsal_mount", "tail_sensors"],
}


def _pick_slot(module: str, rng: random.Random) -> str:
    slots = _SLOT_PRIORITY.get(module, ["cranial_sensor"])
    return rng.choice(slots)


def _attach_module(
    genes: Dict[str, ModuleGene],
    module_type: str,
    parent: str,
    slot: str,
    *,
    parameters: Optional[Dict[str, object]] = None,
) -> str:
    gene_id = _next_gene_id(f"{module_type}", genes)
    genes[gene_id] = ModuleGene(
        gene_id,
        module_type,
        parameters or {},
        parent=parent,
        slot=slot,
    )
    return gene_id


def _seed_core_structure(genes: Dict[str, ModuleGene]) -> Dict[str, str]:
    core_id = "core"
    genes[core_id] = ModuleGene(core_id, "core", {})
    head_id = _attach_module(genes, "head", core_id, "head_socket")
    thruster_id = _attach_module(genes, "propulsion", core_id, "ventral_core")
    return {"core": core_id, "head": head_id, "thrusters": thruster_id}


def _random_limb_chain(
    genes: Dict[str, ModuleGene],
    parent: str,
    slot: str,
    rng: random.Random,
) -> None:
    chain_length = 1 + rng.randint(0, 2)
    last_parent = parent
    last_slot = slot
    for index in range(chain_length):
        segment_id = _next_gene_id(f"limb_{parent}_{index}", genes)
        genes[segment_id] = ModuleGene(segment_id, "limb", {}, parent=last_parent, slot=last_slot)
        last_parent = segment_id
        last_slot = "proximal_joint"


def generate_modular_blueprint(
    diet: str,
    *,
    rng: Optional[random.Random] = None,
) -> Dict[str, object]:
    """Build a small but valid modular blueprint tailored to ``diet``."""

    rng = rng or random.Random()
    genes: Dict[str, ModuleGene] = {}

    anchors = _seed_core_structure(genes)
    core_id = anchors["core"]
    head_id = anchors["head"]
    thruster_ids = [anchors["thrusters"]]

    sensor_slots = ["cranial_sensor", "dorsal_mount", "tail_sensors"]
    spectra = list(_SENSOR_SPECTRUMS.get(diet, _SENSOR_SPECTRUMS["omnivore"]))
    rng.shuffle(spectra)
    for slot in sensor_slots:
        if not spectra:
            break
        if rng.random() < 0.65:
            spectrum = list(spectra.pop())
            if slot == "cranial_sensor":
                parent = head_id
            elif slot == "tail_sensors":
                parent = rng.choice(thruster_ids)
            else:
                parent = core_id
            _attach_module(genes, "sensor", parent, slot, parameters=_sensor_parameters(spectrum))

    limb_pairs = rng.randint(1, 3)
    for pair in range(limb_pairs):
        for slot in ("lateral_mount_left", "lateral_mount_right"):
            if rng.random() < 0.6:
                _random_limb_chain(genes, core_id, slot, rng)

    optional_slots = ["dorsal_mount", "tail_sensors"]
    for slot in optional_slots:
        if rng.random() < 0.4:
            parent = core_id if slot == "dorsal_mount" else rng.choice(thruster_ids)
            _attach_module(
                genes,
                "sensor",
                parent,
                slot,
                parameters=_sensor_parameters(_select_spectrum(diet, rng)),
            )

    if rng.random() < 0.3:
        # Thrusters only mount to the ventral slot on the core; tail sockets are reserved for sensors.
        new_thruster = _attach_module(genes, "propulsion", core_id, "ventral_core")
        thruster_ids.append(new_thruster)

    estimated_load = 0.0
    for gene in genes.values():
        estimated_load += _MODULE_NERVE_LOAD.get(gene.module_type, 1.0)
    nerve_capacity = max(_DEFAULT_CONSTRAINTS.nerve_capacity, math.ceil(estimated_load + 1.5))
    constraints = GenomeConstraints(
        max_mass=_DEFAULT_CONSTRAINTS.max_mass,
        nerve_capacity=nerve_capacity,
    )
    genome = Genome(genes=genes, constraints=constraints)
    return genome.to_dict()

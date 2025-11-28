
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
    "round_core": 5.0,
    "bell_core": 4.0,
    "head": 3.0,
    "limb": 1.8,
    "tentacle": 1.4,
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





def generate_modular_blueprint(
    diet: str,
    base_form: Optional[str] = None,
    *,
    rng: Optional[random.Random] = None,
) -> Dict[str, object]:
    """Build a modular blueprint tailored to ``diet`` and ``base_form``."""

    rng = rng or random.Random()
    genes: Dict[str, ModuleGene] = {}

    # Default to a random base form if none provided
    if not base_form:
        # Weighted choice favoring simple starters
        choices = ["starter_swimmer", "starter_drifter"]
        weights = [0.5, 0.5]
        base_form = rng.choices(choices, weights=weights, k=1)[0]

    # Dispatch to specific builders
    if base_form == "starter_swimmer":
        _build_starter_swimmer(genes, diet, rng)
    elif base_form == "starter_drifter":
        _build_starter_drifter(genes, diet, rng)
    else:
        # Fallback to starter swimmer
        _build_starter_swimmer(genes, diet, rng)

    # Calculate nerve load and constraints
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


def _build_starter_swimmer(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Simple fish-like starter: Scaled down Core, Head, 2 Fins, Jet."""
    core_id = "core"
    # Use TrunkCore but scaled down
    genes[core_id] = ModuleGene(core_id, "core", {"size_scale": 0.4})
    
    # Head
    head_id = _attach_module(genes, "head", core_id, "head_socket", parameters={"variant": "simple", "size_scale": 0.5})
    _attach_sensors(genes, head_id, ["cranial_sensor"], diet, rng)
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)
    
    # Propulsion: Jet on tail
    _attach_module(genes, "propulsion", core_id, "ventral_core", parameters={"size_scale": 0.5})
    
    # Stability: Two side fins
    _attach_module(genes, "limb", core_id, "lateral_mount_left", parameters={"variant": "fin", "size_scale": 0.4})
    _attach_module(genes, "limb", core_id, "lateral_mount_right", parameters={"variant": "fin", "size_scale": 0.4})


def _build_starter_drifter(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Simple jellyfish-like starter: Scaled down Core, Head, Hanging Tentacles."""
    core_id = "core"
    # Use RoundCore scaled down
    genes[core_id] = ModuleGene(core_id, "round_core", {"variant": "gelatinous", "size_scale": 0.4})
    
    # Head
    head_id = _attach_module(genes, "head", core_id, "head_socket", parameters={"variant": "simple", "size_scale": 0.5})
    _attach_sensors(genes, head_id, ["cranial_sensor"], diet, rng)
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)
    
    # Propulsion/Drift: Hanging tentacles
    # RoundCore has radial slots.
    
    # Attach tentacles to radials
    for i in range(1, 4):
        slot = f"radial_{i}"
        _attach_module(genes, "tentacle", core_id, slot, parameters={"variant": "tentacle", "size_scale": 0.3})
    
    # And one on ventral
    _attach_module(genes, "tentacle", core_id, "ventral_socket", parameters={"variant": "tentacle", "size_scale": 0.4})





def _attach_sensors(genes: Dict[str, ModuleGene], parent: str, slots: Sequence[str], diet: str, rng: random.Random) -> None:
    spectra = list(_SENSOR_SPECTRUMS.get(diet, _SENSOR_SPECTRUMS["omnivore"]))
    for slot in slots:
        roll = rng.random()
        if roll < 0.5:
            # Attach Eye
            _attach_module(genes, "eye", parent, slot, parameters={"pupil_shape": rng.choice(["circle", "slit", "rect"])})
        elif roll < 0.9:
            spectrum = rng.choice(spectra)
            _attach_module(genes, "sensor", parent, slot, parameters=_sensor_parameters(spectrum))


def _attach_mouth(genes: Dict[str, ModuleGene], parent: str, slot: str, diet: str, rng: random.Random) -> None:
    jaw_types = {
        "carnivore": ["mandibles", "beak"],
        "herbivore": ["beak", "sucker"],
        "omnivore": ["mandibles", "beak", "sucker"],
    }
    jaw_type = rng.choice(jaw_types.get(diet, ["mandibles"]))
    # Check if parent has this slot? We assume yes for now as we added it to CephalonHead.
    # But we should wrap in try/except or just let it fail if slot missing?
    # _attach_module doesn't check slot existence in the gene dict, only when building graph.
    # So it's safe to add the gene.
    _attach_module(genes, "mouth", parent, slot, parameters={"jaw_type": jaw_type})


def _random_limb_chain(
    genes: Dict[str, ModuleGene],
    parent: str,
    slot: str,
    rng: random.Random,
    *,
    length_bias: int = 0,
    module_type: str = "limb",
) -> None:
    chain_length = 1 + rng.randint(0, 2) + length_bias
    last_parent = parent
    last_slot = slot
    for index in range(chain_length):
        segment_id = _next_gene_id(f"{module_type}_{parent}_{index}", genes)
        genes[segment_id] = ModuleGene(segment_id, module_type, {}, parent=last_parent, slot=last_slot)
        # Update for next segment
        # If it's a tentacle, it has 'distal_tip'. If limb, 'proximal_joint'.
        # We need to know the slot for the next segment.
        # This is tricky without instantiating.
        # But we can assume standard naming or pass it in.
        # For now, let's assume 'distal_tip' for tentacles and 'proximal_joint' for limbs.
        last_parent = segment_id
        if module_type == "tentacle":
            last_slot = "distal_tip"
        else:
            last_slot = "proximal_joint"

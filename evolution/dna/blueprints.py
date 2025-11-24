
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


def _seed_core_structure(genes: Dict[str, ModuleGene]) -> Dict[str, str]:
    core_id = "core"
    genes[core_id] = ModuleGene(core_id, "core", {})
    head_id = _attach_module(genes, "head", core_id, "head_socket")
    thruster_id = _attach_module(genes, "propulsion", core_id, "ventral_core")
    return {"core": core_id, "head": head_id, "thrusters": thruster_id}


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
        base_form = rng.choice(["streamliner", "drifter", "burrower", "tentacle_core", "bastion"])

    # Dispatch to specific builders
    if base_form == "drifter":
        _build_drifter(genes, diet, rng)
    elif base_form == "burrower":
        _build_burrower(genes, diet, rng)
    elif base_form == "streamliner":
        _build_streamliner(genes, diet, rng)
    elif base_form == "tentacle_core":
        _build_tentacle_core(genes, diet, rng)
    elif base_form == "bastion":
        _build_bastion(genes, diet, rng)
    else:
        # Fallback to generic streamliner-ish
        _build_streamliner(genes, diet, rng)

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


def _build_drifter(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Jellyfish-like: Bell core, hanging tentacles."""
    core_id = "core"
    # Use RoundCore for Drifter for a more compact, jelly-like body
    genes[core_id] = ModuleGene(core_id, "round_core", {"variant": "gelatinous"})
    
    # Bell / Umbrella
    head_id = _attach_module(genes, "head", core_id, "head_socket", parameters={"variant": "dome"})
    
    # Hanging tentacles from ventral
    tentacle_count = rng.randint(4, 8)
    for i in range(tentacle_count):
        # RoundCore has ventral_socket and radial slots.
        # For a drifter, we want them hanging down.
        # We can attach one main chain to ventral, and others to radials but angled down?
        # Or just attach to radials.
        
        slot = "ventral_socket" if i == 0 else f"radial_{((i-1)%4)+1}"
        
        # Use "tentacle" module type for TentacleLimb
        root = _attach_module(genes, "tentacle", core_id, slot, parameters={"variant": "tentacle"})
        _random_limb_chain(genes, root, "distal_tip", rng, length_bias=3, module_type="tentacle")

    # Sensors on rim (head)
    _attach_sensors(genes, head_id, ["cranial_sensor"], diet, rng)
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)

def _build_burrower(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Worm-like: Segmented chain."""
    core_id = "core"
    genes[core_id] = ModuleGene(core_id, "core", {"variant": "segmented"})
    
    head_id = _attach_module(genes, "head", core_id, "head_socket", parameters={"variant": "conical"})
    _attach_sensors(genes, head_id, ["cranial_sensor"], diet, rng)
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)
    
    # Long chain of segments
    segments = rng.randint(4, 8)
    current_parent = core_id
    current_slot = "tail_socket" # Assuming core has a tail socket
    
    # We need to ensure core has a tail socket or similar. 
    # The default core usually has 'ventral_core', 'head_socket', 'lateral_mount_left/right'.
    # Let's use 'ventral_core' as the "back" for now, or assume a 'tail' slot exists.
    # If not, we chain from ventral.
    
    last_id = core_id
    for i in range(segments):
        seg_id = _next_gene_id(f"segment_{i}", genes)
        genes[seg_id] = ModuleGene(seg_id, "propulsion", {}, parent=last_id, slot="ventral_core" if i==0 else "tail_socket")
        # Add small legs/bristles
        if rng.random() < 0.7:
            _attach_module(genes, "limb", seg_id, "lateral_mount_left", parameters={"variant": "bristle"})
            _attach_module(genes, "limb", seg_id, "lateral_mount_right", parameters={"variant": "bristle"})
        last_id = seg_id


def _build_streamliner(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Fish-like: Head, Core, Tail, Fins."""
    anchors = _seed_core_structure(genes)
    core_id = anchors["core"]
    head_id = anchors["head"]
    thruster_id = anchors["thrusters"]
    
    # Fins
    _attach_module(genes, "limb", core_id, "lateral_mount_left", parameters={"variant": "fin"})
    _attach_module(genes, "limb", core_id, "lateral_mount_right", parameters={"variant": "fin"})
    
    # Dorsal fin
    _attach_module(genes, "limb", core_id, "dorsal_mount", parameters={"variant": "fin_dorsal"})
    
    # Sensors
    # Sensors
    _attach_sensors(genes, head_id, ["cranial_sensor"], diet, rng)
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)

def _build_tentacle_core(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Octopus-like: Central core, radial arms."""
    core_id = "core"
    # Use RoundCore for spherical body
    genes[core_id] = ModuleGene(core_id, "round_core", {"variant": "spherical"})
    head_id = _attach_module(genes, "head", core_id, "head_socket", parameters={"variant": "bulbous"})
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)
    
    # Arms
    arm_count = rng.randint(4, 8)
    for i in range(arm_count):
        # Use RoundCore's radial slots
        slot = f"radial_{(i%4)+1}"
        
        # Use "tentacle" module type
        arm_root = _attach_module(genes, "tentacle", core_id, slot, parameters={"variant": "tentacle"})
        _random_limb_chain(genes, arm_root, "distal_tip", rng, length_bias=3, module_type="tentacle")


def _build_bastion(genes: Dict[str, ModuleGene], diet: str, rng: random.Random) -> None:
    """Crab/Turtle-like: Armored core, legs."""
    core_id = "core"
    genes[core_id] = ModuleGene(core_id, "core", {"variant": "armored"})
    genes[core_id] = ModuleGene(core_id, "core", {"variant": "armored"})
    head_id = _attach_module(genes, "head", core_id, "head_socket", parameters={"variant": "armored_visored"})
    _attach_mouth(genes, head_id, "mouth_socket", diet, rng)
    
    # Shell - represented as rigid limbs/plates
    _attach_module(genes, "limb", core_id, "dorsal_mount", parameters={"variant": "shell_plate"})
    
    # Legs
    _attach_module(genes, "limb", core_id, "lateral_mount_left", parameters={"variant": "leg_armored"})
    _attach_module(genes, "limb", core_id, "lateral_mount_right", parameters={"variant": "leg_armored"})
    
    # Tail shield
    _attach_module(genes, "limb", core_id, "ventral_core", parameters={"variant": "tail_plate"})


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

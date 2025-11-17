"""Helpers to assemble DNA blueprints for modular body graphs."""
from __future__ import annotations

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

_DEFAULT_CONSTRAINTS = GenomeConstraints(max_mass=240.0, nerve_capacity=32.0)


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


def generate_modular_blueprint(
    diet: str,
    *,
    rng: Optional[random.Random] = None,
) -> Dict[str, object]:
    """Build a small but valid modular blueprint tailored to ``diet``."""

    rng = rng or random.Random()
    genes: Dict[str, ModuleGene] = {}

    def _register(gene: ModuleGene) -> None:
        genes[gene.gene_id] = gene

    # Core structure -----------------------------------------------------
    _register(ModuleGene("core", "core", {}))
    _register(ModuleGene("head", "head", {}, parent="core", slot="head_socket"))
    _register(ModuleGene("thruster", "propulsion", {}, parent="core", slot="ventral_core"))
    _register(
        ModuleGene("fin_left", "limb", {}, parent="core", slot="lateral_mount_left")
    )
    _register(
        ModuleGene("fin_right", "limb", {}, parent="core", slot="lateral_mount_right")
    )

    # Sensor suite -------------------------------------------------------
    def _attach_sensor(parent: str, slot: str, base: str, spectrum: Sequence[str]) -> None:
        gene_id = _next_gene_id(base, genes)
        _register(ModuleGene(gene_id, "sensor", _sensor_parameters(spectrum), parent, slot))

    _attach_sensor("head", "cranial_sensor", "head_sensor", _select_spectrum(diet, rng))

    if rng.random() < 0.7:
        _attach_sensor("thruster", "tail_sensors", "tail_sensor", ("sonar",))

    if rng.random() < 0.55:
        dorsal_spectrum = _select_spectrum("omnivore", rng)
        _attach_sensor("core", "dorsal_mount", "dorsal_sensor", dorsal_spectrum)

    constraints = GenomeConstraints(
        max_mass=_DEFAULT_CONSTRAINTS.max_mass,
        nerve_capacity=_DEFAULT_CONSTRAINTS.nerve_capacity,
    )
    genome = Genome(genes=genes, constraints=constraints)
    return genome.to_dict()

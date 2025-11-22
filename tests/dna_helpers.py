from __future__ import annotations

from typing import Dict

from evolution.dna.genes import Genome, GenomeConstraints, ModuleGene


def sample_genes() -> Dict[str, ModuleGene]:
    """Return a representative set of module genes for tests."""

    return {
        "core": ModuleGene("core", "core", {}),
        "head": ModuleGene("head", "head", {}, parent="core", slot="head_socket"),
        "fin_left": ModuleGene(
            "fin_left",
            "limb",
            {},
            parent="core",
            slot="lateral_mount_left",
        ),
        "fin_right": ModuleGene(
            "fin_right",
            "limb",
            {},
            parent="core",
            slot="lateral_mount_right",
        ),
        "thruster": ModuleGene(
            "thruster",
            "propulsion",
            {},
            parent="core",
            slot="ventral_core",
        ),
        "tail_eye": ModuleGene(
            "tail_eye",
            "sensor",
            {"spectrum": ["light", "sonar"]},
            parent="thruster",
            slot="tail_sensors",
        ),
        "crown_sensor": ModuleGene(
            "crown_sensor",
            "sensor",
            {"spectrum": ["bioelectric"]},
            parent="head",
            slot="cranial_sensor",
        ),
        "fin_segment": ModuleGene(
            "fin_segment",
            "limb",
            {},
            parent="fin_left",
            slot="proximal_joint",
        ),
    }


def build_genome(**overrides: object) -> Genome:
    """Helper that constructs a :class:`Genome` with sensible defaults."""

    constraints = overrides.get(
        "constraints",
        GenomeConstraints(max_mass=200.0, nerve_capacity=24.0),
    )
    genes = overrides.get("genes", sample_genes())
    return Genome(genes=genes, constraints=constraints)

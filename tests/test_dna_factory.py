"""Tests for DNA → BodyGraph factory and round-trip serialization."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.dna.factory import build_body_graph, serialize_body_graph
from evolution.dna.genes import Genome, GenomeConstraints, ModuleGene


def _sample_genes() -> dict[str, ModuleGene]:
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
    }


def _build_genome(**overrides: object) -> Genome:
    constraints = overrides.get(
        "constraints",
        GenomeConstraints(max_mass=200.0, nerve_capacity=20.0),
    )
    genes = overrides.get("genes", _sample_genes())
    return Genome(genes=genes, constraints=constraints)


def test_build_body_graph_assembles_modules() -> None:
    genome = _build_genome()
    graph = build_body_graph(genome)

    assert graph.root_id == "core"
    assert set(graph.nodes["core"].children) == {
        "head",
        "fin_left",
        "fin_right",
        "thruster",
    }
    assert graph.nodes["head"].children == {"crown_sensor": "cranial_sensor"}
    assert graph.nodes["thruster"].children == {"tail_eye": "tail_sensors"}


def test_build_body_graph_validates_mass_limit() -> None:
    constraints = GenomeConstraints(max_mass=30.0, nerve_capacity=50.0)
    genome = _build_genome(constraints=constraints)

    with pytest.raises(ValueError, match="exceeds genome limit"):
        build_body_graph(genome)


def test_build_body_graph_validates_nerve_capacity() -> None:
    constraints = GenomeConstraints(max_mass=400.0, nerve_capacity=5.0)
    genome = _build_genome(constraints=constraints)

    with pytest.raises(ValueError, match="nerve load"):
        build_body_graph(genome)


def test_serialize_body_graph_round_trip() -> None:
    genome = _build_genome()
    graph = build_body_graph(genome)

    serialised = serialize_body_graph(graph)
    rebuilt = build_body_graph(serialised)

    assert rebuilt.summary() == graph.summary()

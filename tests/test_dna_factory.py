"""Tests for DNA → BodyGraph factory and round-trip serialization."""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.dna.factory import build_body_graph, serialize_body_graph
from evolution.dna.genes import GenomeConstraints
from .dna_helpers import build_genome as _build_genome


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
    assert graph.nodes["fin_left"].children == {"fin_segment": "proximal_joint"}


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

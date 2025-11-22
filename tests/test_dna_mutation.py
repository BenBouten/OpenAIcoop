from __future__ import annotations

import pathlib
import random
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evolution.dna.factory import build_body_graph, _NERVE_LOAD
from evolution.dna.genes import Genome, GenomeConstraints
from evolution.dna.mutation import (
    MutationError,
    mutate_add_module,
    mutate_adjust_material,
    mutate_adjust_size,
    mutate_remove_module,
)

from .dna_helpers import build_genome


def test_mutate_add_module_attaches_sensor_to_core() -> None:
    genome = build_genome(constraints=GenomeConstraints(max_mass=200.0, nerve_capacity=32.0))

    mutated = mutate_add_module(genome, rng=random.Random(0))

    assert len(mutated.genes) == len(genome.genes) + 1
    new_gene_ids = set(mutated.genes) - set(genome.genes)
    assert len(new_gene_ids) == 1
    gene_id = new_gene_ids.pop()
    gene = mutated.genes[gene_id]
    assert gene.parent == "core"
    assert gene.slot == "dorsal_mount"
    assert gene.module_type == "sensor"


def test_mutate_add_module_respects_nerve_capacity() -> None:
    genome = build_genome()
    graph = build_body_graph(genome)
    nerve_load = sum(
        _NERVE_LOAD.get(node.module.module_type, 1.0)
        for node in graph.nodes.values()
    )
    tight_constraints = GenomeConstraints(
        max_mass=genome.constraints.max_mass,
        nerve_capacity=nerve_load,
    )
    tight_genome = Genome(genes=genome.genes, constraints=tight_constraints)

    with pytest.raises(MutationError, match="nerve load"):
        mutate_add_module(tight_genome, rng=random.Random(1))


def test_mutate_remove_module_drops_subtree() -> None:
    genome = build_genome()

    mutated = mutate_remove_module(genome, target_gene="thruster")

    assert "thruster" not in mutated.genes
    assert "tail_eye" not in mutated.genes


def test_mutate_adjust_size_updates_parameters() -> None:
    genome = build_genome()
    base_graph = build_body_graph(genome)
    base_head_size = tuple(base_graph.get_node("head").module.size)

    mutated = mutate_adjust_size(genome, target_gene="head", rng=random.Random(2))

    new_size = mutated.genes["head"].parameters["size"]
    assert new_size != base_head_size
    assert len(new_size) == 3


def test_mutate_adjust_material_respects_attachment_limits() -> None:
    genome = build_genome()

    mutated = mutate_adjust_material(genome, target_gene="head", rng=random.Random(3))

    material = mutated.genes["head"].parameters["material"]
    assert material in ("bio-alloy", "chitin")
    assert material != build_body_graph(genome).get_node("head").module.material
    build_body_graph(mutated)  # Should not raise

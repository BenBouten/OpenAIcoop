"""DNA mutation helpers that operate on :class:`Genome` blueprints."""

from __future__ import annotations

import random
from typing import Dict, List, Mapping, Optional, Tuple

from ..body.attachment import AttachmentPoint
from .factory import DEFAULT_MODULE_FACTORIES, build_body_graph
from .genes import Genome, ModuleGene

__all__ = [
    "MutationError",
    "mutate_genome",
    "mutate_add_module",
    "mutate_remove_module",
    "mutate_adjust_size",
    "mutate_adjust_material",
]


class MutationError(RuntimeError):
    """Raised when a mutation cannot be applied or violates constraints."""


_MUTATION_TEMPLATES = {
    key: DEFAULT_MODULE_FACTORIES[key]
    for key in ("head", "limb", "propulsion", "sensor", "tentacle", "bell_core", "eye", "mouth")
}

_MATERIAL_LIBRARY: Dict[str, Tuple[str, ...]] = {
    "core": ("bio-alloy", "chitin"),
    "bell_core": ("mesoglea", "chitin"),
    "head": ("bio-alloy", "ceramic"),
    "limb": ("flex-polymer", "titanium"),
    "tentacle": ("mesoglea", "flex-polymer"),
    "propulsion": ("titanium", "ceramic"),
    "sensor": ("ceramic", "bio-alloy"),
    "eye": ("organic", "ceramic"),
    "mouth": ("chitin", "organic"),
}


def mutate_genome(genome: Genome, *, rng: Optional[random.Random] = None) -> Genome:
    """Apply a random mutation and return a new :class:`Genome`."""

    rng = rng or random
    operations = [
        mutate_add_module,
        mutate_remove_module,
        mutate_adjust_size,
        mutate_adjust_material,
    ]
    rng.shuffle(operations)
    for operation in operations:
        try:
            return operation(genome, rng=rng)
        except MutationError:
            continue
    raise MutationError("Geen enkele mutatie kon worden toegepast")


def mutate_add_module(genome: Genome, *, rng: Optional[random.Random] = None) -> Genome:
    """Attach a new module to an available attachment point."""

    rng = rng or random
    graph = build_body_graph(genome)
    slot_candidates = _available_slots(graph)
    if not slot_candidates:
        raise MutationError("Er zijn geen vrije bevestigingspunten")

    slot_candidates.sort(key=lambda item: (item[0] != "core", item[1]))
    parent_id, slot_name, attachment = slot_candidates[0]
    module_type = _select_module_for_attachment(attachment, rng=rng)
    if module_type is None:
        raise MutationError("Geen moduletype beschikbaar voor deze aansluiting")

    new_gene_id = _next_gene_id(genome.genes, module_type)
    new_gene = ModuleGene(
        gene_id=new_gene_id,
        module_type=module_type,
        parameters={},
        parent=parent_id,
        slot=slot_name,
    )

    genes = dict(genome.genes)
    genes[new_gene.gene_id] = new_gene
    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated


def mutate_remove_module(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Genome:
    """Remove a module (and its sub-tree) from the genome."""

    rng = rng or random
    removable = [gene_id for gene_id, gene in genome.genes.items() if gene.parent]
    if not removable:
        raise MutationError("Het genoom bevat geen verwijderbare modules")

    if target_gene is not None:
        if target_gene not in removable:
            raise MutationError(f"Module '{target_gene}' kan niet verwijderd worden")
        victim = target_gene
    else:
        victim = rng.choice(removable)

    to_remove = _collect_subtree(genome.genes, victim)
    genes = {
        gene_id: gene for gene_id, gene in genome.genes.items() if gene_id not in to_remove
    }
    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated


def mutate_adjust_size(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Genome:
    """Slightly tweak the size vector of a module."""

    rng = rng or random
    graph = build_body_graph(genome)
    gene_id = _select_gene_id(genome, rng=rng, target_gene=target_gene)
    node = graph.get_node(gene_id)

    current_size = tuple(node.module.size)
    axis = rng.randrange(3)
    delta = rng.uniform(-0.2, 0.2)
    mutated_size = list(current_size)
    mutated_size[axis] = max(0.2, round(mutated_size[axis] * (1.0 + delta), 3))

    genes = dict(genome.genes)
    gene = genes[gene_id]
    parameters = dict(gene.parameters)
    parameters["size"] = tuple(mutated_size)
    genes[gene_id] = ModuleGene(
        gene_id=gene.gene_id,
        module_type=gene.module_type,
        parameters=parameters,
        parent=gene.parent,
        slot=gene.slot,
    )

    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated


def mutate_adjust_material(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Genome:
    """Change the material of a module while respecting attachment limits."""

    rng = rng or random
    graph = build_body_graph(genome)
    gene_id = _select_gene_id(genome, rng=rng, target_gene=target_gene)
    gene = genome.genes[gene_id]
    node = graph.get_node(gene_id)

    allowed = _allowed_materials(graph, gene)
    current_material = getattr(node.module, "material", None)
    candidate_pool = [mat for mat in allowed if mat != current_material]
    if not candidate_pool:
        raise MutationError("Geen alternatieve materialen beschikbaar")
    new_material = rng.choice(candidate_pool)

    parameters = dict(gene.parameters)
    parameters["material"] = new_material
    genes = dict(genome.genes)
    genes[gene_id] = ModuleGene(
        gene_id=gene.gene_id,
        module_type=gene.module_type,
        parameters=parameters,
        parent=gene.parent,
        slot=gene.slot,
    )

    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated


def _allowed_materials(graph, gene: ModuleGene) -> Tuple[str, ...]:
    if gene.parent and gene.slot:
        parent_node = graph.get_node(gene.parent)
        point = parent_node.module.get_attachment_point(gene.slot)
        if point.allowed_materials:
            return tuple(point.allowed_materials)

    module_type = graph.get_node(gene.gene_id).module.module_type
    return _MATERIAL_LIBRARY.get(module_type, tuple())


def _select_gene_id(
    genome: Genome,
    *,
    rng: random.Random,
    target_gene: Optional[str],
) -> str:
    if target_gene is not None:
        if target_gene not in genome.genes:
            raise MutationError(f"Onbekend module-id '{target_gene}'")
        return target_gene
    return rng.choice(list(genome.genes))


def _available_slots(graph) -> List[Tuple[str, str, AttachmentPoint]]:
    slots: List[Tuple[str, str, AttachmentPoint]] = []
    for node_id, node in graph.nodes.items():
        used = set(node.children.values())
        for slot_name, point in node.module.attachment_points.items():
            if slot_name in used:
                continue
            slots.append((node_id, slot_name, point))
    return slots


def _select_module_for_attachment(
    attachment: AttachmentPoint, *, rng: random.Random
) -> Optional[str]:
    candidates: List[str] = []
    weights: List[float] = []
    
    # Define base weights for module types to control rarity
    # This satisfies the requirement: "mutate other modules ... to a lower chance"
    # Common modules have high weight, specialized ones have low weight.
    base_weights = {
        "limb": 30.0,
        "sensor": 30.0,
        "propulsion": 20.0,
        "head": 2.0,
        "tentacle": 5.0,   # Rare
        "bell_core": 1.0,  # Very rare
        "eye": 15.0,
        "mouth": 10.0,
    }
    
    for module_type, factory in _MUTATION_TEMPLATES.items():
        probe = factory("probe", {})
        if attachment.allows(probe):
            candidates.append(module_type)
            weights.append(base_weights.get(module_type, 10.0))
            
    if not candidates:
        return None
        
    return rng.choices(candidates, weights=weights, k=1)[0]


def _collect_subtree(genes: Mapping[str, ModuleGene], start: str) -> set[str]:
    removal: set[str] = set()
    stack = [start]
    while stack:
        gene_id = stack.pop()
        removal.add(gene_id)
        for child_id, gene in genes.items():
            if gene.parent == gene_id and child_id not in removal:
                stack.append(child_id)
    return removal


def _next_gene_id(genes: Mapping[str, ModuleGene], prefix: str) -> str:
    candidate = prefix
    counter = 1
    existing = set(genes)
    while candidate in existing:
        counter += 1
        candidate = f"{prefix}_{counter}"
    return candidate


def _validate_genome(genome: Genome) -> None:
    try:
        build_body_graph(genome)
    except ValueError as exc:  # pragma: no cover - re-raised for clarity
        raise MutationError(str(exc)) from exc

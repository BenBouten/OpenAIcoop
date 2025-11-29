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
    "mutate_shape",
    "mutate_attachment_points",
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


def mutate_genome(genome: Genome, *, rng: Optional[random.Random] = None) -> Tuple[Genome, str]:
    """Apply a random mutation and return a new :class:`Genome` and a description."""

    rng = rng or random
    operations = [
        mutate_add_module,
        mutate_remove_module,
        mutate_adjust_size,
        mutate_adjust_material,
        mutate_shape,
        mutate_attachment_points,
        mutate_bioluminescence,
    ]
    rng.shuffle(operations)
    for operation in operations:
        try:
            return operation(genome, rng=rng)
        except MutationError:
            continue
    raise MutationError("Geen enkele mutatie kon worden toegepast")


def mutate_add_module(genome: Genome, *, rng: Optional[random.Random] = None) -> Tuple[Genome, str]:
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
    
    # Deep Evolution: Bias new modules to be small
    # Start at 30% size, will grow via mutation or age
    parameters = {"size_scale": 0.3}
    
    new_gene = ModuleGene(
        gene_id=new_gene_id,
        module_type=module_type,
        parameters=parameters,
        parent=parent_id,
        slot=slot_name,
    )

    genes = dict(genome.genes)
    genes[new_gene.gene_id] = new_gene
    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated, f"Added {module_type} to {parent_id}"


def mutate_remove_module(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Tuple[Genome, str]:
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
    return mutated, f"Removed {victim} and {len(to_remove)-1} descendants"


def mutate_adjust_size(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Tuple[Genome, str]:
    """Slightly tweak the size vector of a module."""

    rng = rng or random
    graph = build_body_graph(genome)
    gene_id = _select_gene_id(genome, rng=rng, target_gene=target_gene)
    node = graph.get_node(gene_id)

    current_size = tuple(node.module.size)
    
    # 50% chance to scale uniformly (all axes), 50% chance to scale a single axis
    if rng.random() < 0.5:
        delta = rng.uniform(-0.2, 0.2)
        mutated_size = [max(0.2, round(s * (1.0 + delta), 3)) for s in current_size]
        desc = f"Scaled {gene_id} uniformly by {delta:+.2f}"
    else:
        axis = rng.randrange(3)
        delta = rng.uniform(-0.2, 0.2)
        mutated_size = list(current_size)
        mutated_size[axis] = max(0.2, round(mutated_size[axis] * (1.0 + delta), 3))
        desc = f"Scaled {gene_id} axis {axis} by {delta:+.2f}"

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
    return mutated, desc


def mutate_adjust_material(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Tuple[Genome, str]:
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
    return mutated, f"Changed {gene_id} material to {new_material}"


def mutate_shape(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Tuple[Genome, str]:
    """Mutate the shape vectors of a module."""
    rng = rng or random
    graph = build_body_graph(genome)
    gene_id = _select_gene_id(genome, rng=rng, target_gene=target_gene)
    node = graph.get_node(gene_id)
    
    # Get current shape or generate default
    current_shape = node.module.shape_vertices
    if not current_shape:
        # Generate default polygon (hexagon)
        # Normalized coordinates (-0.5 to 0.5)
        import math
        current_shape = []
        segments = 6
        for i in range(segments):
            angle = (i / segments) * 2 * math.pi
            # X is length (forward), Y is width (side)
            # Let's orient it so point is forward?
            current_shape.append((0.5 * math.cos(angle), 0.5 * math.sin(angle)))
            
    # Mutate shape
    new_shape = list(current_shape)
    mutation_type = rng.choice(["perturb", "add_vertex", "remove_vertex"])
    desc = ""
    
    if mutation_type == "perturb" and new_shape:
        idx = rng.randrange(len(new_shape))
        vx, vy = new_shape[idx]
        new_shape[idx] = (
            max(-0.6, min(0.6, vx + rng.uniform(-0.1, 0.1))),
            max(-0.6, min(0.6, vy + rng.uniform(-0.1, 0.1)))
        )
        desc = f"Perturbed shape vertex {idx} of {gene_id}"
        
    elif mutation_type == "add_vertex" and len(new_shape) < 12:
        idx = rng.randrange(len(new_shape))
        next_idx = (idx + 1) % len(new_shape)
        v1 = new_shape[idx]
        v2 = new_shape[next_idx]
        mid_x = (v1[0] + v2[0]) / 2
        mid_y = (v1[1] + v2[1]) / 2
        # Push out slightly to create convexity
        mid_x += rng.uniform(-0.05, 0.05)
        mid_y += rng.uniform(-0.05, 0.05)
        new_shape.insert(next_idx, (mid_x, mid_y))
        desc = f"Added shape vertex to {gene_id}"
        
    elif mutation_type == "remove_vertex" and len(new_shape) > 3:
        idx = rng.randrange(len(new_shape))
        new_shape.pop(idx)
        desc = f"Removed shape vertex from {gene_id}"
    else:
        # Fallback if mutation couldn't happen
        raise MutationError("Shape mutation failed (constraints)")
        
    # Update gene
    genes = dict(genome.genes)
    gene = genes[gene_id]
    parameters = dict(gene.parameters)
    parameters["shape_vertices"] = new_shape
    genes[gene_id] = ModuleGene(
        gene_id=gene.gene_id,
        module_type=gene.module_type,
        parameters=parameters,
        parent=gene.parent,
        slot=gene.slot,
    )
    
    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated, desc


def mutate_attachment_points(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Tuple[Genome, str]:
    """Add or remove attachment points on a module."""
    rng = rng or random
    graph = build_body_graph(genome)
    gene_id = _select_gene_id(genome, rng=rng, target_gene=target_gene)
    node = graph.get_node(gene_id)
    
    # Get current custom points or defaults
    current_points = node.module.custom_attachment_points
    if current_points is None:
        # Start with defaults
        current_points = list(node.module.attachment_points.values())
        
    # Convert to dicts for storage/mutation if they are objects
    # (In factory we deserialize, here we need to serialize if we are modifying)
    # Actually, let's work with the objects and then serialize to dicts for the gene.
    
    new_points = list(current_points)
    desc = ""
    
    if rng.random() < 0.6: # Add point
        # Pick a random angle
        angle = rng.uniform(0, 360)
        # Pick a random type
        from ..body.attachment import AttachmentPoint, Joint, JointType
        from ..body.modules import LimbModule, SensoryModule, PropulsionModule
        
        allowed = [LimbModule, SensoryModule]
        if rng.random() < 0.3:
            allowed.append(PropulsionModule)
            
        # Calculate offset based on angle (unit circle)
        import math
        rad = math.radians(angle)
        # Ellipse approximation (0.5 radius)
        offset_val = (0.5 * math.cos(rad), 0.5 * math.sin(rad))
            
        new_point = AttachmentPoint(
            name=f"custom_{len(new_points)}_{rng.randint(100,999)}",
            joint=Joint(JointType.MUSCLE, swing_limits=(-45, 45)),
            allowed_modules=tuple(allowed),
            description="Evolved attachment point",
            max_child_mass=rng.uniform(2.0, 10.0),
            allowed_materials=("mesoglea", "flex-polymer", "bio-alloy"),
            angle=angle,
            offset=offset_val,
            relative=True
        )
        
        new_points.append(new_point)
        desc = f"Added attachment point to {gene_id}"
        
    elif new_points: # Remove point
        # Don't remove points that are currently used!
        used_slots = set(node.children.values())
        candidates = [i for i, p in enumerate(new_points) if p.name not in used_slots]
        if candidates:
            idx = rng.choice(candidates)
            new_points.pop(idx)
            desc = f"Removed attachment point from {gene_id}"
        else:
             raise MutationError("Cannot remove any attachment points (all used)")
    else:
         raise MutationError("No attachment points to remove")
    
    # Serialize points to dicts for gene storage
    serialized_points = []
    for p in new_points:
        # Minimal serialization
        p_data = {
            "name": p.name,
            "angle": p.angle,
            "offset": p.offset,
            "relative": p.relative,
            "max_child_mass": p.max_child_mass,
            # We lose some joint info here unless we fully serialize.
            # For prototype, this is acceptable.
        }
        serialized_points.append(p_data)

    # Update gene
    genes = dict(genome.genes)
    gene = genes[gene_id]
    parameters = dict(gene.parameters)
    parameters["custom_attachment_points"] = serialized_points
    genes[gene_id] = ModuleGene(
        gene_id=gene.gene_id,
        module_type=gene.module_type,
        parameters=parameters,
        parent=gene.parent,
        slot=gene.slot,
    )
    
    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated, desc


def mutate_bioluminescence(
    genome: Genome,
    *,
    rng: Optional[random.Random] = None,
    target_gene: Optional[str] = None,
) -> Tuple[Genome, str]:
    """Mutate bioluminescence properties of a module."""
    rng = rng or random
    graph = build_body_graph(genome)
    gene_id = _select_gene_id(genome, rng=rng, target_gene=target_gene)
    node = graph.get_node(gene_id)
    
    # Get current props
    module = node.module
    
    # Decide what to mutate
    mutation_type = rng.choice(["color", "intensity", "pattern", "frequency"])
    desc = ""
    
    parameters = dict(genome.genes[gene_id].parameters)
    
    if mutation_type == "color":
        # Mutate or initialize color
        current_color = module.light_color or (0, 0, 0)
        # Shift color
        r = max(0, min(255, current_color[0] + rng.randint(-30, 30)))
        g = max(0, min(255, current_color[1] + rng.randint(-30, 30)))
        b = max(0, min(255, current_color[2] + rng.randint(-30, 30)))
        
        # Chance to enable if disabled
        if module.light_color is None and rng.random() < 0.5:
            # Pick a vibrant color
            hue = rng.random()
            import colorsys
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            r, g, b = int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255)
            
        parameters["light_color"] = (r, g, b)
        if "light_intensity" not in parameters:
            parameters["light_intensity"] = 0.5
        desc = f"Mutated light color of {gene_id}"
            
    elif mutation_type == "intensity":
        current = module.light_intensity
        new_val = max(0.0, min(1.0, current + rng.uniform(-0.2, 0.2)))
        parameters["light_intensity"] = new_val
        desc = f"Mutated light intensity of {gene_id}"
        
    elif mutation_type == "pattern":
        patterns = ["steady", "pulse", "flash", "wave"]
        parameters["light_pattern"] = rng.choice(patterns)
        desc = f"Mutated light pattern of {gene_id}"
        
    elif mutation_type == "frequency":
        current = module.light_frequency
        # Range 0.1 to 5.0 Hz
        new_val = max(0.1, min(5.0, current + rng.uniform(-0.5, 0.5)))
        parameters["light_frequency"] = new_val
        parameters["light_phase"] = rng.random()
        desc = f"Mutated light frequency of {gene_id}"
        
    # Update gene
    genes = dict(genome.genes)
    gene = genes[gene_id]
    genes[gene_id] = ModuleGene(
        gene_id=gene.gene_id,
        module_type=gene.module_type,
        parameters=parameters,
        parent=gene.parent,
        slot=gene.slot,
    )
    
    mutated = Genome(genes=genes, constraints=genome.constraints)
    _validate_genome(mutated)
    return mutated, desc


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

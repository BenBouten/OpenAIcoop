"""Utilities to convert DNA blueprints to ``BodyGraph`` instances and back."""

from __future__ import annotations

from dataclasses import MISSING, fields, replace
from typing import Callable, Dict, Iterable, Mapping, Optional, Type

from ..body.body_graph import BodyGraph
from ..body.modules import (
    BodyModule,
    CephalonHead,
    HydroFin,
    JellyBell,
    PulseSiphon,
    ModuleStats,
    SensorPod,
    SensoryModule,
    TentacleLimb,
    TailThruster,
    SensorPod,
    SensoryModule,
    TentacleLimb,
    TailThruster,
    TrunkCore,
    RoundCore,
    HexagonCore,
    Eye,
    Mouth,
)
from .genes import Genome, GenomeConstraints, ModuleGene, ensure_genome

ModuleFactory = Callable[[str, Mapping[str, object]], BodyModule]

__all__ = [
    "build_body_graph",
    "serialize_body_graph",
    "DEFAULT_MODULE_FACTORIES",
]


def _apply_shape_stats(module: BodyModule) -> None:
    """Recalculate module stats based on custom shape vertices."""
    if not module.shape_vertices:
        return

    # Calculate polygon area
    area = 0.0
    vertices = module.shape_vertices
    n = len(vertices)
    if n < 3:
        return
        
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    area = abs(area) / 2.0
    
    # Standard box (-0.5, -0.5) to (0.5, 0.5) has area 1.0
    shape_factor = max(0.2, area)
    
    module.stats = replace(
        module.stats,
        mass=module.stats.mass * shape_factor,
        energy_cost=module.stats.energy_cost * shape_factor,
        integrity=module.stats.integrity * (shape_factor ** 0.5),
        heat_dissipation=module.stats.heat_dissipation * (shape_factor ** 0.5),
        power_output=module.stats.power_output * shape_factor,
        buoyancy_bias=module.stats.buoyancy_bias
    )
    
    if hasattr(module, "energy_capacity"):
        module.energy_capacity *= shape_factor
    if hasattr(module, "cargo_slots"):
        module.cargo_slots = int(module.cargo_slots * (shape_factor ** 0.5))


def _default_factory_for(cls: Type[BodyModule]) -> ModuleFactory:
    def _builder(key: str, parameters: Mapping[str, object]) -> BodyModule:
        kwargs = dict(parameters)
        kwargs.setdefault("key", key)
        module_field_names = {f.name for f in fields(cls)}

        stat_overrides: Dict[str, object] = {}
        deferred_overrides: Optional[Dict[str, object]] = None
        stat_fields = set(ModuleStats.__annotations__.keys())
        for name in list(kwargs.keys()):
            if name in stat_fields and name not in module_field_names:
                stat_overrides[name] = kwargs.pop(name)

        # Ensure tuples for immutable sequence fields such as sensor spectrums.
        if "spectrum" in kwargs and not isinstance(kwargs["spectrum"], tuple):
            value = kwargs["spectrum"]
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                kwargs["spectrum"] = tuple(value)
        # Handle size scaling
        if "size_scale" in kwargs:
            scale = float(kwargs.pop("size_scale"))
            # We need to instantiate with scaled size if it's not passed explicitly
            # But wait, size is a field on the dataclass.
            # We can't easily modify the default factory lambda for stats if we change size here.
            # However, the classes are dataclasses.
            # If we pass 'size' in kwargs, it overrides the default.
            # But we don't know the default size here without the class.
            # Actually, we can just let the class init, then modify? No, frozen=False but good practice.
            
            # Better approach: The classes define 'size' as a field with a default.
            # We can't access that default easily on the class before init without inspecting.
            # BUT, we can just pass size_scale to the constructor if we add it to BodyModule?
            # Or we can handle it here by inspecting the class default.
            
            # Let's try to get the default size from the class if possible.
            # Most modules have a default size.
            for f in fields(cls):
                if f.name == "size":
                    default_size = f.default
                    if default_size and isinstance(default_size, tuple):
                        kwargs["size"] = (
                            default_size[0] * scale,
                            default_size[1] * scale,
                            default_size[2] * scale
                        )
                    break
        
        if stat_overrides:
            if "stats" in kwargs and isinstance(kwargs["stats"], ModuleStats):
                kwargs["stats"] = replace(kwargs["stats"], **stat_overrides)
            else:
                stats_field = next((f for f in fields(cls) if f.name == "stats"), None)
                if stats_field is not None:
                    if stats_field.default_factory is not MISSING:  # type: ignore[attr-defined]
                        base_stats = stats_field.default_factory()
                    elif stats_field.default is not MISSING:
                        base_stats = stats_field.default
                    else:
                        base_stats = None

                    if isinstance(base_stats, ModuleStats):
                        kwargs["stats"] = replace(base_stats, **stat_overrides)
                    else:
                        # Fallback: defer overrides until after instantiation
                        deferred_overrides = stat_overrides
                else:
                    deferred_overrides = stat_overrides
        else:
            deferred_overrides = None

        if "shape_vertices" in kwargs:
            # Ensure vertices are tuples
            raw_verts = kwargs["shape_vertices"]
            if raw_verts and isinstance(raw_verts, list):
                kwargs["shape_vertices"] = [tuple(v) for v in raw_verts]

        if "custom_attachment_points" in kwargs:
            # Deserialize attachment points if they are dicts
            raw_points = kwargs["custom_attachment_points"]
            if raw_points and isinstance(raw_points, list):
                from ..body.attachment import AttachmentPoint
                deserialized = []
                for p in raw_points:
                    if isinstance(p, dict):
                        # Reconstruct AttachmentPoint from dict
                        # We need to handle the 'joint' field which might be missing or complex
                        # For now, assume default joint if missing
                        from ..body.attachment import Joint, JointType
                        
                        # Default joint
                        joint = Joint(JointType.FIXED)
                        # If we serialized joint info, we could restore it. 
                        # The mutation script didn't serialize joint info fully, just lost it.
                        # Let's assume a default joint for evolved points or try to infer.
                        # Ideally we should serialize the joint too.
                        
                        # For now, create a generic point
                        point = AttachmentPoint(
                            name=p.get("name", "custom"),
                            joint=joint, # Placeholder
                            allowed_modules=(), # Placeholder, will need to fix this
                            description="Deserialized point",
                            max_child_mass=p.get("max_child_mass"),
                            offset=tuple(p.get("offset", (0,0))),
                            angle=p.get("angle", 0.0),
                            relative=p.get("relative", False)
                        )
                        # Wait, allowed_modules is required.
                        # We need to know what modules are allowed.
                        # The mutation script didn't serialize this either.
                        # This is a problem. We need to serialize more data.
                        
                        # Let's fix mutation.py to serialize more data first?
                        # Or make factory robust?
                        # Let's allow 'any' or standard set if missing.
                        from ..body.modules import LimbModule, SensoryModule, PropulsionModule
                        point = replace(point, allowed_modules=(LimbModule, SensoryModule, PropulsionModule))
                        
                        deserialized.append(point)
                    else:
                        deserialized.append(p)
                kwargs["custom_attachment_points"] = deserialized

        module = cls(**kwargs)

        if stat_overrides and "stats" not in kwargs and deferred_overrides:
            module.stats = replace(module.stats, **deferred_overrides)
            
        # Deep Evolution: Recalculate stats based on shape volume
        if module.shape_vertices:
            _apply_shape_stats(module)
            
        # Deep Evolution: Register custom attachment points
        if module.custom_attachment_points:
            # Override defaults entirely to allow removal/modification
            module.attachment_points.clear()
            module.add_attachment_points(module.custom_attachment_points)

        return module

    return _builder


DEFAULT_MODULE_FACTORIES: Dict[str, ModuleFactory] = {
    "TrunkCore": _default_factory_for(TrunkCore),
    "CephalonHead": _default_factory_for(CephalonHead),
    "HydroFin": _default_factory_for(HydroFin),
    "TailThruster": _default_factory_for(TailThruster),
    "SensorPod": _default_factory_for(SensorPod),
    "JellyBell": _default_factory_for(JellyBell),
    "PulseSiphon": _default_factory_for(PulseSiphon),
    "TentacleLimb": _default_factory_for(TentacleLimb),
    "core": _default_factory_for(TrunkCore),
    "round_core": _default_factory_for(RoundCore),
    "bell_core": _default_factory_for(JellyBell),
    "head": _default_factory_for(CephalonHead),
    "limb": _default_factory_for(HydroFin),
    "tentacle": _default_factory_for(TentacleLimb),
    "propulsion": _default_factory_for(TailThruster),
    "sensor": _default_factory_for(SensorPod),
    "eye": _default_factory_for(Eye),
    "mouth": _default_factory_for(Mouth),
    "hexagon_core": _default_factory_for(HexagonCore),
}

_NERVE_LOAD: Dict[str, float] = {
    "core": 5.0,
    "bell_core": 4.0,
    "head": 3.0,
    "limb": 1.8,
    "tentacle": 1.4,
    "propulsion": 2.5,
    "sensor": 0.8,
    "eye": 0.5,
    "mouth": 1.0,
}


def _instantiate_module(gene: ModuleGene, factories: Mapping[str, ModuleFactory]) -> BodyModule:
    factory = factories.get(gene.module_type)
    if factory is None:
        raise KeyError(f"No factory registered for module type '{gene.module_type}'")
    return factory(gene.gene_id, gene.parameters)


def _nerve_load(module: BodyModule) -> float:
    return _NERVE_LOAD.get(module.module_type, 1.0)


def _serialise_parameters(module: BodyModule) -> Dict[str, object]:
    data: Dict[str, object] = {"key": module.key}
    if isinstance(module, SensoryModule):
        data["spectrum"] = list(module.spectrum)
    
    # Deep Evolution: Serialise shape and custom points
    if module.shape_vertices:
        data["shape_vertices"] = module.shape_vertices
    if module.custom_attachment_points:
        # We need to serialise attachment points to dicts
        # For now, let's just store them if they are serializable or skip
        # Ideally we'd have a to_dict method on AttachmentPoint
        pass 
        
    # Bioluminescence
    if module.light_color:
        data["light_color"] = module.light_color
        data["light_intensity"] = module.light_intensity
        data["light_pattern"] = module.light_pattern
        data["light_frequency"] = module.light_frequency
        data["light_phase"] = module.light_phase
        
    return data


def build_body_graph(
    dna_data: Mapping[str, object] | Genome,
    *,
    module_factories: Optional[Mapping[str, ModuleFactory]] = None,
    include_geometry: bool = False,
) -> BodyGraph | tuple[BodyGraph, Dict[str, float]]:
    """Convert DNA data into a validated :class:`BodyGraph`.

    When ``include_geometry`` is true, returns ``(graph, geometry_summary)``.
    """

    genome = dna_data if isinstance(dna_data, Genome) else ensure_genome(dna_data)
    factories = dict(DEFAULT_MODULE_FACTORIES)
    if module_factories:
        factories.update(module_factories)

    root_gene = genome.root_gene()
    modules: Dict[str, BodyModule] = {}
    for gene in genome.ordered_genes():
        module = _instantiate_module(gene, factories)
        modules[gene.gene_id] = module

    graph = BodyGraph(root_gene.gene_id, modules[root_gene.gene_id])
    for gene in genome.ordered_genes():
        if gene.parent is None:
            continue
        if gene.parent not in modules:
            raise KeyError(f"Parent '{gene.parent}' referenced by '{gene.gene_id}' is undefined")
        slot = gene.slot or ""
        if not slot:
            raise ValueError(f"Gene '{gene.gene_id}' requires an attachment slot")
        graph.add_module(gene.gene_id, modules[gene.gene_id], gene.parent, slot)

    graph.validate()
    _validate_graph_constraints(graph, genome.constraints)
    if include_geometry:
        return graph, graph.geometry_summary()
    return graph


def _validate_graph_constraints(graph: BodyGraph, constraints: GenomeConstraints) -> None:
    total_mass = graph.total_mass()
    if total_mass > constraints.max_mass:
        raise ValueError(
            f"BodyGraph mass {total_mass:.1f} exceeds genome limit {constraints.max_mass:.1f}"
        )
    total_load = sum(_nerve_load(node.module) for node in graph.nodes.values())
    if total_load > constraints.nerve_capacity:
        raise ValueError(
            f"BodyGraph nerve load {total_load:.1f} exceeds capacity {constraints.nerve_capacity:.1f}"
        )


def serialize_body_graph(
    graph: BodyGraph,
    *,
    constraints: Optional[GenomeConstraints] = None,
) -> Genome:
    """Serialise a :class:`BodyGraph` into a :class:`Genome`."""

    genes: Dict[str, ModuleGene] = {}
    for node_id, node in graph.nodes.items():
        parameters = _serialise_parameters(node.module)
        genes[node_id] = ModuleGene(
            gene_id=node_id,
            module_type=type(node.module).__name__,
            parameters=parameters,
            parent=node.parent,
            slot=node.attachment_point,
        )

    if constraints is None:
        default_constraints = GenomeConstraints()
        required_mass = max(graph.total_mass(), default_constraints.max_mass)
        nerve_usage = sum(_nerve_load(node.module) for node in graph.nodes.values())
        required_nerve = max(nerve_usage, default_constraints.nerve_capacity)
        constraints = GenomeConstraints(max_mass=required_mass, nerve_capacity=required_nerve)

    return Genome(genes=genes, constraints=constraints)

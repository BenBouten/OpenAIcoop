"""Utilities to convert DNA blueprints to ``BodyGraph`` instances and back."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, Mapping, Optional, Type

from ..body.body_graph import BodyGraph
from ..body.modules import (
    BodyModule,
    CephalonHead,
    HydroFin,
    JellyBell,
    PulseSiphon,
    SensorPod,
    SensoryModule,
    TentacleLimb,
    TailThruster,
    TrunkCore,
)
from .genes import Genome, GenomeConstraints, ModuleGene, ensure_genome

ModuleFactory = Callable[[str, Mapping[str, object]], BodyModule]

__all__ = [
    "build_body_graph",
    "serialize_body_graph",
    "DEFAULT_MODULE_FACTORIES",
]


def _default_factory_for(cls: Type[BodyModule]) -> ModuleFactory:
    def _builder(key: str, parameters: Mapping[str, object]) -> BodyModule:
        kwargs = dict(parameters)
        kwargs.setdefault("key", key)
        # Ensure tuples for immutable sequence fields such as sensor spectrums.
        if "spectrum" in kwargs and not isinstance(kwargs["spectrum"], tuple):
            value = kwargs["spectrum"]
            if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
                kwargs["spectrum"] = tuple(value)
        return cls(**kwargs)

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
    "bell_core": _default_factory_for(JellyBell),
    "head": _default_factory_for(CephalonHead),
    "limb": _default_factory_for(HydroFin),
    "tentacle": _default_factory_for(TentacleLimb),
    "propulsion": _default_factory_for(TailThruster),
    "sensor": _default_factory_for(SensorPod),
}

_NERVE_LOAD: Dict[str, float] = {
    "core": 5.0,
    "bell_core": 4.0,
    "head": 3.0,
    "limb": 1.8,
    "tentacle": 1.4,
    "propulsion": 2.5,
    "sensor": 0.8,
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

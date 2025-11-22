"""Data structures for the Creature Creator templates and drafts."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from ..body.body_graph import BodyGraph
from ..body.modules import BodyModule, ModuleStats, catalogue_default_modules
from ..body.attachment import AttachmentPoint

_ROOT_NODE_ID = "core"


def _default_root_node() -> "ModuleDraft":
    return ModuleDraft(node_id=_ROOT_NODE_ID, module_type="core", parent_id=None, attachment_point=None)


@dataclass
class ModuleDraft:
    """Editable module data living inside the creator."""

    node_id: str
    module_type: str
    parent_id: Optional[str]
    attachment_point: Optional[str]
    parameters: Dict[str, object] = field(default_factory=dict)

    def clone(self) -> "ModuleDraft":
        return ModuleDraft(
            node_id=self.node_id,
            module_type=self.module_type,
            parent_id=self.parent_id,
            attachment_point=self.attachment_point,
            parameters=dict(self.parameters),
        )


@dataclass
class CreatureTemplate:
    """Serialisable representation of a creature design."""

    name: str
    nodes: List[ModuleDraft]
    intended_layer: Optional[str] = None
    notes: str = ""
    version: str = "1.0"

    @classmethod
    def blank(cls, name: str = "untitled") -> "CreatureTemplate":
        return cls(name=name, nodes=[_default_root_node()])

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "nodes": [
                {
                    "id": node.node_id,
                    "module_type": node.module_type,
                    "parent_id": node.parent_id,
                    "attachment_point": node.attachment_point,
                    "parameters": dict(node.parameters),
                }
                for node in self.nodes
            ],
            "intended_layer": self.intended_layer,
            "notes": self.notes,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "CreatureTemplate":
        nodes = [
            ModuleDraft(
                node_id=str(entry.get("id")),
                module_type=str(entry.get("module_type")),
                parent_id=entry.get("parent_id"),
                attachment_point=entry.get("attachment_point"),
                parameters=dict(entry.get("parameters", {})),
            )
            for entry in data.get("nodes", [])
        ]
        if not nodes:
            nodes = [_default_root_node()]
        return cls(
            name=str(data.get("name", "untitled")),
            nodes=nodes,
            intended_layer=data.get("intended_layer"),
            notes=str(data.get("notes", "")),
            version=str(data.get("version", "1.0")),
        )

    def root_node(self) -> ModuleDraft:
        roots = [node for node in self.nodes if node.parent_id is None]
        if len(roots) != 1:
            raise ValueError("Template must contain exactly one root module")
        return roots[0]

    def node_map(self) -> Dict[str, ModuleDraft]:
        mapping: Dict[str, ModuleDraft] = {}
        for node in self.nodes:
            if node.node_id in mapping:
                raise ValueError(f"Duplicate node id '{node.node_id}' detected")
            mapping[node.node_id] = node
        return mapping


@dataclass
class CreatureDraft:
    """Mutable draft that powers the creator overlay."""

    template: CreatureTemplate
    modules_catalogue: Dict[str, BodyModule] = field(default_factory=catalogue_default_modules)

    def __post_init__(self) -> None:
        if not self.template.nodes:
            self.template.nodes.append(_default_root_node())

    @classmethod
    def new(cls, name: str = "untitled") -> "CreatureDraft":
        return cls(CreatureTemplate.blank(name))

    def add_module(
        self,
        node_id: str,
        module_type: str,
        parent_id: str,
        attachment_point: str,
        *,
        parameters: Optional[Dict[str, object]] = None,
    ) -> ModuleDraft:
        nodes = self.template.node_map()
        if node_id in nodes:
            raise ValueError(f"Module id '{node_id}' already exists")
        if parent_id not in nodes:
            raise KeyError(f"Parent '{parent_id}' does not exist")
        draft = ModuleDraft(
            node_id=node_id,
            module_type=module_type,
            parent_id=parent_id,
            attachment_point=attachment_point,
            parameters=dict(parameters or {}),
        )
        self.template.nodes.append(draft)
        return draft

    def remove_module(self, node_id: str) -> None:
        root = self.template.root_node().node_id
        if node_id == root:
            raise ValueError("Cannot remove root module")
        to_remove = {node_id}
        changed = True
        while changed:
            changed = False
            for node in list(self.template.nodes):
                if node.parent_id in to_remove and node.node_id not in to_remove:
                    to_remove.add(node.node_id)
                    changed = True
        before = len(self.template.nodes)
        self.template.nodes = [node for node in self.template.nodes if node.node_id not in to_remove]
        if len(self.template.nodes) == before:
            raise KeyError(f"Module '{node_id}' not found")

    def update_module(self, node_id: str, *, parameters: Optional[Dict[str, object]] = None) -> ModuleDraft:
        nodes = self.template.node_map()
        if node_id not in nodes:
            raise KeyError(f"Module '{node_id}' not found")
        target = nodes[node_id]
        if parameters is not None:
            target.parameters = dict(parameters)
        return target

    def attach_module(self, module_type: str, parent_id: str) -> ModuleDraft:
        slots = self.available_attachment_points(parent_id, module_type)
        if not slots:
            raise ValueError(f"Geen beschikbare sloten op '{parent_id}' voor type '{module_type}'")
        node_id = self.generate_node_id(module_type)
        return self.add_module(node_id, module_type, parent_id, slots[0])

    def iter_modules(self) -> Iterable[ModuleDraft]:
        return tuple(node.clone() for node in self.template.nodes)

    def build_graph(self) -> BodyGraph:
        self._validate()
        node_lookup = self.template.node_map()
        root_id = self.template.root_node().node_id
        modules = {node_id: self._instantiate_module(node) for node_id, node in node_lookup.items()}
        graph = BodyGraph(root_id, modules[root_id])
        order = self._topological_order(node_lookup)
        for node_id in order:
            node = node_lookup[node_id]
            if node.parent_id is None:
                continue
            if not node.attachment_point:
                raise ValueError(f"Module '{node_id}' is missing an attachment point")
            graph.add_module(node_id, modules[node_id], node.parent_id, node.attachment_point)
        graph.validate()
        return graph

    def generate_node_id(self, base: str) -> str:
        nodes = self.template.node_map()
        candidate = base
        suffix = 2
        while candidate in nodes:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def available_attachment_points(self, parent_id: str, module_type: str) -> Tuple[str, ...]:
        nodes = self.template.node_map()
        if parent_id not in nodes:
            raise KeyError(f"Parent '{parent_id}' not found")
        graph = self.build_graph()
        parent_node = graph.get_node(parent_id)
        occupied = set(parent_node.children.values())
        parent_module = parent_node.module
        base_module = self.modules_catalogue.get(module_type)
        if base_module is None:
            raise KeyError(f"Module type '{module_type}' is not available")
        candidate = copy.deepcopy(base_module)
        options: List[str] = []
        for point_name, attachment in parent_module.attachment_points.items():
            if point_name in occupied:
                continue
            if attachment.allows(candidate):
                options.append(point_name)
        return tuple(options)

    def attachment_points(self, node_id: str) -> Tuple[AttachmentPoint, ...]:
        graph = self.build_graph()
        node = graph.get_node(node_id)
        return tuple(node.module.attachment_points.values())

    def get_module(self, node_id: str) -> ModuleDraft:
        nodes = self.template.node_map()
        if node_id not in nodes:
            raise KeyError(f"Module '{node_id}' not found")
        return nodes[node_id]

    def effective_module(self, node_id: str) -> BodyModule:
        node = self.get_module(node_id)
        return self._instantiate_module(node)

    def adjust_stat_override(self, node_id: str, stat_name: str, delta: float) -> float:
        node = self.get_module(node_id)
        base_module = self.modules_catalogue.get(node.module_type)
        if not base_module:
            raise KeyError(f"Module type '{node.module_type}' is onbekend")
        base_value = getattr(base_module.stats, stat_name)
        overrides = dict(node.parameters.get("stats", {}))
        current = overrides.get(stat_name, base_value)
        new_value = max(0.0, current + delta)
        overrides[stat_name] = new_value
        node.parameters = dict(node.parameters)
        node.parameters["stats"] = overrides
        return new_value

    def reset_overrides(self, node_id: str) -> None:
        node = self.get_module(node_id)
        node.parameters = {k: v for k, v in node.parameters.items() if k != "stats"}

    def reparent(self, node_id: str, parent_id: str, attachment_point: str) -> None:
        if node_id == self.template.root_node().node_id:
            raise ValueError("Kerngedeelte kan niet worden verplaatst")
        nodes = self.template.node_map()
        if node_id not in nodes or parent_id not in nodes:
            raise KeyError("Onbekende module referentie")
        node = nodes[node_id]
        node.parent_id = parent_id
        node.attachment_point = attachment_point

    def add_module_to_template(
        self, module_type: str, parent_id: str, slot: str
    ) -> ModuleInstance:
        """Convenience wrapper to append a module instance to a draft template."""

        node_id = self.generate_node_id(module_type)
        module = ModuleDraft(module_type=module_type)
        instance = ModuleInstance(
            node_id=node_id,
            parent_id=parent_id,
            module_type=module_type,
            attachment_slot=slot,
        )
        self.template.nodes.append(instance)
        self.recalculate_graph()
        return instance

    def add_floating_module(
        self, module_type: str, *, parameters: Optional[Dict[str, object]] = None
    ) -> ModuleDraft:
        node_id = self.generate_node_id(module_type)
        module = ModuleDraft(
            node_id=node_id,
            parent_id=None,
            module_type=module_type,
            attachment_point=None,
            parameters=parameters or {},
        )
        self.template.nodes.append(module)
        return module

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        nodes = self.template.node_map()
        root_candidates = [node for node in nodes.values() if node.parent_id is None]
        if len(root_candidates) != 1:
            raise ValueError("Creature must have exactly one root module")
        for node in nodes.values():
            if node.parent_id is None:
                continue
            if node.parent_id not in nodes:
                raise KeyError(f"Parent '{node.parent_id}' not found for module '{node.node_id}'")
            if not node.attachment_point:
                raise ValueError(f"Module '{node.node_id}' missing attachment metadata")
            if node.parent_id == node.node_id:
                raise ValueError("Module cannot reference itself as parent")

    def _instantiate_module(self, node: ModuleDraft) -> BodyModule:
        base = self.modules_catalogue.get(node.module_type)
        if base is None:
            raise KeyError(f"Module type '{node.module_type}' is not available in the palette")
        module = copy.deepcopy(base)
        module.key = node.node_id
        self._apply_overrides(module, node.parameters)
        return module

    def _apply_overrides(self, module: BodyModule, overrides: Dict[str, object]) -> None:
        for key, value in overrides.items():
            if key == "stats" and isinstance(value, dict):
                module.stats = self._merge_stats(module.stats, value)
                continue
            if hasattr(module, key):
                setattr(module, key, value)

    @staticmethod
    def _merge_stats(stats: ModuleStats, overrides: Dict[str, object]) -> ModuleStats:
        data = {
            "mass": stats.mass,
            "energy_cost": stats.energy_cost,
            "integrity": stats.integrity,
            "heat_dissipation": stats.heat_dissipation,
            "power_output": stats.power_output,
            "buoyancy_bias": stats.buoyancy_bias,
        }
        for key, default in data.items():
            if key in overrides:
                data[key] = type(default)(overrides[key])  # preserve numeric type
        return ModuleStats(**data)

    def _topological_order(self, nodes: Dict[str, ModuleDraft]) -> List[str]:
        children: Dict[str, List[str]] = {}
        for node in nodes.values():
            if node.parent_id is None:
                continue
            children.setdefault(node.parent_id, []).append(node.node_id)
        order: List[str] = []
        queue: List[str] = [self.template.root_node().node_id]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            order.append(current)
            queue.extend(children.get(current, []))
        if len(order) != len(nodes):
            missing = set(nodes.keys()) - set(order)
            raise ValueError(f"Unreachable modules detected: {sorted(missing)}")
        return order

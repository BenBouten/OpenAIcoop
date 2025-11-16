"""Graph data structure representing assembled body modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional

from .modules import BodyModule


@dataclass
class BodyNode:
    """Node that stores a module instance and its relations."""

    module: BodyModule
    parent: Optional[str] = None
    attachment_point: Optional[str] = None
    children: Dict[str, str] = field(default_factory=dict)

    def add_child(self, child_id: str, point_name: str) -> None:
        if child_id in self.children:
            raise ValueError(f"Child '{child_id}' already registered under node '{self.module.key}'")
        self.children[child_id] = point_name


class BodyGraph:
    """Mutable forest of body modules with helpers for traversal and queries."""

    def __init__(self, root_id: str, root_module: BodyModule) -> None:
        self.root_id = root_id
        self.nodes: Dict[str, BodyNode] = {root_id: BodyNode(module=root_module)}

    def add_module(
        self,
        node_id: str,
        module: BodyModule,
        parent_id: str,
        attachment_point: str,
    ) -> None:
        """Attach ``module`` to ``parent_id`` at ``attachment_point``."""

        if node_id in self.nodes:
            raise ValueError(f"Node '{node_id}' already exists in the graph")
        parent_node = self.nodes.get(parent_id)
        if parent_node is None:
            raise KeyError(f"Parent '{parent_id}' does not exist")

        point = parent_node.module.get_attachment_point(attachment_point)
        if not point.allows(module):
            raise ValueError(
                f"Attachment point '{attachment_point}' on '{parent_id}' does not accept module type {type(module).__name__}"
            )

        parent_node.add_child(node_id, attachment_point)
        self.nodes[node_id] = BodyNode(module=module, parent=parent_id, attachment_point=attachment_point)

    def remove_module(self, node_id: str) -> None:
        """Remove ``node_id`` and detach its entire sub-tree."""

        if node_id == self.root_id:
            raise ValueError("Cannot remove the root node")
        node = self.nodes.pop(node_id)
        parent = node.parent
        if parent is None:  # pragma: no cover - sanity check
            return
        parent_node = self.nodes[parent]
        parent_node.children.pop(node_id, None)
        for child_id in list(node.children.keys()):
            self.remove_module(child_id)

    def get_node(self, node_id: str) -> BodyNode:
        try:
            return self.nodes[node_id]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise KeyError(f"Node '{node_id}' not found") from exc

    def iter_depth_first(self, start: Optional[str] = None) -> Iterator[BodyNode]:
        """Depth-first traversal starting at ``start`` (root by default)."""

        start = start or self.root_id
        stack: List[str] = [start]
        visited: set[str] = set()
        while stack:
            node_id = stack.pop()
            if node_id in visited:
                continue
            visited.add(node_id)
            node = self.nodes[node_id]
            yield node
            stack.extend(reversed(list(node.children.keys())))

    def iter_modules(self) -> Iterator[BodyModule]:
        """Iterate over the modules contained in the graph."""

        for node in self.iter_depth_first():
            yield node.module

    def children_of(self, node_id: str) -> Dict[str, BodyNode]:
        """Return a mapping of child id to node for ``node_id``."""

        node = self.get_node(node_id)
        return {child_id: self.nodes[child_id] for child_id in node.children}

    def ancestors(self, node_id: str) -> List[BodyNode]:
        """Return a list of ancestors starting from parent up to the root."""

        ancestors: List[BodyNode] = []
        node = self.get_node(node_id)
        parent_id = node.parent
        while parent_id is not None:
            parent_node = self.nodes[parent_id]
            ancestors.append(parent_node)
            parent_id = parent_node.parent
        return ancestors

    def find_path(self, node_id: str) -> List[BodyNode]:
        """Return nodes from root to ``node_id`` inclusive."""

        path = list(reversed(self.ancestors(node_id)))
        path.append(self.get_node(node_id))
        return path

    def summary(self) -> Dict[str, Dict[str, str]]:
        """Return a serialisable view of the current graph layout."""

        summary: Dict[str, Dict[str, str]] = {}
        for node_id, node in self.nodes.items():
            summary[node_id] = {
                "module": node.module.key,
                "type": node.module.module_type,
                "parent": node.parent or "",
                "attachment_point": node.attachment_point or "",
            }
        return summary

    def total_mass(self) -> float:
        """Aggregate mass by summing each module's stats."""

        return sum(node.module.stats.mass for node in self.nodes.values())

    def validate(self) -> None:
        """Run sanity checks to ensure every connection is valid."""

        for node_id, node in self.nodes.items():
            if node.parent is None:
                continue
            parent = self.nodes[node.parent]
            point_name = node.attachment_point
            if point_name is None:
                raise ValueError(f"Node '{node_id}' is missing attachment metadata")
            point = parent.module.get_attachment_point(point_name)
            if not point.allows(node.module):
                raise ValueError(
                    f"Node '{node_id}' uses attachment '{point_name}' on '{node.parent}', which does not allow {type(node.module).__name__}"
                )

    def nodes_at_depth(self, depth: int) -> List[BodyNode]:
        """Return all nodes exactly ``depth`` hops from the root."""

        if depth < 0:
            raise ValueError("depth must be >= 0")
        current = [self.root_id]
        current_depth = 0
        while current and current_depth < depth:
            next_level: List[str] = []
            for node_id in current:
                next_level.extend(self.nodes[node_id].children.keys())
            current = next_level
            current_depth += 1
        return [self.nodes[node_id] for node_id in current]

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes

    def __len__(self) -> int:
        return len(self.nodes)

"""Graph data structure representing assembled body modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import prod, cos, sin, radians
from typing import Dict, Iterator, List, Optional, Tuple

from .modules import BodyModule


@dataclass(frozen=True)
class SteeringSurface:
    """Control surface or thruster that can impart directional thrust."""

    module_type: str
    side: int
    leverage: float
    thrust: float
    lift: float
    phase_offset: float


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
        self._physics_cache: Optional["BodyGraph.PhysicsAggregation"] = None
        self._transforms: Dict[str, Tuple[float, float, float]] = {}
        self._recompute_transform(root_id)

    # ------------------------------------------------------------------
    # Aggregation helpers

    @dataclass(frozen=True)
    class PhysicsAggregation:
        """Aggregated geometry/force stats derived from all modules."""

        mass: float
        volume: float
        frontal_area: float
        lateral_area: float
        dorsal_area: float
        drag_area: float
        total_thrust: float
        total_grip: float
        power_output: float
        energy_cost: float
        buoyancy_volume: float
        lift_total: float
        lift_modules: int
        buoyancy_positive: float
        buoyancy_negative: float
        tentacle_grip: float
        tentacle_span: float
        tentacle_reach: float
        tentacle_count: int
        steering_surfaces: Tuple[SteeringSurface, ...]

    def _aggregate_geometry(self) -> PhysicsAggregation:
        """Internal helper that walks modules once to derive stats."""

        mass = 0.0
        volume = 0.0
        frontal_area = 0.0
        lateral_area = 0.0
        dorsal_area = 0.0
        drag_area = 0.0
        thrust = 0.0
        grip = 0.0
        power_output = 0.0
        energy_cost = 0.0
        buoyancy_volume = 0.0
        lift_total = 0.0
        lift_modules = 0
        buoyancy_positive = 0.0
        buoyancy_negative = 0.0
        tentacle_grip = 0.0
        tentacle_span = 0.0
        tentacle_reach = 0.0
        tentacle_count = 0

        steering_surfaces: list[SteeringSurface] = []

        for node_id, node in self.nodes.items():
            module = node.module
            stats = module.stats
            width, height, length = module.size
            module_volume = max(0.0, prod(module.size))
            module_frontal = max(0.0, width * height)
            module_lateral = max(0.0, height * length)
            module_dorsal = max(0.0, width * length)

            streamlining = self._streamlining_factor(module)
            module_drag = (
                module_frontal * streamlining
                + module_lateral * 0.5 * streamlining
                + module_dorsal * 0.35 * streamlining
            )

            thrust += float(getattr(module, "thrust", 0.0))
            thrust += float(getattr(module, "thrust_power", 0.0))
            grip += float(getattr(module, "grip_strength", 0.0))

            mass += float(stats.mass)
            power_output += float(stats.power_output)
            energy_cost += float(stats.energy_cost)
            volume += module_volume
            frontal_area += module_frontal
            lateral_area += module_lateral
            dorsal_area += module_dorsal
            drag_area += module_drag
            buoyancy_volume += module_volume
            bias = float(getattr(stats, "buoyancy_bias", 0.0))
            if bias >= 0.0:
                buoyancy_positive += bias
            else:
                buoyancy_negative += abs(bias)
            lift_coeff = float(getattr(module, "lift_coefficient", 0.0))
            if lift_coeff > 0.0:
                lift_total += lift_coeff
                lift_modules += 1

            if module.module_type == "tentacle":
                tentacle_count += 1
                tentacle_grip += float(getattr(module, "grip_strength", 0.0))
                tentacle_reach += max(0.0, length)
                tentacle_span += max(width, height)

            if module.module_type in {"propulsion", "tentacle", "limb"} or lift_coeff > 0.0:
                tx, ty, _ = self._transforms.get(node_id, (0.0, 0.0, 0.0))
                side = 0
                if tx > 0.05:
                    side = 1
                elif tx < -0.05:
                    side = -1
                leverage = max(0.1, abs(tx) + 0.15 * abs(ty))
                thrust_power = float(getattr(module, "thrust_power", 0.0)) + float(
                    getattr(module, "thrust", 0.0)
                )
                if thrust_power > 0.0 or lift_coeff > 0.0:
                    phase_seed = int.from_bytes(node_id.encode("utf-8"), "little") % 1000
                    phase_offset = (phase_seed / 1000.0) * 6.28318
                    steering_surfaces.append(
                        SteeringSurface(
                            module_type=module.module_type,
                            side=side,
                            leverage=leverage,
                            thrust=thrust_power,
                            lift=lift_coeff,
                            phase_offset=phase_offset,
                        )
                    )

        return BodyGraph.PhysicsAggregation(
            mass=mass,
            volume=volume,
            frontal_area=frontal_area,
            lateral_area=lateral_area,
            dorsal_area=dorsal_area,
            drag_area=drag_area,
            total_thrust=thrust,
            total_grip=grip,
            power_output=power_output,
            energy_cost=energy_cost,
            buoyancy_volume=buoyancy_volume,
            lift_total=lift_total,
            lift_modules=lift_modules,
            buoyancy_positive=buoyancy_positive,
            buoyancy_negative=buoyancy_negative,
            tentacle_grip=tentacle_grip,
            tentacle_span=tentacle_span,
            tentacle_reach=tentacle_reach,
            tentacle_count=tentacle_count,
            steering_surfaces=tuple(steering_surfaces),
        )

    @staticmethod
    def _streamlining_factor(module: BodyModule) -> float:
        """Return a heuristic factor to describe hydrodynamic drag."""

        base = 1.0
        if module.module_type == "propulsion":
            base = 0.75
        elif module.module_type == "head":
            base = 0.85
        elif module.module_type == "limb":
            base = 1.2
        elif module.module_type == "tentacle":
            base = 1.35
        elif module.module_type == "sensor":
            base = 0.95
        elif module.module_type == "core":
            base = 0.9
        elif module.module_type == "bell_core":
            base = 0.82
        return base

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
        self._physics_cache = None
        self._recompute_transform(node_id)

    @staticmethod
    def _module_radius(module: BodyModule) -> float:
        width, height, _ = module.size
        return max(width, height) / 2.0

    def _compute_single_transform(self, node_id: str) -> Tuple[float, float, float]:
        node = self.nodes[node_id]
        if node.parent is None:
            angle = getattr(node.module, "natural_orientation", 0.0)
            transform = (0.0, 0.0, angle)
        else:
            parent_id = node.parent
            if parent_id not in self._transforms:
                self._compute_single_transform(parent_id)
            px, py, pa = self._transforms[parent_id]
            parent_module = self.nodes[parent_id].module
            point = parent_module.get_attachment_point(node.attachment_point or "")
            ox, oy = getattr(point, "offset", (0.0, 0.0))
            if getattr(point, "relative", False):
                width, height, _ = parent_module.size
                ox *= width
                oy *= height
            parent_angle = radians(pa)
            attach_x = px + ox * cos(parent_angle) - oy * sin(parent_angle)
            attach_y = py + ox * sin(parent_angle) + oy * cos(parent_angle)
            direction = pa + getattr(point, "angle", 0.0)
            direction_rad = radians(direction)
            clearance = getattr(point, "clearance", 0.0)
            radius = self._module_radius(node.module)
            offset_distance = clearance + radius
            attach_x += offset_distance * cos(direction_rad)
            attach_y += offset_distance * sin(direction_rad)
            angle = direction + getattr(node.module, "natural_orientation", 0.0)
            transform = (attach_x, attach_y, angle)
        self._transforms[node_id] = transform
        return transform

    def _recompute_transform(self, node_id: str) -> None:
        self._compute_single_transform(node_id)
        for child_id in self.nodes[node_id].children:
            self._recompute_transform(child_id)

    def node_transform(self, node_id: str) -> Tuple[float, float, float]:
        return self._transforms.get(node_id, (0.0, 0.0, 0.0))

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
        self._physics_cache = None
        self._transforms.pop(node_id, None)

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

        return self.aggregate_physics_stats().mass

    def total_volume(self) -> float:
        """Aggregate module volume (used for buoyancy calculations)."""

        return self.aggregate_physics_stats().volume

    def total_thrust(self) -> float:
        """Sum of all locomotion modules' thrust output."""

        return self.aggregate_physics_stats().total_thrust

    def total_grip_strength(self) -> float:
        """Sum of limb grip strengths for crawling/balancing heuristics."""

        return self.aggregate_physics_stats().total_grip

    def drag_signature(self) -> float:
        """Return a heuristic drag area derived from module cross-sections."""

        return self.aggregate_physics_stats().drag_area

    def buoyancy_volume(self) -> float:
        """Effective displaced volume used to estimate buoyancy."""

        return self.aggregate_physics_stats().buoyancy_volume

    def frontal_area(self) -> float:
        """Return the combined frontal cross-section."""

        return self.aggregate_physics_stats().frontal_area

    def lateral_area(self) -> float:
        """Return the combined lateral cross-section."""

        return self.aggregate_physics_stats().lateral_area

    def dorsal_area(self) -> float:
        """Return the combined dorsal cross-section."""

        return self.aggregate_physics_stats().dorsal_area

    def available_power(self) -> float:
        """Return the total power output produced by all modules."""

        return self.aggregate_physics_stats().power_output

    def upkeep_energy_cost(self) -> float:
        """Return the sum of passive energy costs for the body."""

        return self.aggregate_physics_stats().energy_cost

    def aggregate_physics_stats(self) -> "BodyGraph.PhysicsAggregation":
        """Expose a cached view combining geometry, forces and resources."""

        if self._physics_cache is None:
            self._physics_cache = self._aggregate_geometry()
        return self._physics_cache

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

    def compute_bounds(self) -> Tuple[float, float, float]:
        """Calculate total width, height, and depth of the assembled body (meters)."""
        min_x, max_x = 0.0, 0.0
        min_y, max_y = 0.0, 0.0
        min_z, max_z = 0.0, 0.0

        for node_id, node in self.nodes.items():
            tx, ty, ta = self.node_transform(node_id)
            module = node.module
            width, height, length = module.size
            # Simple axis-aligned bounds: treat module as box centered at transform
            half_w = width / 2.0
            half_h = height / 2.0
            half_l = length / 2.0

            min_x = min(min_x, tx - half_w)
            max_x = max(max_x, tx + half_w)
            min_y = min(min_y, ty - half_h)
            max_y = max(max_y, ty + half_h)
            min_z = min(min_z, -half_l)
            max_z = max(max_z, half_l)

        width_total = max(0.1, max_x - min_x)
        height_total = max(0.1, max_y - min_y)
        depth_total = max(0.1, max_z - min_z)
        return width_total, height_total, depth_total

    def geometry_summary(self) -> Dict[str, float]:
        """Return a cached geometry view for spawning/AI heuristics."""
        if self._physics_cache is None:
            _ = self.aggregate_physics_stats()
        width, height, depth = self.compute_bounds()
        frontal = width * height
        lateral = height * depth
        dorsal = width * depth
        collision_radius = max(width, height, depth) / 2.0
        return {
            "width": width,
            "height": height,
            "depth": depth,
            "frontal_area": frontal,
            "lateral_area": lateral,
            "dorsal_area": dorsal,
            "collision_radius": collision_radius,
        }

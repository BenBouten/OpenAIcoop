"""Conversion between procedural body graphs and physics-friendly parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from ..body.body_graph import BodyGraph


@dataclass(frozen=True)
class PhysicsBody:
    """Compact representation of hydrodynamic properties for simulation."""

    mass: float
    volume: float
    density: float
    frontal_area: float
    lateral_area: float
    dorsal_area: float
    drag_coefficient: float
    buoyancy_volume: float
    max_thrust: float
    grip_strength: float
    power_output: float
    energy_cost: float
    lift_per_fin: float = 0.0
    buoyancy_offsets: Tuple[float, float] = (0.0, 0.0)
    tentacle_grip: float = 0.0
    tentacle_span: float = 0.0
    tentacle_reach: float = 0.0
    tentacle_count: int = 0

    def propulsion_acceleration(self, effort: float) -> float:
        """Return longitudinal acceleration (m/s^2) for the provided effort."""

        clamped = max(-1.0, min(1.0, effort))
        return (self.max_thrust * clamped) / max(0.1, self.mass)


def _derive_drag_coefficient(aggregation: BodyGraph.PhysicsAggregation) -> float:
    """Translate surface area heuristics to a usable drag coefficient."""

    reference_area = max(1.0, aggregation.frontal_area * 0.7 + aggregation.lateral_area * 0.2)
    drag = aggregation.drag_area / reference_area
    return max(0.05, min(2.5, drag))


def build_physics_body(graph: BodyGraph) -> PhysicsBody:
    """Convert a :class:`BodyGraph` into hydrodynamic parameters."""

    aggregation = graph.aggregate_physics_stats()
    mass = max(0.1, aggregation.mass)
    volume = max(1.0, aggregation.volume)
    density = mass / max(1.0, volume)
    drag_coefficient = _derive_drag_coefficient(aggregation)
    lift_per_fin = 0.0
    if aggregation.lift_modules > 0:
        lift_per_fin = aggregation.lift_total / aggregation.lift_modules
    buoyancy_offsets = (aggregation.buoyancy_positive, aggregation.buoyancy_negative)
    return PhysicsBody(
        mass=mass,
        volume=volume,
        density=density,
        frontal_area=aggregation.frontal_area,
        lateral_area=aggregation.lateral_area,
        dorsal_area=aggregation.dorsal_area,
        drag_coefficient=drag_coefficient,
        buoyancy_volume=max(1.0, aggregation.buoyancy_volume),
        max_thrust=max(5.0, aggregation.total_thrust),
        grip_strength=max(0.0, aggregation.total_grip),
        power_output=aggregation.power_output,
        energy_cost=aggregation.energy_cost,
        lift_per_fin=lift_per_fin,
        buoyancy_offsets=buoyancy_offsets,
        tentacle_grip=aggregation.tentacle_grip,
        tentacle_span=aggregation.tentacle_span,
        tentacle_reach=aggregation.tentacle_reach,
        tentacle_count=aggregation.tentacle_count,
    )

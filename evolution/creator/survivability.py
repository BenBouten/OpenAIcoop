"""Survivability metric helpers for Creature Creator drafts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..body.body_graph import BodyGraph
from ..world.ocean_world import DepthLayer

_GRAVITY = 9.81


@dataclass
class LayerBuoyancy:
    layer_name: str
    drift: str
    net_force: float


@dataclass
class SurvivabilityMetrics:
    mobility_rating: str
    thrust_to_drag: float
    energy_efficiency: float
    sensors: float
    offence: float
    defence: float
    buoyancy_by_layer: List[LayerBuoyancy]


def evaluate_graph(graph: BodyGraph, layers: List[DepthLayer]) -> SurvivabilityMetrics:
    aggregation = graph.aggregate_physics_stats()
    drag = max(1e-3, aggregation.drag_area)
    thrust = aggregation.total_thrust
    thrust_to_drag = thrust / drag
    mobility_rating = _categorise(thrust_to_drag, (0.4, 0.8, 1.5), ("Traag", "Gemiddeld", "Zeer wendbaar"))

    energy_cost = max(1e-3, aggregation.energy_cost)
    power_output = max(1e-3, aggregation.power_output)
    energy_ratio = power_output / energy_cost
    energy_efficiency = energy_ratio

    sensors = aggregation.lift_total  # proxy for sensor coverage for now
    offence = aggregation.total_thrust * 0.2
    defence = aggregation.mass * 0.1

    buoyancy_rows = _estimate_buoyancy(graph, aggregation, layers)

    return SurvivabilityMetrics(
        mobility_rating=mobility_rating,
        thrust_to_drag=thrust_to_drag,
        energy_efficiency=energy_efficiency,
        sensors=sensors,
        offence=offence,
        defence=defence,
        buoyancy_by_layer=buoyancy_rows,
    )


def _categorise(value: float, thresholds: tuple[float, float, float], labels: tuple[str, str, str]) -> str:
    low, medium, high = thresholds
    slow, average, fast = labels
    if value < low:
        return slow
    if value < medium:
        return average
    return fast if value >= high else average


def _estimate_buoyancy(graph: BodyGraph, aggregation, layers: List[DepthLayer]) -> List[LayerBuoyancy]:
    results: List[LayerBuoyancy] = []
    displaced_volume = aggregation.buoyancy_volume
    mass = max(1.0, aggregation.mass)
    weight = mass * _GRAVITY
    for layer in layers:
        fluid_density = getattr(layer.biome, "density", 1.0)
        buoyant_force = fluid_density * displaced_volume * _GRAVITY
        net_force = buoyant_force - weight
        drift = "stijgt" if net_force > weight * 0.05 else ("daalt" if net_force < -weight * 0.05 else "zweeft")
        results.append(LayerBuoyancy(layer.biome.name, drift, net_force))
    return results


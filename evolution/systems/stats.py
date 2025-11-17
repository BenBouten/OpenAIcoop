"""Simulation statistics aggregation helpers."""

from __future__ import annotations

from typing import Dict

from ..simulation.state import SimulationState


def collect_population_stats(
    state: SimulationState, formatted_time_passed: str
) -> Dict[str, object]:
    """Return aggregated statistics for the current lifeform population."""

    lifeforms = state.lifeforms
    death_ages = state.death_ages

    stats: Dict[str, object] = {
        "lifeform_count": len(lifeforms),
        "formatted_time": formatted_time_passed,
        "average_health": 0.0,
        "average_vision": 0.0,
        "average_gen": 0.0,
        "average_hunger": 0.0,
        "average_size": 0.0,
        "average_age": 0.0,
        "average_maturity": 0.0,
        "average_speed": 0.0,
        "average_cooldown": 0.0,
        "average_mass": 0.0,
        "average_body_mass": 0.0,
        "average_reach": 0.0,
        "average_maintenance_cost": 0.0,
        "average_perception_rays": 0.0,
        "average_hearing_range": 0.0,
        "average_module_count": 0.0,
        "average_drag": 0.0,
        "average_max_thrust": 0.0,
        "average_body_energy_cost": 0.0,
        "death_age_avg": sum(death_ages) / len(death_ages) if death_ages else 0.0,
        "dna_count": {},
        "dna_attribute_averages": {},
    }

    if lifeforms:
        count = len(lifeforms)
        totals = {
            "health_now": 0.0,
            "vision": 0.0,
            "generation": 0.0,
            "hunger": 0.0,
            "size": 0.0,
            "age": 0.0,
            "maturity": 0.0,
            "speed": 0.0,
            "reproduced_cooldown": 0.0,
            "mass": 0.0,
            "reach": 0.0,
            "maintenance": 0.0,
            "perception_rays": 0.0,
            "hearing_range": 0.0,
            "modules": 0.0,
            "drag": 0.0,
            "thrust": 0.0,
            "body_mass": 0.0,
            "body_energy": 0.0,
        }
        dna_attributes = [
            "health",
            "vision",
            "attack_power_now",
            "defence_power_now",
            "speed",
            "maturity",
            "size",
            "longevity",
            "energy",
            "mass",
            "reach",
            "perception_rays",
            "maintenance_cost",
            "hearing_range",
        ]
        dna_totals: Dict[int, Dict[str, float]] = {}

        for lifeform in lifeforms:
            totals["health_now"] += lifeform.health_now
            totals["vision"] += lifeform.vision
            totals["generation"] += lifeform.generation
            totals["hunger"] += lifeform.hunger
            totals["size"] += lifeform.size
            totals["age"] += lifeform.age
            totals["maturity"] += lifeform.maturity
            totals["speed"] += lifeform.speed
            totals["reproduced_cooldown"] += lifeform.reproduced_cooldown
            totals["mass"] += getattr(lifeform, "mass", 1.0)
            totals["reach"] += getattr(lifeform, "reach", 4.0)
            totals["maintenance"] += getattr(lifeform, "maintenance_cost", 0.0)
            totals["perception_rays"] += getattr(lifeform, "perception_rays", 0.0)
            totals["hearing_range"] += getattr(lifeform, "hearing_range", 0.0)
            totals["modules"] += float(getattr(lifeform, "body_module_count", 0.0))
            totals["drag"] += float(getattr(lifeform, "drag_coefficient", 0.0))
            totals["thrust"] += float(getattr(lifeform, "max_thrust", 0.0))
            totals["body_mass"] += float(getattr(lifeform, "body_mass", getattr(lifeform, "mass", 0.0)))
            totals["body_energy"] += float(getattr(lifeform, "body_energy_cost", getattr(lifeform, "maintenance_cost", 0.0)))

            dna_entry = dna_totals.setdefault(
                lifeform.dna_id,
                {"count": 0.0, **{attr: 0.0 for attr in dna_attributes}},
            )
            dna_entry["count"] += 1.0
            for attribute in dna_attributes:
                dna_entry[attribute] += getattr(lifeform, attribute)

        stats["average_health"] = totals["health_now"] / count
        stats["average_vision"] = totals["vision"] / count
        stats["average_gen"] = totals["generation"] / count
        stats["average_hunger"] = totals["hunger"] / count
        stats["average_size"] = totals["size"] / count
        stats["average_age"] = totals["age"] / count
        stats["average_maturity"] = totals["maturity"] / count
        stats["average_speed"] = totals["speed"] / count
        stats["average_cooldown"] = totals["reproduced_cooldown"] / count
        stats["average_mass"] = totals["mass"] / count
        stats["average_reach"] = totals["reach"] / count
        stats["average_maintenance_cost"] = totals["maintenance"] / count
        stats["average_perception_rays"] = totals["perception_rays"] / count
        stats["average_hearing_range"] = totals["hearing_range"] / count
        stats["average_module_count"] = totals["modules"] / count
        stats["average_drag"] = totals["drag"] / count
        stats["average_max_thrust"] = totals["thrust"] / count
        stats["average_body_mass"] = totals["body_mass"] / count
        stats["average_body_energy_cost"] = totals["body_energy"] / count
        stats["dna_count"] = {
            _normalize_dna_id(dna_id): int(data["count"])
            for dna_id, data in dna_totals.items()
        }
        stats["dna_attribute_averages"] = {
            _normalize_dna_id(dna_id): {
                attribute: data[attribute] / data["count"]
                for attribute in dna_attributes
            }
            for dna_id, data in dna_totals.items()
            if data["count"]
        }

    return stats


def _normalize_dna_id(dna_id: object) -> object:
    """Return a consistent, JSON-serialisable representation of a DNA identifier."""

    if isinstance(dna_id, int):
        return dna_id

    try:
        return int(dna_id)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return str(dna_id)

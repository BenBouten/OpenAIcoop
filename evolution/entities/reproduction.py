"""Reproduction helpers for entities."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple, TYPE_CHECKING

from ..config import settings
from ..dna.blueprints import generate_modular_blueprint
from ..dna.development import mix_development_plans, mutate_profile_development
from ..dna.factory import build_body_graph
from ..dna.genes import Genome
from ..dna.mutation import MutationError, mutate_genome
from ..morphology.genotype import MorphologyGenotype, mutate_profile_morphology

if TYPE_CHECKING:
    from ..simulation.state import SimulationState
    from .lifeform import Lifeform


@dataclass(frozen=True)
class OffspringMetadata:
    """Summary of the genetic changes applied to an offspring profile."""

    dna_change: float
    color_change: float
    mutations: Tuple[str, ...]
    source_profile: str
    is_new_profile: bool


def create_offspring_profile(
    state: "SimulationState",
    parent: "Lifeform",
    partner: "Lifeform",
) -> Tuple[Dict[str, object], OffspringMetadata]:
    """Create a DNA profile for the offspring of two parents."""

    candidate = _mix_parent_traits(parent, partner)
    _apply_mutations(candidate)
    _clamp_profile(candidate)

    parent_profile = _find_profile(state.dna_profiles, parent.dna_id)
    dna_change, color_change, mutated_attributes = _calculate_change(
        candidate, parent_profile
    )

    is_new_profile = False
    source_profile_id: str = str(parent.dna_id)

    graph = None
    geometry = None
    if settings.USE_BODYGRAPH_SIZE:
        graph, geometry = _build_offspring_geometry(candidate)
        _apply_geometry_dimensions(candidate, geometry)

    if (
        dna_change > settings.DNA_CHANGE_THRESHOLD
        or color_change > settings.COLOR_CHANGE_THRESHOLD
    ):
        matched_profile = _find_matching_profile(
            candidate, state.dna_profiles, exclude_id=parent.dna_id
        )
        if matched_profile is not None:
            candidate = matched_profile.copy()
            source_profile_id = str(candidate["dna_id"])
        else:
            candidate = _register_new_profile(
                state,
                parent,
                partner,
                candidate,
                dna_change,
                color_change,
                mutated_attributes,
            )
            source_profile_id = str(candidate["dna_id"])
            is_new_profile = True
    else:
        candidate["dna_id"] = parent.dna_id

    if settings.USE_BODYGRAPH_SIZE and not geometry:
        _, geometry = _build_offspring_geometry(candidate)
        _apply_geometry_dimensions(candidate, geometry)

    metadata = OffspringMetadata(
        dna_change=dna_change,
        color_change=color_change,
        mutations=tuple(mutated_attributes),
        source_profile=source_profile_id,
        is_new_profile=is_new_profile,
    )
    return candidate, metadata


def _mix_parent_traits(parent: "Lifeform", partner: "Lifeform") -> Dict[str, object]:
    color = tuple(
        max(0, min(255, int((a + b) / 2)))
        for a, b in zip(parent.color, partner.color)
    )

    social = (parent.social_tendency + partner.social_tendency) / 2
    boid = (getattr(parent, "boid_tendency", social) + getattr(partner, "boid_tendency", social)) / 2
    risk = (parent.risk_tolerance + partner.risk_tolerance) / 2
    restlessness = (parent.restlessness + partner.restlessness) / 2

    diet = parent.diet if parent.diet == partner.diet else random.choice(
        [parent.diet, partner.diet]
    )

    morphology = MorphologyGenotype.mix(parent.morphology, partner.morphology)
    development = mix_development_plans(diet, parent.development, partner.development)

    genome_blueprint = _mix_parent_genome(parent, partner)

    return {
        "dna_id": parent.dna_id,
        "width": int((parent.width + partner.width) // 2),
        "height": int((parent.height + partner.height) // 2),
        "color": color,
        "health": int((parent.health + partner.health) // 2),
        "maturity": int((parent.maturity + partner.maturity) // 2),
        "vision": int((parent.vision + partner.vision) // 2),
        "defence_power": int(
            (parent.defence_power + partner.defence_power) // 2
        ),
        "attack_power": int(
            (parent.attack_power + partner.attack_power) // 2
        ),
        "energy": int((parent.energy + partner.energy) // 2),
        "longevity": int((parent.longevity + partner.longevity) // 2),
        "diet": diet,
        "social": social,
        "boid_tendency": boid,
        "risk_tolerance": risk,
        "restlessness": restlessness,
        "morphology": morphology.to_dict(),
        "development": development,
        "genome": genome_blueprint,
    }


def _mix_parent_genome(parent: "Lifeform", partner: "Lifeform") -> Dict[str, object]:
    genomes: List[Genome] = []
    for candidate in (getattr(parent, "genome", None), getattr(partner, "genome", None)):
        if isinstance(candidate, Genome):
            genomes.append(candidate)
    if not genomes:
        return generate_modular_blueprint(getattr(parent, "diet", "omnivore"))

    base = random.choice(genomes)
    genome = base
    try:
        if random.randint(0, 100) < settings.MUTATION_CHANCE:
            genome = mutate_genome(genome)
    except MutationError:
        genome = base
    return genome.to_dict()


def _apply_mutations(profile: Dict[str, object]) -> None:
    chance = settings.MUTATION_CHANCE

    if random.randint(0, 100) < chance:
        profile["width"] += random.randint(-2, 2)
    if random.randint(0, 100) < chance:
        profile["height"] += random.randint(-2, 2)
    if random.randint(0, 100) < chance:
        profile["color"] = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
        )
    if random.randint(0, 100) < chance:
        profile["health"] += random.randint(-25, 25)
    if random.randint(0, 100) < chance:
        profile["maturity"] += random.randint(-40, 40)
    if random.randint(0, 100) < chance:
        profile["vision"] += random.randint(-6, 6)
    if random.randint(0, 100) < chance:
        profile["defence_power"] += random.randint(-20, 20)
    if random.randint(0, 100) < chance:
        profile["attack_power"] += random.randint(-20, 20)
    if random.randint(0, 100) < chance:
        profile["energy"] += random.randint(-6, 6)
    if random.randint(0, 100) < chance:
        profile["longevity"] += random.randint(-120, 120)
    if random.randint(0, 100) < chance:
        profile["social"] += random.uniform(-0.08, 0.08)
    if random.randint(0, 100) < chance:
        profile["boid_tendency"] = profile.get("boid_tendency", profile.get("social", 0.5)) + random.uniform(
            -0.08, 0.08
        )
    if random.randint(0, 100) < chance:
        profile["risk_tolerance"] += random.uniform(-0.08, 0.08)
    if random.randint(0, 100) < chance:
        profile["restlessness"] = profile.get("restlessness", 0.5) + random.uniform(
            -0.12, 0.12
        )

    mutate_profile_morphology(profile)
    mutate_profile_development(profile)


def _apply_geometry_dimensions(profile: Dict[str, object], geometry: Optional[Dict[str, float]]) -> None:
    if not geometry:
        return
    width_m = geometry.get("width")
    height_m = geometry.get("height")
    if width_m is not None:
        profile["width"] = max(1, int(round(width_m * settings.BODY_PIXEL_SCALE)))
    if height_m is not None:
        profile["height"] = max(1, int(round(height_m * settings.BODY_PIXEL_SCALE)))
    profile["collision_radius"] = geometry.get(
        "collision_radius",
        profile.get("collision_radius", max(profile.get("width", 1), profile.get("height", 1)) / 2),
    )
    profile["geometry"] = geometry


def _build_offspring_geometry(profile: Dict[str, object]) -> Tuple[Optional[object], Optional[Dict[str, float]]]:
    try:
        result = build_body_graph(profile.get("genome", {}), include_geometry=True)
    except Exception:
        return None, None
    if isinstance(result, tuple):
        graph, geometry = result
    else:
        graph, geometry = result, None
    return graph, geometry


def _clamp_profile(profile: Dict[str, object]) -> None:
    if settings.USE_BODYGRAPH_SIZE and "geometry" in profile:
        _apply_geometry_dimensions(profile, profile.get("geometry"))
    else:
        profile["width"] = max(
            settings.MIN_WIDTH, min(settings.MAX_WIDTH, int(profile.get("width", settings.MIN_WIDTH)))
        )
        profile["height"] = max(
            settings.MIN_HEIGHT, min(settings.MAX_HEIGHT, int(profile.get("height", settings.MIN_HEIGHT)))
        )

    r, g, b = profile["color"]
    profile["color"] = (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )

    profile["health"] = max(1, int(profile["health"]))
    profile["maturity"] = max(
        settings.MIN_MATURITY, min(settings.MAX_MATURITY, int(profile["maturity"]))
    )
    profile["vision"] = max(
        settings.VISION_MIN, min(settings.VISION_MAX, int(profile["vision"]))
    )
    profile["defence_power"] = max(1, min(100, int(profile["defence_power"])) )
    profile["attack_power"] = max(1, min(100, int(profile["attack_power"])) )
    profile["energy"] = max(1, min(150, int(profile["energy"])) )
    profile["longevity"] = max(1, int(profile["longevity"]))
    profile["social"] = float(max(0.0, min(1.0, profile["social"])))
    profile["boid_tendency"] = float(
        max(0.0, min(1.0, profile.get("boid_tendency", profile["social"])) )
    )
    profile["risk_tolerance"] = float(
        max(0.0, min(1.0, profile["risk_tolerance"]))
    )
    profile["restlessness"] = float(
        max(0.0, min(1.0, profile.get("restlessness", 0.5)))
    )


def _calculate_change(
    candidate: Dict[str, object],
    reference: Optional[Dict[str, object]],
) -> Tuple[float, float, Tuple[str, ...]]:
    if reference is None:
        return 0.0, 0.0, tuple()

    dna_change = 0.0
    color_change = 0.0
    compared = 0
    mutated: set[str] = set()

    for attribute, value in candidate.items():
        if attribute == "dna_id" or attribute not in reference:
            continue

        original_value = reference[attribute]
        if isinstance(value, tuple) and isinstance(original_value, tuple):
            denom = sum(original_value) or 1
            delta = sum(
                abs(int(v) - int(ov)) for v, ov in zip(value, original_value)
            ) / denom
            if delta > 0:
                mutated.add(attribute)
            color_change = delta
            dna_change += delta
            compared += 1
        elif isinstance(value, (int, float)) and isinstance(
            original_value, (int, float)
        ):
            if original_value != 0:
                delta = abs(float(original_value) - float(value)) / abs(
                    float(original_value)
                )
            else:
                delta = 1.0 if value != 0 else 0.0
            if delta > 0:
                mutated.add(attribute)
            dna_change += delta
            compared += 1
        elif isinstance(value, Mapping) and isinstance(original_value, Mapping):
            delta = _mapping_difference(value, original_value)
            if delta > 0:
                mutated.add(attribute)
            dna_change += delta
            compared += 1

    if compared:
        dna_change /= compared

    return dna_change, color_change, tuple(sorted(mutated))


def _find_profile(
    profiles: Iterable[Dict[str, object]], dna_id: object
) -> Optional[Dict[str, object]]:
    for profile in profiles:
        if profile.get("dna_id") == dna_id:
            return profile
    return None


def _find_matching_profile(
    candidate: Dict[str, object],
    profiles: Iterable[Dict[str, object]],
    exclude_id: object,
) -> Optional[Dict[str, object]]:
    for profile in profiles:
        if profile.get("dna_id") == exclude_id:
            continue
        dna_delta, color_delta, _ = _calculate_change(candidate, profile)
        if (
            dna_delta < settings.DNA_CHANGE_THRESHOLD
            and color_delta < settings.COLOR_CHANGE_THRESHOLD
        ):
            return profile
    return None


def _register_new_profile(
    state: "SimulationState",
    parent: "Lifeform",
    partner: "Lifeform",
    candidate: Dict[str, object],
    dna_change: float,
    color_change: float,
    mutated_attributes: Tuple[str, ...],
) -> Dict[str, object]:
    parent_id = str(parent.dna_id)
    counts = state.dna_id_counts
    counts[parent_id] = counts.get(parent_id, 0) + 1
    new_id = f"{parent_id}-{counts[parent_id]}"

    new_profile = candidate.copy()
    new_profile["dna_id"] = new_id
    state.dna_profiles.append(new_profile.copy())
    state.dna_home_biome[new_id] = state.dna_home_biome.get(parent.dna_id)
    state.dna_lineage[new_id] = {
        "parents": (str(parent.dna_id), str(partner.dna_id)),
        "dna_change": dna_change,
        "color_change": color_change,
        "mutations": list(mutated_attributes),
    }
    return new_profile


def _mapping_difference(candidate: Mapping[str, object], reference: Mapping[str, object]) -> float:
    """Return a relative difference metric between two numeric mappings."""

    total = 0.0
    compared = 0
    for key, value in candidate.items():
        if key not in reference:
            continue
        original_value = reference[key]
        if isinstance(value, (int, float)) and isinstance(original_value, (int, float)):
            compared += 1
            if original_value != 0:
                total += abs(float(original_value) - float(value)) / abs(float(original_value))
            elif value != 0:
                total += 1.0
        elif isinstance(value, Mapping) and isinstance(original_value, Mapping):
            nested_delta = _mapping_difference(value, original_value)
            if nested_delta:
                compared += 1
                total += nested_delta

    if compared == 0:
        return 0.0
    return total / compared

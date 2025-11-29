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
from .neural_controller import (
    expected_weight_count,
    initialize_brain_weights,
    mutate_brain_weights,
)

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

    candidate, genome_mutations = _mix_parent_traits(parent, partner)
    
    # Apply unified mutations (genome, brain, traits)
    mutation_list = _mutate_offspring(candidate)
    
    _clamp_profile(candidate)

    parent_profile = _find_profile(state.dna_profiles, parent.dna_id)
    dna_change, color_change, mutated_attributes = _calculate_change(
        candidate, parent_profile
    )
    
    # Combine all mutation sources
    all_mutations = list(mutated_attributes) + genome_mutations + mutation_list

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
                tuple(all_mutations),
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
        mutations=tuple(all_mutations),
        source_profile=source_profile_id,
        is_new_profile=is_new_profile,
    )
    
    # Log reproduction telemetry
    try:
        import pygame
        from ..systems import telemetry
        telemetry.reproduction_sample(
            tick=pygame.time.get_ticks(),
            parent_1_id=getattr(parent, "id", "unknown"),
            parent_2_id=getattr(partner, "id", "unknown"),
            parent_1_dna=str(parent.dna_id),
            parent_2_dna=str(partner.dna_id),
            offspring_dna=str(candidate.get("dna_id", "unknown")),
            is_new_profile=is_new_profile,
            dna_change=dna_change,
            color_change=color_change,
            mutations=all_mutations,
            offspring_color=candidate.get("color", (0, 0, 0)),
        )
    except Exception:
        pass
        
    return candidate, metadata


def create_asexual_offspring(
    state: "SimulationState",
    parent: "Lifeform",
) -> Tuple[Dict[str, object], OffspringMetadata]:
    """Create a DNA profile for the asexual offspring of a parent."""

    candidate, genome_mutations = _clone_parent_traits(parent)
    
    # Apply unified mutations (genome, brain, traits)
    mutation_list = _mutate_offspring(candidate)
    
    _clamp_profile(candidate)

    parent_profile = _find_profile(state.dna_profiles, parent.dna_id)
    dna_change, color_change, mutated_attributes = _calculate_change(
        candidate, parent_profile
    )
    
    # Combine all mutation sources
    all_mutations = list(mutated_attributes) + genome_mutations + mutation_list

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
            # Register new profile (using parent as both parents for lineage)
            candidate = _register_new_profile(
                state,
                parent,
                parent, 
                candidate,
                dna_change,
                color_change,
                tuple(all_mutations),
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
        mutations=tuple(all_mutations),
        source_profile=source_profile_id,
        is_new_profile=is_new_profile,
    )
    
    # Log reproduction telemetry
    try:
        import pygame
        from ..systems import telemetry
        telemetry.reproduction_sample(
            tick=pygame.time.get_ticks(),
            parent_1_id=getattr(parent, "id", "unknown"),
            parent_2_id="asexual",
            parent_1_dna=str(parent.dna_id),
            parent_2_dna="none",
            offspring_dna=str(candidate.get("dna_id", "unknown")),
            is_new_profile=is_new_profile,
            dna_change=dna_change,
            color_change=color_change,
            mutations=all_mutations,
            offspring_color=candidate.get("color", (0, 0, 0)),
        )
    except Exception:
        pass
        
    return candidate, metadata



def _mutate_offspring(profile: Dict[str, object]) -> List[str]:
    """Apply unified mutations to an offspring profile (genome, brain, traits)."""
    mutations: List[str] = []
    
    # 1. Genome Mutation
    # Note: Genome structural mutation is complex to do on a dict.
    # Ideally, we should have mutated the Genome object before converting to dict.
    # In _mix_parent_genome and _clone_parent_traits, we already handle genome mutation
    # if we kept that logic.
    # Let's rely on the upstream functions for genome mutation for now, 
    # or implementing a proper Genome.from_dict() -> mutate -> to_dict() flow would be better but requires more changes.
    # For this refactor, we will assume genome mutations are handled during the mix/clone phase 
    # OR we add a simple "parameter mutation" for modules if possible.
    
    # However, we removed genome mutation from _clone_parent_traits!
    # So we MUST handle it here or put it back.
    # Since we don't have the Genome object here easily, let's put it back in _clone_parent_traits 
    # and _mix_parent_genome, OR we accept that we need to reconstruct Genome here.
    
    # Let's try to reconstruct Genome if possible.
    # We need constraints. We don't have them here.
    # So, let's revert the decision to remove genome mutation from _clone_parent_traits?
    # No, the goal was to unify.
    
    # Alternative: Pass 'state' to this function and use default constraints?
    # Or just handle non-structural mutations here?
    
    # Let's stick to Brain and Traits here for now, and rely on _mix_parent_genome for genome mutations (which it does).
    # But _clone_parent_traits needs to mutate genome too.
    
    # 2. Brain Mutation
    if "brain_weights" in profile and random.randint(0, 100) < settings.MUTATION_CHANCE:
        weights = list(profile["brain_weights"]) # type: ignore
        profile["brain_weights"] = mutate_brain_weights(
            weights,
            mutation_rate=0.1, # 10% of weights change
            sigma=0.1
        )
        mutations.append("brain_structure")

    # 3. Trait Mutations
    # List of mutable scalar traits
    traits = [
        "risk_tolerance",
        "restlessness",
        "bite_force",
        "tissue_hardness",
        "digest_efficiency_plants",
        "digest_efficiency_meat",
        "longevity",
    ]
    
    for trait in traits:
        if trait in profile and random.randint(0, 100) < settings.MUTATION_CHANCE:
            current = float(profile[trait]) # type: ignore
            # +/- 10% variation
            delta = random.uniform(-0.1, 0.1)
            new_val = current + delta
            # Clamp logic will handle limits later
            profile[trait] = new_val
            mutations.append(trait)

    # Color mutation
    if random.randint(0, 100) < settings.MUTATION_CHANCE:
        r, g, b = profile["color"] # type: ignore
        dr = random.randint(-20, 20)
        dg = random.randint(-20, 20)
        db = random.randint(-20, 20)
        profile["color"] = (r + dr, g + dg, b + db)
        mutations.append(f"color: {profile['color']}")

    return mutations


def _mix_parent_traits(parent: "Lifeform", partner: "Lifeform") -> Tuple[Dict[str, object], List[str]]:
    color = tuple(
        max(0, min(255, int((a + b) / 2)))
        for a, b in zip(parent.color, partner.color)
    )

    risk = (parent.risk_tolerance + partner.risk_tolerance) / 2
    restlessness = (parent.restlessness + partner.restlessness) / 2

    diet = parent.diet if parent.diet == partner.diet else random.choice(
        [parent.diet, partner.diet]
    )

    morphology = MorphologyGenotype.mix(parent.morphology, partner.morphology)
    development = mix_development_plans(diet, parent.development, partner.development)

    genome_blueprint, genome_mutations = _mix_parent_genome(parent, partner)
    brain_weights = _mix_brain_weights(parent, partner)

    return {
        "dna_id": parent.dna_id,
        "color": color,
        "maturity": 0.0,
        "longevity": int((parent.longevity + partner.longevity) // 2),
        "diet": diet,
        "risk_tolerance": risk,
        "restlessness": restlessness,
        "digest_efficiency_plants": (
            getattr(parent, "digest_efficiency_plants", 1.0)
            + getattr(partner, "digest_efficiency_plants", 1.0)
        )
        / 2,
        "digest_efficiency_meat": (
            getattr(parent, "digest_efficiency_meat", 1.0)
            + getattr(partner, "digest_efficiency_meat", 1.0)
        )
        / 2,
        "bite_force": (
            getattr(parent, "bite_force", settings.PLANT_BITE_NUTRITION_TARGET)
            + getattr(partner, "bite_force", settings.PLANT_BITE_NUTRITION_TARGET)
        )
        / 2,
        "tissue_hardness": (
            getattr(parent, "tissue_hardness", 0.6)
            + getattr(partner, "tissue_hardness", 0.6)
        )
        / 2,
        "morphology": morphology.to_dict(),
        "development": development,
        "genome": genome_blueprint,
        "brain_weights": brain_weights,
    }, genome_mutations


def _clone_parent_traits(parent: "Lifeform") -> Tuple[Dict[str, object], List[str]]:
    """Clone a parent's traits for asexual reproduction."""
    
    # Clone mutable structures
    morphology = parent.morphology.to_dict() # Assuming to_dict creates a copy
    development = parent.development.copy() if parent.development else {}
    
    # Clone genome
    genome_blueprint = parent.genome_blueprint.copy() if parent.genome_blueprint else {}
    # Note: Genome mutations are now handled in _mutate_offspring, not here.
    mutations = []

    brain_weights = list(parent.brain_weights) if parent.brain_weights else initialize_brain_weights()

    return {
        "dna_id": parent.dna_id,
        "color": parent.color,
        "maturity": 0.0,
        "longevity": parent.longevity,
        "diet": parent.diet,
        "risk_tolerance": parent.risk_tolerance,
        "restlessness": parent.restlessness,
        "digest_efficiency_plants": getattr(parent, "digest_efficiency_plants", 1.0),
        "digest_efficiency_meat": getattr(parent, "digest_efficiency_meat", 1.0),
        "bite_force": getattr(parent, "bite_force", settings.PLANT_BITE_NUTRITION_TARGET),
        "tissue_hardness": getattr(parent, "tissue_hardness", 0.6),
        "morphology": morphology,
        "development": development,
        "genome": genome_blueprint,
        "brain_weights": brain_weights,
    }, mutations


def _mix_parent_genome(parent: "Lifeform", partner: "Lifeform") -> Tuple[Dict[str, object], List[str]]:
    genomes: List[Genome] = []
    for candidate in (getattr(parent, "genome", None), getattr(partner, "genome", None)):
        if isinstance(candidate, Genome):
            genomes.append(candidate)
    if not genomes:
        return generate_modular_blueprint(getattr(parent, "diet", "omnivore")), []

    base = random.choice(genomes)
    genome = base
    mutations = []
    try:
        if random.randint(0, 100) < settings.MUTATION_CHANCE:
            genome, desc = mutate_genome(genome)
            mutations.append(desc)
    except MutationError:
        genome = base
    return genome.to_dict(), mutations


def _mix_brain_weights(parent: "Lifeform", partner: "Lifeform") -> List[float]:
    expected = expected_weight_count()
    candidates: List[List[float]] = []
    for source in (parent, partner):
        weights = getattr(source, "brain_weights", None)
        if isinstance(weights, list) and len(weights) == expected:
            candidates.append(weights)

    if candidates:
        # Average when both parents have valid controllers to keep behaviour smooth
        if len(candidates) == 2:
            return [
                (a + b) / 2.0
                for a, b in zip(candidates[0], candidates[1])
            ]


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
    
    # Note: width/height/health/vision/energy/attack/defence are now fully derived
    # from body graph and physics, so we don't clamp them here anymore.

    r, g, b = profile["color"]
    profile["color"] = (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )

    profile["maturity"] = max(
        settings.MIN_MATURITY, min(settings.MAX_MATURITY, int(profile["maturity"]))
    )
    profile["longevity"] = max(1, int(profile["longevity"]))
    profile["risk_tolerance"] = float(
        max(0.0, min(1.0, profile["risk_tolerance"]))
    )
    profile["restlessness"] = float(
        max(0.0, min(1.0, profile.get("restlessness", 0.5)))
    )
    profile["digest_efficiency_plants"] = max(
        0.1, min(2.0, float(profile.get("digest_efficiency_plants", 1.0)))
    )
    profile["digest_efficiency_meat"] = max(
        0.1, min(2.0, float(profile.get("digest_efficiency_meat", 1.0)))
    )
    profile["bite_force"] = max(
        2.0, min(80.0, float(profile.get("bite_force", settings.PLANT_BITE_NUTRITION_TARGET)))
    )
    profile["tissue_hardness"] = max(0.0, min(5.0, float(profile.get("tissue_hardness", 0.6))))


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

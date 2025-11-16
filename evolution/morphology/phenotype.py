"""Phenotype computation for morphology genotypes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .genotype import MorphologyGenotype, clamp_float, clamp_int


@dataclass(frozen=True)
class MorphStats:
    """Derived morphology statistics that influence gameplay systems."""

    swim_speed_multiplier: float
    turn_rate: float
    grip_strength: float
    vision_range_bonus: float
    fov_cosine_threshold: float
    perception_rays: int
    maintenance_cost: float
    mass: float
    reach: float
    collision_scale: float
    hearing_range: float
    pigment_tint: Tuple[float, float, float]


def _compute_pigment_tint(pigment: float) -> Tuple[float, float, float]:
    """Return colour multipliers to apply to the DNA base colour."""

    pigment = clamp_float(pigment, 0.0, 1.0)
    intensity = 0.7 + pigment * 0.6
    red = clamp_float(intensity, 0.5, 1.4)
    green = clamp_float(intensity * 0.95, 0.5, 1.35)
    blue = clamp_float(intensity * 0.9, 0.45, 1.3)
    return red, green, blue


def compute_morph_stats(genotype: MorphologyGenotype, base_size: Tuple[int, int]) -> MorphStats:
    """Derive gameplay stats from the provided ``genotype``."""

    width, height = base_size
    diagonal = max(1.0, (width ** 2 + height ** 2) ** 0.5)

    legs_factor = genotype.legs / 6.0
    fins_factor = genotype.fins / 4.0
    antennae_factor = genotype.antennae / 4.0
    eyes_factor = genotype.eyes / 6.0
    ears_factor = genotype.ears / 6.0
    whisker_factor = genotype.whiskers / 12.0

    swim_speed_multiplier = 0.8 + fins_factor * 0.55 - legs_factor * 0.18
    swim_speed_multiplier += max(0.0, fins_factor - 0.5) * 0.25
    swim_speed_multiplier -= max(0.0, legs_factor - 0.25) * 0.18
    swim_speed_multiplier = clamp_float(swim_speed_multiplier, 0.45, 2.2)

    turn_rate = clamp_float(0.35 + fins_factor * 0.3 + eyes_factor * 0.2, 0.2, 1.05)

    grip_strength = clamp_float(
        0.6 + legs_factor * 0.45 + whisker_factor * 0.18 - fins_factor * 0.15,
        0.35,
        2.0,
    )

    vision_range_bonus = clamp_float(
        diagonal * (0.25 + eyes_factor * 0.4 + antennae_factor * 0.45),
        0.0,
        220.0,
    )

    fov_cosine_threshold = clamp_float(0.25 + eyes_factor * 0.5 + antennae_factor * 0.2, 0.05, 0.95)

    perception_rays = clamp_int(6 + genotype.eyes * 2 + genotype.antennae, 4, 28)

    maintenance_cost = clamp_float(
        0.18
        + genotype.legs * 0.06
        + genotype.fins * 0.08
        + genotype.antennae * 0.05
        + genotype.ears * 0.04
        + genotype.whiskers * 0.03,
        0.12,
        3.5,
    )

    mass = clamp_float(
        1.0
        + genotype.legs * 0.25
        + genotype.fins * 0.3
        + genotype.antennae * 0.12
        + genotype.ears * 0.1
        + genotype.whiskers * 0.05,
        0.8,
        6.0,
    )

    reach = clamp_float(4.0 + genotype.whiskers * 0.5 + genotype.legs * 0.35, 3.0, 12.0)

    collision_scale = clamp_float(1.0 + mass * 0.04 - fins_factor * 0.05, 0.8, 1.8)

    hearing_range = clamp_float(antennae_factor * 40.0 + ears_factor * 70.0, 0.0, 240.0)

    pigment_tint = _compute_pigment_tint(genotype.pigment)

    return MorphStats(
        swim_speed_multiplier=swim_speed_multiplier,
        turn_rate=turn_rate,
        grip_strength=grip_strength,
        vision_range_bonus=vision_range_bonus,
        fov_cosine_threshold=fov_cosine_threshold,
        perception_rays=perception_rays,
        maintenance_cost=maintenance_cost,
        mass=mass,
        reach=reach,
        collision_scale=collision_scale,
        hearing_range=hearing_range,
        pigment_tint=pigment_tint,
    )

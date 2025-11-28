"""Seed population templates built around a neutral common ancestor.

This module centralises the small set of base DNA templates used when the
simulation boots. Every initial creature is a lightly mutated clone of one of
these templates so that diversity emerges from mutation rather than bespoke
behaviour code or predator/prey roles.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from ..config import settings
from ..dna.development import generate_development_plan
from ..dna.factory import build_body_graph, serialize_body_graph
from ..dna.genes import Genome, GenomeConstraints, ModuleGene
from ..dna.mutation import MutationError, mutate_genome
from ..entities.neural_controller import (
    initialize_brain_weights,
    mutate_brain_weights,
)
from ..morphology.genotype import MorphologyGenotype


Color = Tuple[int, int, int]


@dataclass(frozen=True)
class BaseDNATemplate:
    key: str
    label: str
    genome: Genome
    color: Color
    morphology: MorphologyGenotype
    diet: str = "omnivore"
    maturity: int = 90
    vision: int = 110
    energy: int = 100
    health: int = 120
    longevity: int = 2600
    defence_power: int = 48
    attack_power: int = 42
    social: float = 0.55
    boid_tendency: float = 0.55
    risk_tolerance: float = 0.45
    restlessness: float = 0.42
    base_brain: Sequence[float] = ()

    def spawn_profile(self, dna_id: int, rng: random.Random) -> dict:
        """Clone the template with small body + brain mutations."""

        genome = self.genome
        try:
            genome = mutate_genome(genome, rng=rng)
        except MutationError:
            pass

        try:
            graph, geometry = build_body_graph(genome, include_geometry=True)
        except Exception:
            graph, geometry = build_body_graph(self.genome, include_geometry=True)
        blueprint = serialize_body_graph(graph).to_dict()

        brain_seed = list(self.base_brain) or initialize_brain_weights(rng)
        brain = mutate_brain_weights(
            brain_seed, rng=rng, sigma=0.06, mutation_rate=0.22
        )

        color = _jitter_color(self.color, rng)
        development = generate_development_plan(self.diet)
        morphology = self.morphology.mutate(rng)

        profile = {
            "dna_id": dna_id,
            "base_form": self.key,
            "base_form_label": self.label,
            "width": settings.MIN_WIDTH,
            "height": settings.MIN_HEIGHT,
            "color": color,
            "health": self.health,
            "maturity": self.maturity,
            "vision": self.vision,
            "defence_power": self.defence_power,
            "attack_power": self.attack_power,
            "energy": self.energy,
            "longevity": self.longevity,
            "diet": self.diet,
            "social": self.social,
            "boid_tendency": self.boid_tendency,
            "risk_tolerance": self.risk_tolerance,
            "restlessness": self.restlessness,
            "morphology": morphology.to_dict(),
            "development": development,
            "genome": blueprint,
            "brain_weights": brain,
            "guaranteed_spawn": True,
        }

        if settings.USE_BODYGRAPH_SIZE and geometry:
            radius = float(geometry.get("collision_radius") or 8.0)
            width_m = geometry.get("width", settings.MIN_WIDTH / settings.BODY_PIXEL_SCALE)
            height_m = geometry.get("height", settings.MIN_HEIGHT / settings.BODY_PIXEL_SCALE)
            profile["width"] = int(round(width_m * settings.BODY_PIXEL_SCALE))
            profile["height"] = int(round(height_m * settings.BODY_PIXEL_SCALE))
            profile["collision_radius"] = radius
            profile["geometry"] = geometry

        return profile


def base_templates(rng: random.Random, *, count: int) -> List[BaseDNATemplate]:
    """Return the requested number of neutral base templates."""

    templates: List[BaseDNATemplate] = [_common_ancestor(rng)]
    optional_variants = [_ray_variant(rng), _keel_variant(rng)]

    if count > 1:
        idx = 0
        while len(templates) < count and optional_variants:
            templates.append(optional_variants[idx % len(optional_variants)])
            idx += 1

    return templates[:count]


def _common_ancestor(rng: random.Random) -> BaseDNATemplate:
    """Small symmetric body with paired fins and a central thruster."""

    genes = {
        "core": ModuleGene("core", "core", {}),
        "head": ModuleGene("head", "head", {}, parent="core", slot="head_socket"),
        "mouth": ModuleGene("mouth", "mouth", {}, parent="head", slot="mouth_socket"),
        "eye": ModuleGene("eye", "eye", {}, parent="head", slot="cranial_sensor"),
        "thruster": ModuleGene("thruster", "propulsion", {}, parent="core", slot="ventral_core"),
        "fin_left": ModuleGene(
            "fin_left",
            "limb",
            {"variant": "fin"},
            parent="core",
            slot="lateral_mount_left",
        ),
        "fin_right": ModuleGene(
            "fin_right",
            "limb",
            {"variant": "fin"},
            parent="core",
            slot="lateral_mount_right",
        ),
    }
    genome = Genome(genes=genes, constraints=GenomeConstraints(max_mass=160.0, nerve_capacity=20.0))
    morphology = MorphologyGenotype(legs=0, fins=2, antennae=1, eyes=2, ears=1, whiskers=0, pigment=0.55)
    color = (rng.randint(90, 140), rng.randint(150, 210), rng.randint(160, 220))
    return BaseDNATemplate(
        key="common_ancestor",
        label="Common Ancestor",
        genome=genome,
        color=color,
        morphology=morphology,
        base_brain=initialize_brain_weights(rng),
    )


def _ray_variant(rng: random.Random) -> BaseDNATemplate:
    """Wide pectoral fins and a lower thruster for glide-biased bodies."""

    genes = {
        "core": ModuleGene("core", "core", {"material": "bio-alloy"}),
        "head": ModuleGene("head", "head", {}, parent="core", slot="head_socket"),
        "mouth": ModuleGene("mouth", "mouth", {}, parent="head", slot="mouth_socket"),
        "sensor": ModuleGene("sensor", "sensor", {"spectrum": ["light", "colour"]}, parent="head", slot="cranial_sensor"),
        "thruster": ModuleGene("thruster", "propulsion", {"fuel_efficiency": 0.9}, parent="core", slot="ventral_core"),
        "fin_left": ModuleGene(
            "fin_left",
            "limb",
            {"variant": "fin"},
            parent="core",
            slot="caudal_tentacle_left",
        ),
        "fin_right": ModuleGene(
            "fin_right",
            "limb",
            {"variant": "fin"},
            parent="core",
            slot="caudal_tentacle_right",
        ),
        "dorsal": ModuleGene("dorsal", "limb", {"variant": "fin_dorsal"}, parent="core", slot="dorsal_mount"),
    }
    genome = Genome(genes=genes, constraints=GenomeConstraints(max_mass=170.0, nerve_capacity=22.0))
    morphology = MorphologyGenotype(legs=0, fins=3, antennae=1, eyes=1, ears=1, whiskers=0, pigment=0.48)
    color = (rng.randint(80, 120), rng.randint(180, 220), rng.randint(150, 210))
    return BaseDNATemplate(
        key="ray_variant",
        label="Ray Variant",
        genome=genome,
        color=color,
        morphology=morphology,
        base_brain=initialize_brain_weights(rng),
    )


def _keel_variant(rng: random.Random) -> BaseDNATemplate:
    """Compact round core with keel fins hugging the centre of mass."""

    genes = {
        "core": ModuleGene("core", "round_core", {"variant": "compact"}),
        "head": ModuleGene("head", "head", {}, parent="core", slot="head_socket"),
        "eye": ModuleGene("eye", "eye", {}, parent="head", slot="cranial_sensor"),
        "mouth": ModuleGene("mouth", "mouth", {}, parent="head", slot="mouth_socket"),
        # RoundCore uses different attachment slots than TrunkCore.
        # Ventral propulsion mounts on the ventral_socket and fins anchor to radial mounts.
        "thruster": ModuleGene(
            "thruster",
            "propulsion",
            {"power_output": 28.0},
            parent="core",
            slot="ventral_socket",
        ),
        "fin_left": ModuleGene(
            "fin_left",
            "limb",
            {"variant": "fin"},
            parent="core",
            slot="radial_1",
        ),
        "fin_right": ModuleGene(
            "fin_right",
            "limb",
            {"variant": "fin"},
            parent="core",
            slot="radial_2",
        ),
    }
    genome = Genome(genes=genes, constraints=GenomeConstraints(max_mass=150.0, nerve_capacity=18.0))
    morphology = MorphologyGenotype(legs=0, fins=2, antennae=0, eyes=2, ears=1, whiskers=0, pigment=0.6)
    color = (rng.randint(100, 150), rng.randint(130, 190), rng.randint(200, 240))
    return BaseDNATemplate(
        key="keel_variant",
        label="Keel Variant",
        genome=genome,
        color=color,
        morphology=morphology,
        base_brain=initialize_brain_weights(rng),
    )


def _jitter_color(color: Color, rng: random.Random) -> Color:
    return tuple(max(0, min(255, int(channel + rng.gauss(0, 6.5)))) for channel in color)


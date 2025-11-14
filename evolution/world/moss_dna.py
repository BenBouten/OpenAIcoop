"""DNA helpers for moss cells."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple

import random

from ..config import settings

Color = Tuple[int, int, int]


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _clamp_color(channel: float) -> int:
    return int(_clamp(channel, 24, 220))


@dataclass(frozen=True)
class MossDNA:
    """Encodes moss traits that affect growth and nutrition."""

    growth_rate: float
    toxicity: float
    nutrition: float
    hydration: float
    vitality: float
    fiber_density: float
    color: Color

    def mutated(
        self,
        rng: random.Random,
        chance: float | None = None,
        strength: float | None = None,
    ) -> "MossDNA":
        """Return a mutated copy of this DNA."""

        chance = settings.MOSS_MUTATION_CHANCE if chance is None else chance
        strength = settings.MOSS_MUTATION_STRENGTH if strength is None else strength

        if chance <= 0.0:
            return self

        def maybe_mutate(value: float, minimum: float, maximum: float, scale: float = 1.0) -> float:
            if rng.random() < chance:
                value += rng.uniform(-strength, strength) * scale
            return _clamp(value, minimum, maximum)

        growth_rate = maybe_mutate(self.growth_rate, 0.5, 1.8, scale=0.6)
        toxicity = maybe_mutate(self.toxicity, 0.0, 0.8, scale=0.4)
        nutrition = maybe_mutate(self.nutrition, 4.0, 18.0, scale=4.0)
        hydration = maybe_mutate(self.hydration, 0.0, 1.0, scale=0.5)
        vitality = maybe_mutate(self.vitality, 0.0, 1.0, scale=0.5)
        fiber_density = maybe_mutate(self.fiber_density, 0.4, 1.8, scale=0.5)

        if rng.random() < chance:
            r = _clamp_color(self.color[0] + rng.randint(-18, 18))
            g = _clamp_color(self.color[1] + rng.randint(-18, 18))
            b = _clamp_color(self.color[2] + rng.randint(-18, 18))
            color = (r, g, b)
        else:
            color = self.color

        return MossDNA(
            growth_rate=growth_rate,
            toxicity=toxicity,
            nutrition=nutrition,
            hydration=hydration,
            vitality=vitality,
            fiber_density=fiber_density,
            color=color,
        )


def random_moss_dna(rng: random.Random) -> MossDNA:
    """Generate a new random moss DNA profile."""

    base_green = rng.randint(90, 170)
    color = (
        _clamp_color(base_green - rng.randint(10, 40)),
        _clamp_color(base_green + rng.randint(0, 40)),
        _clamp_color(base_green - rng.randint(0, 35)),
    )
    return MossDNA(
        growth_rate=rng.uniform(0.8, 1.6),
        toxicity=rng.uniform(0.0, 0.45),
        nutrition=rng.uniform(6.0, 16.0),
        hydration=rng.uniform(0.1, 0.9),
        vitality=rng.uniform(0.0, 0.8),
        fiber_density=rng.uniform(0.7, 1.4),
        color=color,
    )


def average_dna(dnas: Sequence[MossDNA], rng: random.Random) -> MossDNA:
    """Blend DNA from neighbouring cells and mutate the result."""

    if not dnas:
        return random_moss_dna(rng)

    count = float(len(dnas))
    growth_rate = sum(d.growth_rate for d in dnas) / count
    toxicity = sum(d.toxicity for d in dnas) / count
    nutrition = sum(d.nutrition for d in dnas) / count
    hydration = sum(d.hydration for d in dnas) / count
    vitality = sum(d.vitality for d in dnas) / count
    fiber_density = sum(d.fiber_density for d in dnas) / count
    color = (
        _clamp_color(sum(d.color[0] for d in dnas) / count),
        _clamp_color(sum(d.color[1] for d in dnas) / count),
        _clamp_color(sum(d.color[2] for d in dnas) / count),
    )

    blended = MossDNA(
        growth_rate=growth_rate,
        toxicity=toxicity,
        nutrition=nutrition,
        hydration=hydration,
        vitality=vitality,
        fiber_density=fiber_density,
        color=color,
    )
    return blended.mutated(rng)


def ensure_dna_for_cells(cells: Iterable[Tuple[int, int]], rng: random.Random) -> dict[Tuple[int, int], MossDNA]:
    """Assign moss DNA to a set of cells, introducing minor variations."""

    base = random_moss_dna(rng)
    dna_map: dict[Tuple[int, int], MossDNA] = {}
    for gx, gy in cells:
        mutated = base.mutated(rng, chance=settings.MOSS_MUTATION_CHANCE * 0.5)
        dna_map[(int(gx), int(gy))] = mutated
    return dna_map


__all__ = [
    "MossDNA",
    "average_dna",
    "ensure_dna_for_cells",
    "random_moss_dna",
]

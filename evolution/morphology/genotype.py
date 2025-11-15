"""Definitions for morphological genotypes used by lifeforms."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, MutableMapping, Optional


def clamp_int(value: int, minimum: int, maximum: int) -> int:
    """Clamp ``value`` between ``minimum`` and ``maximum`` (inclusive)."""

    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def clamp_float(value: float, minimum: float, maximum: float) -> float:
    """Clamp a floating point value between the provided bounds."""

    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


@dataclass(frozen=True)
class MorphologyGenotype:
    """Compact representation of an organism's organs."""

    legs: int
    fins: int
    antennae: int
    eyes: int
    ears: int
    whiskers: int
    pigment: float

    @classmethod
    def random(cls, rng: Optional[random.Random] = None) -> "MorphologyGenotype":
        """Create a random genotype using the provided ``rng`` (or :mod:`random`)."""

        rng = rng or random
        return cls(
            legs=rng.randint(0, 6),
            fins=rng.randint(0, 4),
            antennae=rng.randint(0, 3),
            eyes=rng.randint(1, 5),
            ears=rng.randint(0, 4),
            whiskers=rng.randint(0, 6),
            pigment=rng.uniform(0.0, 1.0),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "MorphologyGenotype":
        """Build a genotype from a mapping, falling back to safe defaults."""

        if not data:
            return cls(
                legs=2,
                fins=0,
                antennae=1,
                eyes=2,
                ears=1,
                whiskers=0,
                pigment=0.5,
            )

        def _get_int(key: str, default: int) -> int:
            value = int(data.get(key, default))
            if key == "eyes":
                return clamp_int(value, 1, 8)
            return clamp_int(value, 0, 12)

        pigment_value = float(data.get("pigment", 0.5))
        pigment_value = clamp_float(pigment_value, 0.0, 1.0)

        return cls(
            legs=_get_int("legs", 2),
            fins=_get_int("fins", 0),
            antennae=_get_int("antennae", 1),
            eyes=_get_int("eyes", 2),
            ears=_get_int("ears", 1),
            whiskers=_get_int("whiskers", 0),
            pigment=pigment_value,
        )

    def to_dict(self) -> Dict[str, object]:
        """Serialize the genotype to a dictionary that can be stored in DNA."""

        return {
            "legs": int(self.legs),
            "fins": int(self.fins),
            "antennae": int(self.antennae),
            "eyes": int(self.eyes),
            "ears": int(self.ears),
            "whiskers": int(self.whiskers),
            "pigment": float(self.pigment),
        }

    def mutate(self, rng: Optional[random.Random] = None) -> "MorphologyGenotype":
        """Return a mutated copy of the genotype."""

        rng = rng or random

        def _mutate_int(value: int, minimum: int, maximum: int, strength: int = 1) -> int:
            if rng.randint(0, 100) < 18:
                delta = rng.randint(-strength, strength)
                return clamp_int(value + delta, minimum, maximum)
            return value

        legs = _mutate_int(self.legs, 0, 6)
        fins = _mutate_int(self.fins, 0, 4)
        antennae = _mutate_int(self.antennae, 0, 4)
        eyes = _mutate_int(self.eyes, 1, 8)
        ears = _mutate_int(self.ears, 0, 6)
        whiskers = _mutate_int(self.whiskers, 0, 12, strength=2)

        pigment = self.pigment
        if rng.randint(0, 100) < 22:
            pigment += rng.uniform(-0.12, 0.12)
            pigment = clamp_float(pigment, 0.0, 1.0)

        return MorphologyGenotype(
            legs=legs,
            fins=fins,
            antennae=antennae,
            eyes=eyes,
            ears=ears,
            whiskers=whiskers,
            pigment=pigment,
        )

    @classmethod
    def mix(
        cls,
        a: "MorphologyGenotype",
        b: "MorphologyGenotype",
        rng: Optional[random.Random] = None,
    ) -> "MorphologyGenotype":
        """Combine two genotypes using deterministic averaging with variation."""

        rng = rng or random

        def _blend_int(values: Iterable[int], minimum: int, maximum: int) -> int:
            values_tuple = tuple(values)
            total = sum(values_tuple)
            count = len(values_tuple)
            avg = total / float(count or 1)
            if rng.randint(0, 1):
                blended = int(round(avg))
            else:
                blended = int(avg)
            return clamp_int(blended, minimum, maximum)

        legs = _blend_int((a.legs, b.legs), 0, 6)
        fins = _blend_int((a.fins, b.fins), 0, 4)
        antennae = _blend_int((a.antennae, b.antennae), 0, 4)
        eyes = _blend_int((a.eyes, b.eyes), 1, 8)
        ears = _blend_int((a.ears, b.ears), 0, 6)
        whiskers = _blend_int((a.whiskers, b.whiskers), 0, 12)
        pigment = clamp_float((a.pigment + b.pigment) / 2.0, 0.0, 1.0)

        return cls(
            legs=legs,
            fins=fins,
            antennae=antennae,
            eyes=eyes,
            ears=ears,
            whiskers=whiskers,
            pigment=pigment,
        )


def mutate_profile_morphology(profile: MutableMapping[str, object]) -> None:
    """Mutate the ``profile['morphology']`` entry in-place."""

    genotype = MorphologyGenotype.from_mapping(
        profile.get("morphology", {})  # type: ignore[arg-type]
    )
    mutated = genotype.mutate()
    profile["morphology"] = mutated.to_dict()

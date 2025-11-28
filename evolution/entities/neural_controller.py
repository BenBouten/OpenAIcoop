"""Minimal feedforward neural controller for lifeforms.

The controller exposes a fixed topology so we can flatten
weights into DNA and mutate them without touching runtime code.
"""
from __future__ import annotations

import math
import random
from typing import Iterable, List, Sequence


INPUT_KEYS: Sequence[str] = (
    "food_density_forward",
    "food_density_left",
    "food_density_right",
    "depth_norm",
    "energy_ratio",
    "neighbor_density",
    "vertical_velocity",
    "speed",
    "noise",
    "buoyancy_bias",
)

OUTPUT_KEYS: Sequence[str] = (
    "tail_thrust",
    "left_fin_thrust",
    "right_fin_thrust",
    "vertical_thrust",
    "bite_intent",
    "lum_intensity",
    "lum_pattern_mod",
)

# Small fixed network: Input -> Hidden(12) -> Output
HIDDEN_SIZES: Sequence[int] = (12,)


def expected_weight_count() -> int:
    """Return the flattened parameter count for the fixed topology."""

    count = 0
    prev = len(INPUT_KEYS)
    for size in HIDDEN_SIZES:
        count += (prev + 1) * size  # +1 for bias
        prev = size
    count += (prev + 1) * len(OUTPUT_KEYS)
    return count


def initialize_brain_weights(rng: random.Random | None = None) -> List[float]:
    rng = rng or random
    scale = 0.5
    return [rng.gauss(0.0, scale) for _ in range(expected_weight_count())]


def mutate_brain_weights(
    weights: Sequence[float],
    *,
    rng: random.Random | None = None,
    sigma: float = 0.1,
    mutation_rate: float = 0.1,
) -> List[float]:
    rng = rng or random
    mutated = list(weights)
    for i, value in enumerate(mutated):
        if rng.random() < mutation_rate:
            mutated[i] = float(value + rng.gauss(0.0, sigma))
    return mutated


class NeuralController:
    """Simple tanh network with fixed topology."""

    def __init__(self, weights: Sequence[float] | None = None) -> None:
        if weights is None:
            weights = initialize_brain_weights()
        expected = expected_weight_count()
        if len(weights) != expected:
            raise ValueError(f"Expected {expected} weights, got {len(weights)}")
        self.weights = list(weights)

    def forward(self, inputs: Iterable[float]) -> List[float]:
        x = list(inputs)
        if len(x) != len(INPUT_KEYS):
            raise ValueError(
                f"Expected {len(INPUT_KEYS)} inputs, received {len(x)}"
            )
        values = x
        offset = 0
        prev_size = len(INPUT_KEYS)

        for size in HIDDEN_SIZES:
            layer_weights = self.weights[offset : offset + (prev_size + 1) * size]
            offset += (prev_size + 1) * size
            values = self._activate_layer(values, layer_weights, prev_size)
            prev_size = size

        output_weights = self.weights[offset : offset + (prev_size + 1) * len(OUTPUT_KEYS)]
        outputs = self._activate_layer(values, output_weights, prev_size)
        return outputs

    @staticmethod
    def _activate_layer(inputs: List[float], weights: Sequence[float], input_size: int) -> List[float]:
        outputs: List[float] = []
        stride = input_size + 1
        for neuron_idx in range(0, len(weights), stride):
            bias = weights[neuron_idx + input_size]
            acc = bias
            for i, value in enumerate(inputs):
                acc += value * weights[neuron_idx + i]
            outputs.append(math.tanh(acc))
        return outputs

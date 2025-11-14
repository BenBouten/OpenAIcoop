"""Environment synchronisation helpers for the simulation."""

from __future__ import annotations

import math

from .state import SimulationState


def sync_food_abundance(state: SimulationState) -> None:
    """Update plant carrying capacity when the abundance modifier changes."""

    current = state.environment_modifiers.get("plant_regrowth", 1.0)
    if math.isclose(current, state.last_plant_regrowth, rel_tol=1e-4, abs_tol=1e-6):
        return

    state.last_plant_regrowth = current
    if state.world is not None:
        state.world.set_environment_modifiers(state.environment_modifiers)

    for plant in state.plants:
        plant.set_capacity_multiplier(current)


def sync_moss_growth_speed(state: SimulationState) -> None:
    """Propagate moss growth speed updates to every plant instance."""

    current = state.environment_modifiers.get("moss_growth_speed", 1.0)
    if math.isclose(current, state.last_moss_growth_speed, rel_tol=1e-4, abs_tol=1e-6):
        return

    state.last_moss_growth_speed = current
    for plant in state.plants:
        plant.set_growth_speed_modifier(current)

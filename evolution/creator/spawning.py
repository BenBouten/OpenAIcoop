"""Spawning logic for creature templates."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ..dna.factory import serialize_body_graph
from ..dna.factory import serialize_body_graph
from ..dna.genes import Genome
from .templates import CreatureDraft, CreatureTemplate

if TYPE_CHECKING:
    from ..simulation.state import SimulationState
    from ..world.world import World
    from ..entities.lifeform import Lifeform


def spawn_template(state: SimulationState, template: CreatureTemplate, world: "World") -> None:
    """Spawn a new lifeform based on the provided template."""
    from ..entities.lifeform import Lifeform

    
    # 1. Build the body graph from the template
    draft = CreatureDraft(template)
    graph = draft.build_graph()
    
    # 2. Serialize to Genome
    genome = serialize_body_graph(graph)
    
    # 3. Create DNA profile
    # We generate a deterministic but unique-ish DNA ID
    dna_id = abs(hash(template.name)) % 1000000
    
    dna_profile = {
        "dna_id": dna_id,
        "color": (100, 100, 100), # Will be overridden by morphology/genome
        "maturity": 100,
        "longevity": 1000,
        "genome": genome.to_dict(),
        "diet": "omnivore", # Default
        "social": 0.5,
    }
    
    # 4. Spawn in the world
    # Find a safe spot or just center for now
    x = world.width / 2 + random.uniform(-100, 100)
    y = world.height / 2 + random.uniform(-100, 100)
    
    lifeform = Lifeform(state, x, y, dna_profile, 1)
    state.lifeforms.append(lifeform)

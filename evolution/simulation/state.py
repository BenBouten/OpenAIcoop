from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class SimulationState:
    lifeforms: List = field(default_factory=list)
    plants: List = field(default_factory=list)
    pheromones: List = field(default_factory=list)
    world: 'World' = None
    camera: 'Camera' = None
    notifications: 'NotificationManager' = None
    notification_context: object = None
    events: 'EventManager' = None
    player: 'PlayerController' = None
    environment_modifiers: dict = field(default_factory=lambda: {
        "plant_regrowth": 1.0,
        "hunger_rate": 1.0,
    })
    death_ages: List[int] = field(default_factory=list)
    dna_profiles: List[dict] = field(default_factory=list)
    dna_home_biome: dict = field(default_factory=dict)
    dna_id_counts: Dict[str, int] = field(default_factory=dict)
    dna_lineage: Dict[str, dict] = field(default_factory=dict)
    lifeform_genetics: Dict[str, dict] = field(default_factory=dict)
    lifeform_id_counter: int = 0

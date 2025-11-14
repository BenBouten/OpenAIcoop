from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class SimulationState:
    lifeforms: List = field(default_factory=list)
    plants: List = field(default_factory=list)
    pheromones: List = field(default_factory=list)
    world: 'World' = None
    world_type: str = "Rift Valley"
    camera: 'Camera' = None
    notifications: 'NotificationManager' = None
    notification_context: object = None
    events: 'EventManager' = None
    player: 'PlayerController' = None
    environment_modifiers: dict = field(default_factory=lambda: {
        "plant_regrowth": 1.0,
        "hunger_rate": 1.0,
        "weather_intensity": 1.0,
        "moss_growth_speed": 1.0,
    })
    gameplay_settings: Dict[str, float] = field(
        default_factory=lambda: {
            "pheromone_decay": 10.0,
            "pheromone_strength": 90.0,
            "pheromone_evaporation_rate": 12.0,
            "follow_trail_chance": 0.65,
            "home_return_speed_multiplier": 1.35,
        }
    )
    death_ages: List[int] = field(default_factory=list)
    dna_profiles: List[dict] = field(default_factory=list)
    dna_home_biome: dict = field(default_factory=dict)
    dna_home_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    dna_id_counts: Dict[str, int] = field(default_factory=dict)
    dna_lineage: Dict[str, dict] = field(default_factory=dict)
    lifeform_genetics: Dict[str, dict] = field(default_factory=dict)
    lifeform_id_counter: int = 0
    nest_scores: Dict[str, int] = field(default_factory=dict)
    colony_roots: Dict[str, str] = field(default_factory=dict)
    colony_ids: List[str] = field(default_factory=list)
    colony_colors: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)
    colony_labels: Dict[str, str] = field(default_factory=dict)


from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - imported for type hints only
    from ..rendering.effects import EffectManager
    from ..entities.lifeform import Lifeform


@dataclass
class SimulationState:
    lifeforms: List = field(default_factory=list)
    plants: List = field(default_factory=list)
    world: 'World' = None
    world_type: str = "Rift Valley"
    camera: 'Camera' = None
    notifications: 'NotificationManager' = None
    notification_context: object = None
    events: 'EventManager' = None
    player: 'PlayerController' = None
    effects: 'EffectManager' = None
    environment_modifiers: dict = field(
        default_factory=lambda: {
            "plant_regrowth": 1.0,
            "hunger_rate": 1.0,
            "weather_intensity": 1.0,
            "moss_growth_speed": 1.0,
        }
    )
    last_plant_regrowth: float = 1.0
    last_moss_growth_speed: float = 1.0
    death_ages: List[int] = field(default_factory=list)
    dna_profiles: List[dict] = field(default_factory=list)
    dna_home_biome: dict = field(default_factory=dict)
    dna_id_counts: Dict[str, int] = field(default_factory=dict)
    dna_lineage: Dict[str, dict] = field(default_factory=dict)
    lifeform_genetics: Dict[str, dict] = field(default_factory=dict)
    lifeform_id_counter: int = 0
    selected_lifeform: Optional['Lifeform'] = None
    last_debug_log_path: Optional[str] = None

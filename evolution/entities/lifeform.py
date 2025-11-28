"""Lifeform entity logic extracted from the simulation module.

This class owns:
- DNA-based attributes and species characteristics
- Local memory (food, threats, partners, visited)
- Behaviour / AI decisions (who to flee, hunt, follow, etc.)
- Grouping logic, combat stats, reproduction and progression

Generic movement / collision resolution should be done in `movement.py`,
which coordinates with the dedicated `ai` and `combat` modules.
"""

from __future__ import annotations

import logging
import math
import random
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple, TYPE_CHECKING

import pygame
from pygame.math import Vector2

from ..config import settings
from ..dna.blueprints import generate_modular_blueprint
from ..dna.development import describe_skin_stage, ensure_development_plan
from ..dna.factory import build_body_graph
from ..dna.genes import Genome, ensure_genome
from ..morphology import MorphologyGenotype, MorphStats, compute_morph_stats
from ..physics.physics_body import PhysicsBody, build_physics_body
from ..physics.physics_body import PhysicsBody, build_physics_body
from ..world.advanced_carcass import DecomposingCarcass
from ..world.world import BiomeRegion
from . import reproduction
from .locomotion import LocomotionProfile, derive_locomotion_profile
from ..systems.telemetry import log_event

if TYPE_CHECKING:
    from ..simulation.state import SimulationState

logger = logging.getLogger("evolution.simulation")

_GRAVITY = 9.81  # m/s² - used for buoyancy diagnostics


class BehaviorMode:
    IDLE = "idle"
    SEARCH = "search"
    FLEE = "flee"
    HUNT = "hunt"
    FLOCK = "flock"
    INTERACT = "interact"


class Lifeform:
    def __init__(
        self,
        state: SimulationState,
        x: float,
        y: float,
        dna_profile: dict,
        generation: int,
        parents: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self.state = state

        # Position & direction
        self.x = x
        self.y = y
        self.x_direction = 0.0
        self.y_direction = 0.0
        self.velocity = Vector2()

        # Movement / Physics state
        self.thrust_phase = random.uniform(0, 6.28)  # Random start phase for oscillation
        self.adrenaline_factor = 0.0
        self.current_behavior_mode = BehaviorMode.IDLE
        self.target_behavior_mode = BehaviorMode.IDLE


        # Core DNA / stats
        self.dna_id = dna_profile["dna_id"]
        base_color = tuple(int(c) for c in dna_profile["color"])
        self.maturity = int(dna_profile["maturity"])
        self.longevity = int(dna_profile["longevity"])
        self.generation = generation
        self.morphology: MorphologyGenotype = MorphologyGenotype.from_mapping(
            dna_profile.get("morphology", {})
        )
        self.fin_count = getattr(self.morphology, "fins", 0)
        self.morph_stats: MorphStats = compute_morph_stats(
            self.morphology, (32, 32)  # Placeholder base size, will be overwritten
        )
        raw_geometry = dna_profile.get("geometry")
        self.profile_geometry: Dict[str, float] = dict(raw_geometry) if isinstance(raw_geometry, dict) else {}
        self._initialise_body(dna_profile)
        self.development = ensure_development_plan(dna_profile.get("development"))
        self.skin_stage = int(self.development.get("skin_stage", 0))
        self.development_features: Tuple[str, ...] = tuple(
            self.development.get("features", [])
        )
        self.base_form: Optional[str] = dna_profile.get("base_form")
        self.base_form_label: Optional[str] = dna_profile.get("base_form_label")
        tinted = self._apply_pigment(base_color, self.morph_stats.pigment_tint)
        self.body_color = self._apply_skin_development(tinted)
        self.color = self.body_color

        # Feeding traits
        self.digest_efficiency_plants = float(
            dna_profile.get("digest_efficiency_plants", 1.0)
        )
        self.digest_efficiency_meat = float(dna_profile.get("digest_efficiency_meat", 1.0))
        self.bite_force = float(
            dna_profile.get("bite_force", settings.PLANT_BITE_NUTRITION_TARGET)
        )
        self.tissue_hardness = float(dna_profile.get("tissue_hardness", 0.6))
        self.bite_intent = 0.0

        # Derive physical stats from the body graph
        self._derive_stats_from_body()

        scaled_width = int(round(self.base_width * self.morph_stats.collision_scale))
        scaled_height = int(round(self.base_height * self.morph_stats.collision_scale))
        self.width = max(1, scaled_width)
        self.height = max(1, scaled_height)

        adjusted_vision = self.vision + self.morph_stats.vision_range_bonus
        self.vision = max(
            float(settings.VISION_MIN),
            min(float(settings.VISION_MAX), adjusted_vision),
        )
        self.sensory_range = self.vision
        self.perception_rays = self.morph_stats.perception_rays
        self.hearing_range = self.morph_stats.hearing_range
        physics = self.physics_body
        self.body_module_count = len(getattr(self, "body_graph", []))
        self.body_mass = physics.mass
        self.body_volume = physics.volume
        self.body_density = physics.density
        self.body_drag = physics.drag_coefficient
        self.max_thrust = physics.max_thrust
        self.body_energy_cost = physics.energy_cost
        self.body_power_output = physics.power_output
        self.body_grip_strength = physics.grip_strength
        self.lift_per_fin = getattr(physics, "lift_per_fin", 0.0)
        self.buoyancy_offsets = getattr(physics, "buoyancy_offsets", (0.0, 0.0))
        self.buoyancy_volume = physics.buoyancy_volume
        self.tentacle_grip = getattr(physics, "tentacle_grip", 0.0)
        self.tentacle_span = getattr(self, "tentacle_span", getattr(physics, "tentacle_span", 0.0))
        self.tentacle_reach = getattr(self, "tentacle_reach", getattr(physics, "tentacle_reach", 0.0))
        self.tentacle_count = getattr(self, "tentacle_count", getattr(physics, "tentacle_count", 0))
        self.tentacle_grip_bonus = getattr(self, "tentacle_grip_bonus", getattr(physics, "tentacle_grip", 0.0))
        self.mass = self._scaled_mass(self.body_mass)
        self.reach = self.morph_stats.reach
        morph_maintenance = self.morph_stats.maintenance_cost
        self.maintenance_cost = max(
            morph_maintenance, 0.12 + self.body_energy_cost * 0.05
        )
        self.speed_multiplier = self.morph_stats.swim_speed_multiplier
        self.grip_strength = self.morph_stats.grip_strength
        self.turn_rate = max(0.05, self.morph_stats.turn_rate)
        self.fov_threshold = self.morph_stats.fov_cosine_threshold
        fins = getattr(self.morphology, "fins", 0)
        legs = getattr(self.morphology, "legs", 0)
        base_propulsion = max(0.4, min(1.6, 0.75 + fins * 0.12 - legs * 0.04))
        thrust_ratio = self.max_thrust / max(8.0, self.body_mass)
        self.propulsion_efficiency = max(0.4, min(1.8, base_propulsion * (0.65 + thrust_ratio * 0.15)))
        self.speed_multiplier = max(0.4, min(2.5, self.speed_multiplier * (0.7 + thrust_ratio * 0.2)))
        scaled_grip = self._scaled_grip(self.body_grip_strength)
        if scaled_grip > self.grip_strength:
            self.grip_strength = scaled_grip
        self._locomotion_drag_multiplier = 1.0
        self.volume = max(1.0, self.body_volume)
        self.drag_coefficient = max(0.05, self.body_drag)
        self.max_swim_speed = max(45.0, thrust_ratio * 32.0)
        self.last_fluid_properties = None
        self.sensor_suite = self._derive_sensor_suite()
        self._apply_sensor_baselines(self.sensor_suite)
        self.body_module_breakdown = self._summarize_modules()
        self._sensor_target_ranges = self._compute_sensor_target_ranges(self.sensor_suite)

        self.locomotion_profile: LocomotionProfile = derive_locomotion_profile(
            dna_profile,
            self.morphology,
            self.morph_stats,
        )
        self.locomotion_strategy = self.locomotion_profile.key
        self.locomotion_label = self.locomotion_profile.label
        self.locomotion_description = self.locomotion_profile.description
        self.depth_bias = self.locomotion_profile.depth_bias
        self.drift_preference = self.locomotion_profile.drift_preference
        self.motion_energy_cost = self.locomotion_profile.energy_cost + self.body_energy_cost * 0.02
        self.speed_multiplier *= self.locomotion_profile.speed_multiplier
        self.propulsion_efficiency *= self.locomotion_profile.thrust_efficiency
        self.grip_strength *= self.locomotion_profile.grip_bonus
        self._locomotion_drag_multiplier = self.locomotion_profile.drag_multiplier
        self.max_swim_speed *= max(0.85, self.locomotion_profile.speed_multiplier * 1.2)
        self.uses_signal_cones = self.locomotion_profile.uses_signal_cones
        self.signal_cone_threshold = self.locomotion_profile.signal_threshold
        self._burst_timer = 0
        self._burst_cooldown = 0
        self.hover_lift_preference = self.locomotion_profile.hover_lift_preference

        sensor_bonus = self.locomotion_profile.sensor_bonus
        if self.locomotion_profile.light_penalty > 0:
            light_factor = max(0.2, 1.0 - self.locomotion_profile.light_penalty)
            self.vision *= light_factor
        if sensor_bonus:
            self.vision += sensor_bonus
            self.hearing_range += sensor_bonus * 1.4
        self.vision = max(
            float(settings.VISION_MIN),
            min(float(settings.VISION_MAX), self.vision),
        )
        self.hearing_range = max(0.0, self.hearing_range)
        self._refresh_inertial_properties()

        self.parent_ids: Tuple[str, ...] = tuple(parents or ())
        self.family_signature: Tuple[str, ...] = (
            tuple(sorted(self.parent_ids)) if self.parent_ids else tuple()
        )

        self.initial_height = self.height
        self.initial_width = self.width

        counter = getattr(self.state, "lifeform_id_counter", 0)
        self.id = f"{self.dna_id}_{counter}"
        self.state.lifeform_id_counter = counter + 1

        # Derived / dynamic state
        self.dna_id_count = 0
        self.size = 0.0
        self.speed = 0.0
        self.angle = 0.0
        self.angular_velocity = max(0.05, self.turn_rate * 0.85)

        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)

        # Combat stats
        # self.defence_power and self.attack_power are now set in _derive_stats_from_body()
        self.attack_power_now = self.attack_power
        self.defence_power_now = self.defence_power
        
        # Vital stats
        self.age = 0.0
        self.hunger = 0.0
        self.wounded = 0.0  # General wound severity (0-100)
        self.health_now = float(self.health)
        self.energy_now = float(self.energy)
        self._feeding_frames = 0  # hoelang staat dit beest al "aan tafel"
        
        # Advanced wound tracking
        self.wounds: List[Dict[str, Any]] = []  # Individual wounds with metadata
        self.limb_damage: Dict[str, float] = {}  # Damage to specific body parts
        self.healing_factor = 1.0  # Base healing rate modifier
        self.scar_tissue = 0.0  # Accumulated scar tissue (0-1), reduces max health
        
        # Reproduction
        self.reproduced = 0
        self.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE
        
        # Perception targets
        self.closest_prey: Optional[Lifeform] = None
        self.closest_enemy: Optional[Lifeform] = None
        self.closest_partner: Optional[Lifeform] = None
        self.closest_follower: Optional[Lifeform] = None
        self.closest_plant = None  # Vegetation instance
        self.closest_carcass: Optional[SinkingCarcass] = None

        # Environment / biome
        self.current_biome: Optional[BiomeRegion] = None
        self.environment_effects = {
            "movement": 1.0,
            "hunger": 1.0,
            "regrowth": 1.0,
            "energy": 1.0,
            "health": 0.0,
            "temperature": 20,
            "precipitation": "helder",
            "weather_name": "Stabiel",
            "light": 1.0,
            "pressure": 1.0,
            "fluid_density": 1.0,
            "current_speed": 0.0,
        }

        # Social / grouping
        self.follow_range = 30
        self.is_leader = False
        self.search = False
        self.in_group = False
        self.group_neighbors: List[Lifeform] = []
        self.group_center: Optional[Tuple[float, float]] = None
        self.group_strength = 0.0
        self.group_state_timer = 0
        self.group_leader: Optional[Lifeform] = None

        # Behaviour / traits
        self.diet = dna_profile.get("diet", "omnivore")
        self.social_tendency = float(dna_profile.get("social", 0.5))
        self.boid_tendency = float(
            dna_profile.get("boid_tendency", self.social_tendency)
        )
        self.risk_tolerance = float(dna_profile.get("risk_tolerance", 0.5))
        self.restlessness = float(dna_profile.get("restlessness", 0.5))
        if not math.isfinite(self.restlessness):
            self.restlessness = 0.5
        self.restlessness = max(0.0, min(1.0, self.restlessness))
        if not math.isfinite(self.boid_tendency):
            self.boid_tendency = self.social_tendency
        self.boid_tendency = max(0.0, min(1.0, self.boid_tendency))

        # Local memory buffers
        self.memory: Dict[str, Deque[dict]] = {
            "visited": deque(maxlen=settings.MEMORY_MAX_VISITED),
            "food": deque(maxlen=settings.MEMORY_MAX_FOOD),
            "threats": deque(maxlen=settings.MEMORY_MAX_THREATS),
            "partner": deque(maxlen=settings.MEMORY_MAX_PARTNERS),
        }

        self._foraging_focus = False

        self.last_activity: Dict[str, Any] = {
            "name": "Verkennen",
            "details": {},
            "timestamp": pygame.time.get_ticks(),
        }

        # Wander / escape state
        initial_wander = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if initial_wander.length_squared() == 0:
            initial_wander = Vector2(1, 0)
        self.wander_direction = initial_wander.normalize()
        self.last_wander_update = 0
        self._wander_phase = "move"
        self._wander_phase_timer = 0.0
        self._wander_phase_duration = 0.0
        self._wander_pause_speed_factor = 1.0
        self._stuck_frames = 0
        self._boundary_contact_frames = 0
        self._escape_timer = 0
        self._escape_vector = Vector2()
        self._voluntary_pause = False
        self._next_wander_flip = 0
        self._refresh_inertial_properties()
        self._compute_buoyancy_debug()

    # ------------------------------------------------------------------
    # Convenience: access to global notification context via state
    # ------------------------------------------------------------------
    @property
    def notification_context(self):
        return getattr(self.state, "notification_context", None)

    @property
    def effects_manager(self):
        return getattr(self.state, "effects", None)

    def _apply_pigment(
        self, base_color: Tuple[int, int, int], tint: Tuple[float, float, float]
    ) -> Tuple[int, int, int]:
        """Apply a pigment tint multiplier to ``base_color``."""

        red = int(max(0, min(255, base_color[0] * tint[0])))
        green = int(max(0, min(255, base_color[1] * tint[1])))
        blue = int(max(0, min(255, base_color[2] * tint[2])))
        return red, green, blue

    def _apply_skin_development(
        self, base_color: Tuple[int, int, int]
    ) -> Tuple[int, int, int]:
        stage = max(0, min(self.skin_stage, 3))
        richness = 0.82 + stage * 0.08
        detail_bonus = 1.0 + len(self.development_features) * 0.02
        multiplier = richness * detail_bonus
        tinted = tuple(
            int(max(30, min(255, channel * multiplier))) for channel in base_color
        )
        if stage == 0:
            # Extra flets in de eerste generaties.
            tinted = tuple(int(channel * 0.9) for channel in tinted)
        return tinted

    def _trigger_escape_manoeuvre(self, reason: str) -> None:
        escape = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if escape.length_squared() == 0:
            escape = Vector2(1, 0)
        escape = escape.normalize()

        self._escape_vector = escape
        self._escape_timer = settings.ESCAPE_OVERRIDE_FRAMES
        self.wander_direction = escape
        self.x_direction = escape.x
        self.y_direction = escape.y
        self._boundary_contact_frames = 0
        self._stuck_frames = 0

        self.record_activity("Vluchten", reden=reason)

        logger.warning(
            "Lifeform %s executing escape manoeuvre (%s) towards vector (%.2f, %.2f)",
            self.id,
            reason,
            escape.x,
            escape.y,
        )

    # ------------------------------------------------------------------
    # Diet & reproduction helpers
    # ------------------------------------------------------------------
    def prefers_plants(self) -> bool:
        return self.diet in ("herbivore", "omnivore")

    def prefers_meat(self) -> bool:
        return self.diet in ("carnivore", "omnivore")

    def should_seek_food(self) -> bool:
        enemy_active = self.closest_enemy and self.closest_enemy.health_now > 0
        if enemy_active:
            self._foraging_focus = False
            return False

        if self.hunger <= settings.HUNGER_SATIATED_THRESHOLD:
            self._foraging_focus = False
            return False

        if self._foraging_focus and self.hunger <= settings.HUNGER_RELAX_THRESHOLD:
            self._foraging_focus = False

        if self._foraging_focus:
            return True

        locomotion_cost = max(0.1, getattr(self, "motion_energy_cost", 1.0))
        if self.energy_now <= locomotion_cost:
            self._foraging_focus = True
            return True

        if self.hunger >= settings.HUNGER_SEEK_THRESHOLD:
            self._foraging_focus = True
            return True

        if self.energy_now < self.energy * 0.45:
            return True

        return False

    def should_seek_partner(self) -> bool:
        if not self.can_reproduce():
            return False
        partner = self.closest_partner
        if partner and getattr(partner, "health_now", 0) > 0:
            return False
        if getattr(self, "_escape_timer", 0) > 0:
            return False
        return True

    @property
    def is_foraging(self) -> bool:
        return self._foraging_focus

    def can_reproduce(self) -> bool:
        if self.reproduced_cooldown != 0:
            return False
        if not self.is_adult():
            return False
        if self.hunger > settings.HUNGER_SEEK_THRESHOLD:
            return False
        if self.closest_enemy and self.closest_enemy.health_now > 0:
            return False
        energy_ratio = self.energy_now / max(1, self.energy)
        return energy_ratio >= settings.ENERGY_REPRODUCTION_THRESHOLD

    def plant_contact_point(self, plant: "Vegetation") -> Tuple[float, float]:
        """Return the closest point on the plant's surface from our centre."""

        if plant is None:
            return (float(self.rect.centerx), float(self.rect.centery))

        plant_rect = getattr(plant, "rect", None)
        if plant_rect is None:
            plant_rect = pygame.Rect(
                int(plant.x),
                int(plant.y),
                int(getattr(plant, "width", 0)),
                int(getattr(plant, "height", 0)),
            )

        center_x = float(self.rect.centerx)
        center_y = float(self.rect.centery)

        closest_x = max(plant_rect.left, min(center_x, plant_rect.right - 1))
        closest_y = max(plant_rect.top, min(center_y, plant_rect.bottom - 1))
        return (float(closest_x), float(closest_y))

    def direction_to_plant(self, plant: "Vegetation") -> Tuple[Vector2, float]:
        """Direction vector (from centre) and distance to the closest plant cell."""

        if plant is None:
            return Vector2(), 0.0

        target_x, target_y = self.plant_contact_point(plant)
        offset = Vector2(target_x - self.rect.centerx, target_y - self.rect.centery)
        distance = offset.length()
        if distance <= 0:
            return Vector2(), 0.0
        return offset.normalize(), distance

    def direction_to_carcass(self, carcass: SinkingCarcass) -> Tuple[Vector2, float]:
        if carcass is None:
            return Vector2(), 0.0
        offset = Vector2(
            carcass.rect.centerx - self.rect.centerx,
            carcass.rect.centery - self.rect.centery,
        )
        distance = offset.length()
        if distance <= 0:
            return Vector2(), 0.0
        return offset.normalize(), distance

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def _direction_to_point(self, point: Tuple[float, float]) -> Tuple[Vector2, float]:
        vector = Vector2(point[0] - self.x, point[1] - self.y)
        distance = vector.length()
        if distance == 0:
            return Vector2(), 0.0
        return vector.normalize(), distance

    def _direction_to_lifeform(self, other: "Lifeform") -> Tuple[Vector2, float]:
        return self._direction_to_point((other.x, other.y))

    def distance_to(self, other: "Lifeform") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def distance_to_plant(self, plant) -> float:
        """Return the minimal distance between our centre and the plant mass."""

        _, distance = self.direction_to_plant(plant)
        return distance

    def _plant_feeding_radius(self, plant) -> float:
        if plant is None:
            return 0.0
        plant_width = float(getattr(plant, "width", 0.0))
        plant_height = float(getattr(plant, "height", 0.0))
        plant_radius = max(plant_width, plant_height) * 0.5
        body_radius = max(float(self.width), float(self.height)) * 0.5
        reach_allowance = max(8.0, float(self.reach) * 0.5)
        return max(6.0, body_radius + plant_radius + reach_allowance)

    def distance_to_carcass(self, carcass: SinkingCarcass) -> float:
        _, distance = self.direction_to_carcass(carcass)
        return distance

    def is_adult(self) -> bool:
        return self.age >= self.maturity

    def _distance_squared_to_lifeform(self, other: "Lifeform") -> float:
        dx = self.rect.centerx - other.rect.centerx
        dy = self.rect.centery - other.rect.centery
        return float(dx * dx + dy * dy)

    def _distance_squared_to_point(self, x: float, y: float) -> float:
        dx = self.rect.centerx - x
        dy = self.rect.centery - y
        return float(dx * dx + dy * dy)

    # ------------------------------------------------------------------
    # Target selection / groups
    # ------------------------------------------------------------------
    def _is_close_family(self, other: "Lifeform") -> bool:
        """Return True when the other lifeform is considered close family."""

        if other is self:
            return True

        my_parents = getattr(self, "parent_ids", tuple())
        other_parents = getattr(other, "parent_ids", tuple())

        if other.id in my_parents or self.id in other_parents:
            return True

        if my_parents and other_parents and set(my_parents) & set(other_parents):
            return True

        my_signature = getattr(self, "family_signature", tuple())
        other_signature = getattr(other, "family_signature", tuple())
        if my_signature and my_signature == other_signature:
            return True

        return False

    def _can_partner_with(self, other: "Lifeform") -> bool:
        if other is self:
            return False
        if other.health_now <= 0:
            return False
        if other.dna_id != self.dna_id:
            return False
        if not self.is_adult() or not other.is_adult():
            return False
        if self._is_close_family(other):
            return False
        return True

    def update_targets(self) -> None:
        # Use cached sensor ranges
        target_ranges = self._sensor_target_ranges
        
        creature_range = target_ranges.get("creatures", max(0.0, float(self.vision)))
        plant_range = target_ranges.get("plants", creature_range)
        carrion_range = target_ranges.get("carrion", plant_range)

        self.sensory_range = max(creature_range, plant_range, carrion_range)
        vision_range = creature_range
        if vision_range <= 0:
            self.closest_enemy = None
            self.closest_prey = None
            self.closest_partner = None
            self.closest_follower = None
            self.closest_plant = None
            return

        vision_sq = vision_range * vision_range
        plant_sq = plant_range * plant_range
        carrion_sq = carrion_range * carrion_range
        hearing_range = max(
            vision_range, vision_range + max(0.0, self.hearing_range)
        )
        hearing_sq = max(vision_sq, hearing_range * hearing_range)
        close_range = self.reach + max(self.width, self.height) * 0.5
        close_range_sq = max(9.0, close_range * close_range)
        forward = Vector2(self.velocity)
        if forward.length_squared() < 1e-4:
            forward = Vector2(self.x_direction, self.y_direction)
        if forward.length_squared() == 0:
            forward = Vector2(1, 0)
        else:
            forward = forward.normalize()
        threshold = max(0.05, min(0.95, self.fov_threshold))
        if getattr(self, "_energy_starved", False) or self.hunger >= settings.HUNGER_SEEK_THRESHOLD:
            threshold = max(0.05, threshold * 0.8)
        focused_threshold_sq = threshold * threshold
        peripheral_threshold = max(0.05, threshold * 0.65)
        peripheral_threshold_sq = peripheral_threshold * peripheral_threshold
        peripheral_range = max(close_range * 1.5, vision_range * 0.7)
        peripheral_sq = peripheral_range * peripheral_range

        enemy_candidate = None
        prey_candidate = None
        partner_candidate = None
        follower_candidate = None
        plant_candidate = None

        enemy_distance = vision_sq
        prey_distance = vision_sq
        partner_distance = vision_sq
        follower_distance = vision_sq
        plant_distance = plant_sq
        carcass_distance = carrion_sq
        carcass_candidate = None

        # --- Optimization: Use Spatial Grid if available ---
        spatial_grid = getattr(self.state, "spatial_grid", None)
        
        if spatial_grid:
            # Query candidates within the maximum sensory range
            candidate_lifeforms = spatial_grid.query_lifeforms(self.x, self.y, self.sensory_range)
            candidate_plants = spatial_grid.query_plants(self.x, self.y, self.sensory_range)
        else:
            # Fallback to full lists
            candidate_lifeforms = self.state.lifeforms
            candidate_plants = self.state.plants

        for lifeform in candidate_lifeforms:
            if lifeform is self:
                continue
            if lifeform.health_now <= 0:
                continue

            if self._is_close_family(lifeform):
                continue

            dx = lifeform.rect.centerx - self.rect.centerx
            dy = lifeform.rect.centery - self.rect.centery
            distance_sq = float(dx * dx + dy * dy)
            if distance_sq > hearing_sq:
                continue

            in_close = distance_sq <= close_range_sq
            in_vision = distance_sq <= vision_sq
            fov_ok = in_close
            if not fov_ok and in_vision:
                dot = forward.x * dx + forward.y * dy
                if distance_sq <= 1e-6:
                    fov_ok = True
                else:
                    cos_angle = dot / max(1e-6, distance_sq**0.5)
                    if dot > 0 and dot * dot >= focused_threshold_sq * distance_sq:
                        fov_ok = True
                    elif (
                        dot > 0
                        and distance_sq <= peripheral_sq
                        and dot * dot >= peripheral_threshold_sq * distance_sq
                    ):
                        fov_ok = True
                    elif self.uses_signal_cones and cos_angle >= self.signal_cone_threshold:
                        fov_ok = True

            enemy_heard = False
            if not fov_ok and lifeform.attack_power_now > self.defence_power_now:
                enemy_heard = True

            if not in_vision and not enemy_heard:
                continue

            if not self.is_leader and lifeform.is_leader and distance_sq < follower_distance:
                if not fov_ok and not in_close:
                    continue
                follower_candidate = lifeform
                follower_distance = distance_sq

            if self._can_partner_with(lifeform):
                if fov_ok and distance_sq < partner_distance:
                    partner_candidate = lifeform
                    partner_distance = distance_sq
                continue

            if lifeform.dna_id == self.dna_id:
                # Avoid classifying the same species as prey or enemy.
                continue

            if lifeform.attack_power_now > self.defence_power_now:
                if (fov_ok or enemy_heard) and distance_sq < enemy_distance:
                    enemy_candidate = lifeform
                    enemy_distance = distance_sq
                continue

            if lifeform.attack_power_now < self.defence_power_now:
                if fov_ok and distance_sq < prey_distance:
                    prey_candidate = lifeform
                    prey_distance = distance_sq

        for plant in candidate_plants:
            if plant.resource <= 0:
                continue

            contact_x, contact_y = self.plant_contact_point(plant)
            dx = contact_x - self.rect.centerx
            dy = contact_y - self.rect.centery
            distance_sq = float(dx * dx + dy * dy)
            if distance_sq > plant_sq:
                continue
            in_close = distance_sq <= close_range_sq
            if not in_close:
                if distance_sq <= 1e-6:
                    pass
                else:
                    dot = forward.x * dx + forward.y * dy
                    cos_angle = dot / max(1e-6, distance_sq**0.5)
                    within_cone = self.uses_signal_cones and cos_angle >= self.signal_cone_threshold
                    within_periphery = (
                        dot > 0
                        and distance_sq <= peripheral_sq
                        and dot * dot >= peripheral_threshold_sq * distance_sq
                    )
                    if not (dot > 0 and dot * dot >= focused_threshold_sq * distance_sq) and not within_cone and not within_periphery:
                        continue
            if distance_sq < plant_distance:
                plant_candidate = plant
                plant_distance = distance_sq

        for carcass in getattr(self.state, "carcasses", []):
            if getattr(carcass, "is_depleted", lambda: False)():
                continue
            dx = carcass.rect.centerx - self.rect.centerx
            dy = carcass.rect.centery - self.rect.centery
            distance_sq = float(dx * dx + dy * dy)
            if distance_sq > carrion_sq:
                continue
            in_close = distance_sq <= close_range_sq
            if not in_close:
                if distance_sq <= 1e-6:
                    pass
                else:
                    dot = forward.x * dx + forward.y * dy
                    cos_angle = dot / max(1e-6, distance_sq**0.5)
                    within_cone = self.uses_signal_cones and cos_angle >= self.signal_cone_threshold
                    within_periphery = (
                        dot > 0
                        and distance_sq <= peripheral_sq
                        and dot * dot >= peripheral_threshold_sq * distance_sq
                    )
                    if not (dot > 0 and dot * dot >= focused_threshold_sq * distance_sq) and not within_cone and not within_periphery:
                        continue
            if distance_sq < carcass_distance:
                carcass_candidate = carcass
                carcass_distance = distance_sq

        old_enemy = self.closest_enemy
        old_prey = self.closest_prey

        self.closest_enemy = enemy_candidate
        self.closest_prey = prey_candidate
        self.closest_partner = partner_candidate
        self.closest_follower = follower_candidate if not self.is_leader else None
        self.closest_plant = plant_candidate
        self.closest_carcass = carcass_candidate
        
        if self.closest_enemy is not old_enemy and self.closest_enemy:
            log_event("AI", "THREAT_DETECTED", self.id, {
                "target_id": self.closest_enemy.id,
                "dist": round(enemy_distance, 1)
            })
            
        if self.closest_prey is not old_prey and self.closest_prey:
            log_event("AI", "PREY_ACQUIRED", self.id, {
                "target_id": self.closest_prey.id,
                "dist": round(prey_distance, 1)
            })

    def _initialise_body(self, dna_profile: dict) -> None:
        diet = dna_profile.get("diet", "omnivore")
        genome_data = dna_profile.get("genome") or generate_modular_blueprint(diet)
        try:
            genome = ensure_genome(genome_data)
            graph, geometry = build_body_graph(genome, include_geometry=True)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception(
                "Failed to build body graph for dna %s: %s", dna_profile.get("dna_id"), exc
            )
            fallback = generate_modular_blueprint(diet)
            genome = ensure_genome(fallback)
            graph, geometry = build_body_graph(genome, include_geometry=True)
        self.genome: Genome = genome
        self.genome_blueprint = genome.to_dict()
        self.body_graph = graph
        self.body_geometry = geometry
        self.physics_body: PhysicsBody = build_physics_body(graph)

    def _derive_stats_from_body(self) -> None:
        """Calculate all gameplay stats from the assembled body graph."""
        
        # 1. Geometry
        width, height, _ = self.body_graph.compute_bounds()
        # Scale up slightly because modules are small (meters) and world is pixels
        pixel_scale = settings.BODY_PIXEL_SCALE
        if settings.USE_BODYGRAPH_SIZE:
            if self.profile_geometry:
                width = self.profile_geometry.get("width", width)
                height = self.profile_geometry.get("height", height)
            elif getattr(self, "body_geometry", None):
                width = self.body_geometry.get("width", width)
                height = self.body_geometry.get("height", height)
        self.base_width = int(max(1.0, width * pixel_scale))
        self.base_height = int(max(1.0, height * pixel_scale))

        # 2-4. Collect stats in a single pass through modules (much faster!)
        total_integrity = 0.0
        module_capacity = 0.0
        vision_bonus = 0.0
        max_sensor_range = 0.0
        tentacle_count = 0
        tentacle_reach = 0.0
        tentacle_grip = 0.0
        tentacle_span = 0.0

        for module in self.body_graph.iter_modules():
            # Health & Integrity
            total_integrity += module.stats.integrity
            
            # Energy from Core modules
            if module.module_type == "core":
                module_capacity += getattr(module, "energy_capacity", 0.0)
            
            # Vision from Head modules
            if module.module_type == "head":
                vision_bonus += getattr(module, "vision_bonus", 0.0)
            
            # Sensor range from Sensor modules
            if module.module_type == "sensor":
                detection = getattr(module, "detection_range", 0.0)
                if detection > max_sensor_range:
                    max_sensor_range = detection

            if module.module_type == "tentacle":
                tentacle_count += 1
                tentacle_reach += max(0.0, module.size[2])
                tentacle_span += max(module.size[0], module.size[1])
                tentacle_grip += float(getattr(module, "grip_strength", 0.0))

        self.health = max(10, int(total_integrity))

        base_energy = 100.0
        mass_factor = self.physics_body.mass * 2.0
        self.energy = int(base_energy + module_capacity + mass_factor)
        base_vision = 150.0
        self.vision = base_vision + vision_bonus + max_sensor_range

        self.tentacle_count = tentacle_count or getattr(self, "tentacle_count", 0)
        self.tentacle_reach = tentacle_reach or getattr(self.physics_body, "tentacle_reach", 0.0)
        self.tentacle_span = tentacle_span or getattr(self.physics_body, "tentacle_span", 0.0)
        self.tentacle_grip_bonus = tentacle_grip or getattr(self.physics_body, "tentacle_grip", 0.0)

        # 5. Combat Power
        # Attack: Thrust (ramming) + Grip (grappling) + Mass (impact) + Bite (mouths)
        thrust_factor = self.physics_body.max_thrust * 0.2
        grip_factor = self.physics_body.grip_strength * 0.5
        mass_impact = self.physics_body.mass * 0.1

        bite_damage = 0.0
        for module in self.body_graph.iter_modules():
            if getattr(module, "module_type", "") == "mouth":
                bite_damage += getattr(module, "bite_damage", 0.0)

        bite_bonus = max(0.0, self.bite_force * 0.35)

        tentacle_control = (
            self.tentacle_grip_bonus * 0.35
            + self.tentacle_reach * 0.08
            + self.tentacle_span * 0.15
            + self.tentacle_count * 0.5
        )
        self.grapple_power = max(0.0, tentacle_control)

        self.attack_power = max(
            1.0,
            thrust_factor + grip_factor + mass_impact + bite_damage + bite_bonus + self.grapple_power,
        )

        # Defence: Integrity (health) + Mass (bulk) + Density (armor)
        integrity_factor = self.health * 0.1
        bulk_factor = self.physics_body.mass * 0.2
        armor_factor = self.physics_body.density * 5.0 + self.tissue_hardness * 4.0
        self.defence_power = max(
            1.0, integrity_factor + bulk_factor + armor_factor + self.grapple_power * 0.6
        )

    def _compute_buoyancy_debug(self) -> None:
        """Compute and store buoyancy diagnostics for debugging and inspection."""
        pb = getattr(self, 'physics_body', None)
        if pb is None:
            self.net_buoyancy = 0.0
            self.relative_buoyancy = 0.0
            self.is_near_floating = False
            self.buoyancy_debug = {}
            return

        # Try to get fluid density from the world/ocean
        fluid_density = None
        world = getattr(self, 'state', None)
        if world is not None:
            ocean = getattr(world, 'ocean_physics', None) or getattr(world, 'ocean', None)
            if ocean and hasattr(ocean, 'properties_at'):
                try:
                    props = ocean.properties_at(getattr(self, 'y', 0.0))
                    fluid_density = getattr(props, 'density', None)
                except Exception:
                    fluid_density = None

        # Fallback to standard water density
        if fluid_density is None:
            fluid_density = 1.0

        # Extract physics properties
        buoyancy_volume = float(getattr(pb, 'buoyancy_volume', pb.volume))
        body_volume = float(getattr(pb, 'volume', 0.0))
        mass = float(getattr(pb, 'mass', 0.0))

        # Compute forces
        buoyant_force = float(fluid_density) * buoyancy_volume * _GRAVITY
        weight = mass * _GRAVITY
        net_buoyancy = buoyant_force - weight
        relative_net = net_buoyancy / max(weight, 1e-6)

        # Determine if near-floating using tolerance criteria
        rel_tol = 0.05  # 5% relative tolerance
        abs_tol = max(0.02 * weight, 0.5)  # Absolute tolerance
        is_near = abs(relative_net) <= rel_tol or abs(net_buoyancy) <= abs_tol

        # Store computed attributes
        self.net_buoyancy = net_buoyancy
        self.relative_buoyancy = relative_net
        self.is_near_floating = is_near
        self.buoyancy_debug = {
            'fluid_density': float(fluid_density),
            'buoyancy_volume': buoyancy_volume,
            'body_volume': body_volume,
            'body_density': float(getattr(pb, 'density', 0.0)),
            'mass': mass,
            'buoyant_force_N': buoyant_force,
            'weight_N': weight,
            'buoyancy_offsets': getattr(pb, 'buoyancy_offsets', None),
            'drag_coefficient': getattr(pb, 'drag_coefficient', None),
            'grip_strength': getattr(pb, 'grip_strength', None),
        }

        # Log diagnostics
        logger.debug(
            'Lifeform %s @y=%.2f net_buoyancy=%.3f N (rel: %.3f). breakdown: %s',
            getattr(self, 'id', '<no-id>'),
            getattr(self, 'y', 0.0),
            self.net_buoyancy,
            self.relative_buoyancy,
            self.buoyancy_debug,
        )

    def _derive_sensor_suite(self) -> Dict[str, float]:
        return self._scan_sensor_modules()

    def _apply_sensor_baselines(self, sensors: Dict[str, float]) -> None:
        if not sensors:
            return
        spectral_count = len(sensors)
        aggregate_range = sum(float(r) for r in sensors.values())
        spectral_bonus = max(0, spectral_count * 2)
        range_bonus = int(max(0.0, aggregate_range) / 60.0)
        self.perception_rays = max(
            self.morph_stats.perception_rays,
            spectral_bonus + range_bonus + 4,
        )
        audio_specs = ("sonar", "bioelectric", "electro", "thermal")
        best_audio = max((sensors.get(spec, 0.0) for spec in audio_specs), default=0.0)
        if best_audio > 0:
            self.hearing_range = max(
                self.morph_stats.hearing_range,
                min(420.0, best_audio * 1.6),
            )

    def _scan_sensor_modules(self) -> Dict[str, float]:
        sensors: Dict[str, float] = {}
        graph = getattr(self, "body_graph", None)
        if not graph:
            return sensors
        for module in graph.iter_modules():
            m_type = getattr(module, "module_type", "")
            if m_type != "sensor" and m_type != "eye":
                continue
            detection_range = float(getattr(module, "detection_range", 0.0))
            for spectrum in getattr(module, "spectrum", ()):
                key = str(spectrum)
                sensors[key] = max(sensors.get(key, 0.0), detection_range)
        return sensors

    def _compute_sensor_target_ranges(self, sensors: Dict[str, float]) -> Dict[str, float]:
        base = max(0.0, float(self.vision))
        creature_specs = ("light", "colour", "sonar", "bioelectric", "electro", "thermal")
        plant_specs = ("light", "colour", "pheromone")
        carrion_specs = ("pheromone", "bioelectric", "electro")

        def _range(specs: Tuple[str, ...]) -> float:
            values = [sensors.get(spec, 0.0) for spec in specs]
            values.append(base)
            return max(values)

        creature_range = _range(creature_specs)
        plant_range = _range(plant_specs)
        carrion_range = max(
            plant_range, max(sensors.get(spec, 0.0) for spec in carrion_specs)
        )

        return {
            "creatures": creature_range,
            "plants": plant_range,
            "carrion": carrion_range,
            "spectra": sensors,
        }

    def _summarize_modules(self) -> Dict[str, int]:
        breakdown: Dict[str, int] = {}
        names: List[str] = []
        graph = getattr(self, "body_graph", None)
        if not graph:
            self.body_module_names = tuple()
            return breakdown
        for module in graph.iter_modules():
            names.append(getattr(module, "name", getattr(module, "key", type(module).__name__)))
            module_type = getattr(module, "module_type", type(module).__name__)
            breakdown[module_type] = breakdown.get(module_type, 0) + 1
        self.body_module_names = tuple(names)
        return breakdown

    def _scaled_mass(self, value: float) -> float:
        return max(0.6, min(6.5, value / 15.0))

    def _scaled_grip(self, value: float) -> float:
        return max(0.35, min(2.5, value / 6.0))

    def set_size(self) -> None:
        self.size = self.width * self.height * max(0.5, self.mass)
        if self.width < 1:
            self.width = 1
        if self.height < 1:
            self.height = 1
        self._refresh_inertial_properties()

    def _refresh_inertial_properties(self) -> None:
        drag_scale = getattr(self, "_locomotion_drag_multiplier", 1.0)
        physics = getattr(self, "physics_body", None)
        if physics is not None:
            self.volume = max(1.0, physics.volume)
            self.body_density = max(0.2, getattr(physics, "density", 1.0))
            base_drag = max(0.05, getattr(physics, "drag_coefficient", 0.2))
        else:
            area = max(1.0, self.width * self.height)
            self.volume = area * 0.12
            self.body_density = max(0.2, self.mass / max(1.0, self.volume))
            base_drag = max(0.1, min(1.4, (self.width + self.height) / 220.0))
        self.drag_coefficient = max(0.05, min(2.4, base_drag * drag_scale))
        # Update buoyancy diagnostics when inertial properties change
        if hasattr(self, '_compute_buoyancy_debug'):
            self._compute_buoyancy_debug()

    def check_group(self) -> None:
        relevant_radius = min(self.vision, settings.GROUP_MAX_RADIUS)
        if relevant_radius <= 0:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0
            self.group_state_timer = 0
            self.group_leader = None
            return

        neighbors: List[Tuple["Lifeform", float]] = []
        total_distance = 0.0
        total_x = self.x
        total_y = self.y

        for lifeform in self.state.lifeforms:
            if lifeform is self:
                continue
            if lifeform.dna_id != self.dna_id or lifeform.health_now <= 0:
                continue
            if lifeform.age < lifeform.maturity * settings.GROUP_MATURITY_RATIO:
                continue
            distance = self.distance_to(lifeform)
            if distance <= relevant_radius:
                neighbors.append((lifeform, distance))
                total_distance += distance
                total_x += lifeform.x
                total_y += lifeform.y

        self.group_neighbors = [lf for lf, _ in neighbors]
        neighbor_count = len(neighbors)

        qualified = False
        cohesion = 0.0
        if neighbor_count >= settings.GROUP_MIN_NEIGHBORS:
            avg_distance = total_distance / neighbor_count if neighbor_count else 0
            cohesion = max(0.0, 1.0 - avg_distance / relevant_radius)
            if cohesion >= settings.GROUP_COHESION_THRESHOLD:
                qualified = True
        else:
            self.group_strength = 0
            self.group_center = None

        if qualified:
            self.in_group = True
            self.group_state_timer = settings.GROUP_PERSISTENCE_FRAMES
            total_members = neighbor_count + 1
            self.group_center = (total_x / total_members, total_y / total_members)
            self.group_strength = cohesion
            self.group_leader = self._determine_group_leader()
        elif self.group_state_timer > 0:
            self.group_state_timer -= 1
            self.in_group = True
            if not self.group_leader or getattr(self.group_leader, "health_now", 0) <= 0:
                self.group_leader = self._determine_group_leader()
        else:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0
            self.group_leader = None

    def _determine_group_leader(self) -> Optional["Lifeform"]:
        candidates = [self]
        candidates.extend(self.group_neighbors)
        alive = [lf for lf in candidates if getattr(lf, "health_now", 0) > 0]
        if not alive:
            return None

        def _leader_score(lf: "Lifeform") -> Tuple[float, float, float]:
            leader_bonus = 1.0 if getattr(lf, "is_leader", False) else 0.0
            boid_drive = getattr(lf, "boid_tendency", getattr(lf, "social_tendency", 0.5))
            return (leader_bonus, boid_drive, getattr(lf, "age", 0.0))

        alive.sort(key=_leader_score, reverse=True)
        return alive[0]

    # ------------------------------------------------------------------
    # Stats / combat / lifecycle
    # ------------------------------------------------------------------
    def set_speed(self, average_maturity: Optional[float] = None) -> None:
        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        biome, effects = self.state.world.get_environment_context(
            self.x + self.width / 2,
            self.y + self.height / 2,
        )
        self.current_biome = biome
        self.environment_effects = effects
        plant_modifier = 1.0
        
        # --- Optimization: Use Spatial Grid if available ---
        spatial_grid = getattr(self.state, "spatial_grid", None)
        if spatial_grid:
            # Only check plants very close to us
            check_radius = max(self.width, self.height) * 0.6
            nearby_plants = spatial_grid.query_plants(self.rect.centerx, self.rect.centery, check_radius)
        else:
            nearby_plants = self.state.plants

        for plant in nearby_plants:
            if plant.resource <= 0:
                continue
            if plant.contains_point(self.rect.centerx, self.rect.centery):
                plant_modifier = plant.movement_modifier_for(self)
                break

        body_mass = getattr(self, "body_mass", self.mass * 40.0)
        thrust_ratio = self.max_thrust / max(18.0, body_mass * 1.2)
        genetic_speed = 0.45 + min(3.4, thrust_ratio * 0.55)
        locomotion_factor = _clamp(0.7 + self.speed_multiplier * 0.25, 0.65, 1.45)
        propulsion_factor = _clamp(0.75 + getattr(self, "propulsion_efficiency", 1.0) * 0.2, 0.7, 1.35)
        grip_factor = _clamp(0.7 + self.grip_strength * 0.2, 0.7, 1.3)
        base_speed = genetic_speed * locomotion_factor * propulsion_factor * grip_factor

        maturity_target = average_maturity or self.maturity or 1.0
        maturity_target = max(1.0, maturity_target)
        maturity_ratio = self.age / maturity_target
        if maturity_ratio < 1.0:
            age_factor = 0.4 + 0.6 * (maturity_ratio ** 0.8)
        else:
            elder_ratio = (self.age - maturity_target) / max(1.0, self.longevity - maturity_target)
            age_factor = max(0.45, 1.0 - min(0.5, elder_ratio * 0.6))

        hunger_span = max(1.0, settings.HUNGER_CRITICAL_THRESHOLD - settings.HUNGER_RELAX_THRESHOLD)
        hunger_norm = (self.hunger - settings.HUNGER_RELAX_THRESHOLD) / hunger_span
        hunger_norm = _clamp(hunger_norm, 0.0, 1.5)
        hunger_factor = _clamp(1.05 - 0.55 * (hunger_norm ** 1.1), 0.4, 1.05)

        health_ratio = self.health_now / max(1.0, getattr(self, "health", 1.0))
        energy_ratio = self.energy_now / max(1.0, getattr(self, "energy", 1.0))
        vitality_factor = 0.5 + ((health_ratio * 0.7) + (energy_ratio * 0.3)) * 0.5
        vitality_factor = _clamp(vitality_factor, 0.55, 1.2)

        mass_drag = 1.0 - min(0.5, math.log1p(max(0.4, self.mass)) * 0.12)
        adrenaline_boost = 1.0 + min(0.35, max(0.0, getattr(self, "adrenaline_factor", 0.0)) * 0.4)

        base_speed *= age_factor
        base_speed *= hunger_factor
        base_speed *= vitality_factor
        base_speed *= mass_drag
        base_speed *= adrenaline_boost

        movement_factor = float(effects.get("movement", 1.0))
        base_speed *= movement_factor
        base_speed *= plant_modifier

        pause_factor = getattr(self, "_wander_pause_speed_factor", 1.0)
        base_speed *= pause_factor

        min_speed = 0.35 + 0.1 * self.speed_multiplier
        max_speed = min(self.max_swim_speed * 0.12, 9.0 + self.speed_multiplier)
        self.speed = _clamp(base_speed, min_speed, max_speed)

    def handle_death(self) -> bool:
        if self.health_now > 0:
            return False

        self.record_activity("Gestorven")

        context = self.notification_context
        if context:
            context.action(f"{self.id} is gestorven")

        logger.info(
            "Lifeform %s died at age %.1f with hunger %.1f and energy %.1f",
            self.id,
            self.age,
            self.hunger,
            self.energy_now,
        )

        effects = self.effects_manager
        if effects:
            center_x = self.x + self.width / 2
            effects.spawn_death((center_x, self.y - 12))

        carcass = DecomposingCarcass(
            position=(self.x, self.y),
            size=(int(self.width), int(self.height)),
            mass=self.mass,
            nutrition=max(12.0, self.size * 0.18),
            color=self.color,
            body_graph=getattr(self, "body_graph", None),
            body_geometry=getattr(self, "profile_geometry", {}),
        )
        self.state.carcasses.append(carcass)

        if self in self.state.lifeforms:
            self.state.lifeforms.remove(self)
        self.state.death_ages.append(self.age)
        return True

    def update_angle(self) -> None:
        self.angle = math.degrees(math.atan2(self.y_direction, self.x_direction))

    def calculate_age_factor(self) -> float:
        age_factor = 1.0
        if self.age > self.longevity:
            age_factor = age_factor * 0.9 ** (self.age - self.longevity)
        return age_factor

    def calculate_attack_power(self) -> None:
        self.attack_power_now = self.attack_power * (self.energy_now / 100)
        self.attack_power_now -= self.attack_power * (self.wounded / 100)
        # Removed broken size bonus: self.attack_power_now += (self.size - 50) * 0.8
        self.attack_power_now -= self.hunger * 0.1
        self.attack_power_now *= self.calculate_age_factor()
        mass_bonus = 1.0 + (self.mass - 1.0) * 0.12
        reach_bonus = 1.0 + (self.reach - 4.0) * 0.03
        self.attack_power_now *= max(0.4, mass_bonus * reach_bonus)

        if self.attack_power_now < 1:
            self.attack_power_now = 1
        if self.attack_power_now > 100:
            self.attack_power_now = 100

    def calculate_defence_power(self) -> None:
        self.defence_power_now = self.defence_power * (self.energy_now / 100)
        self.defence_power_now -= self.defence_power * (self.wounded / 100)
        # Removed broken size bonus: self.defence_power_now += (self.size - 50) * 0.8
        self.defence_power_now -= self.hunger * 0.1
        self.defence_power_now *= self.calculate_age_factor()
        defence_bonus = 1.0 + (self.grip_strength - 1.0) * 0.25
        defence_bonus *= 1.0 + (self.mass - 1.0) * 0.08
        self.defence_power_now *= max(0.4, defence_bonus)

        if self.defence_power_now < 1:
            self.defence_power_now = 1
        if self.defence_power_now > 100:
            self.defence_power_now = 100

    def record_activity(self, name: str, **details: Any) -> None:
        """Sla de laatst uitgevoerde actie op voor inspectie-overlays."""

        timestamp = pygame.time.get_ticks()
        self.last_activity = {
            "name": name,
            "details": details,
            "timestamp": timestamp,
        }

    def grow(self) -> None:
        if self.age < self.maturity:
            factor = self.age / self.maturity
            self.height = self.initial_height * factor
            self.width = self.initial_width * factor

    def reproduce(self, partner: "Lifeform") -> bool:
        if len(self.state.lifeforms) >= settings.MAX_LIFEFORMS:
            logger.info(
                "Lifeform %s attempted to reproduce with %s but cap %s reached",
                self.id,
                partner.id,
                settings.MAX_LIFEFORMS,
            )
            retry = max(1, settings.POPULATION_CAP_RETRY_COOLDOWN)
            self.reproduced_cooldown = retry
            partner.reproduced_cooldown = retry
            self.record_activity(
                "Reproductie mislukt",
                reden="populatie limiet",
                partner=partner.id,
            )
            partner.record_activity(
                "Reproductie mislukt",
                reden="populatie limiet",
                partner=self.id,
            )
            return False

        child_dna_profile, metadata = reproduction.create_offspring_profile(
            self.state,
            self,
            partner,
        )

        child_parents: Tuple[str, ...] = (self.id, partner.id)
        child = Lifeform(
            self.state,
            self.x,
            self.y,
            child_dna_profile,
            self.generation + 1,
            parents=child_parents,
        )
        if random.randint(0, 100) < 10:
            child.is_leader = True
        self.state.lifeforms.append(child)

        self.state.lifeform_genetics[child.id] = {
            "dna_id": child.dna_id,
            "parents": child_parents,
            "source_profile": metadata.source_profile,
            "dna_change": metadata.dna_change,
            "color_change": metadata.color_change,
            "mutations": list(metadata.mutations),
            "is_new_profile": metadata.is_new_profile,
        }

        player = getattr(self.state, "player", None)
        if player:
            player.on_birth()

        context = self.notification_context
        if context:
            context.action(f"Nieuwe levensvorm geboren uit {self.id}")

        effects = self.effects_manager
        if effects:
            center_x = self.x + self.width / 2
            effects.spawn_birth((center_x, self.y - 16))

        logger.info(
            "Lifeform %s reproduced with %s producing %s at (%.1f, %.1f) [dna %s]",
            self.id,
            partner.id,
            child.id,
            self.x,
            self.y,
            child.dna_id,
        )

        self.record_activity("Reproduceert", partner=partner.id, kind=child.id)
        partner.record_activity("Reproduceert", partner=self.id, kind=child.id)

        self.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE
        partner.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE
        return True

    def progression(self, delta_time: float) -> None:
        biome, effects = self.state.world.get_environment_context(
            self.x + self.width / 2,
            self.y + self.height / 2,
        )
        self.current_biome = biome
        self.environment_effects = effects

        hunger_rate = self.state.environment_modifiers.get(
            "hunger_rate", 1.0
        ) * float(effects["hunger"])
        hunger_rate *= 1.0 + (self.mass - 1.0) * 0.04
        self.hunger += hunger_rate * settings.HUNGER_RATE_PER_SECOND * delta_time
        self.age += settings.AGE_RATE_PER_SECOND * delta_time
        self.energy_now += (
            settings.ENERGY_RECOVERY_PER_SECOND
            * delta_time
            * float(effects["energy"])
        )
        maintenance = self.maintenance_cost * (0.85 + 0.15 * self.mass)
        self.energy_now -= maintenance * delta_time
        self.wounded -= settings.WOUND_HEAL_PER_SECOND * delta_time
        self.health_now += float(effects["health"]) * delta_time

        light_level = float(self.environment_effects.get("light", 1.0))
        if light_level < 0.35:
            self.energy_now -= (0.35 - light_level) * 12.0 * delta_time

        pressure_level = float(self.environment_effects.get("pressure", 1.0))
        if pressure_level > 10.0:
            self.health_now -= (pressure_level - 10.0) * 0.12 * delta_time

        if self.age > self.longevity:
            self.health_now -= (
                settings.LONGEVITY_HEALTH_DECAY_PER_SECOND * delta_time
            )
        if self.age > 10000:
            self.health_now -= (
                settings.EXTREME_LONGEVITY_DECAY_PER_SECOND * delta_time
            )

        if self.hunger > 500:
            self.health_now -= (
                settings.HUNGER_HEALTH_PENALTY_PER_SECOND * delta_time
            )
        if self.hunger > 1000:
            self.health_now -= (
                settings.EXTREME_HUNGER_HEALTH_PENALTY_PER_SECOND * delta_time
            )

        if self.wounded < 0:
            self.wounded = 0
        if self.energy_now < 1:
            self.energy_now = 1
        if self.energy_now > self.energy:
            self.energy_now = self.energy

        if self.health_now > self.health:
            self.health_now = self.health

    # ------------------------------------------------------------------
    # Debug helpers
    # ------------------------------------------------------------------

    def _summarise_related(self, entity: Optional["Lifeform"]) -> Optional[Dict[str, Any]]:
        if entity is None:
            return None
        summary: Dict[str, Any] = {
            "id": getattr(entity, "id", None),
            "dna_id": getattr(entity, "dna_id", None),
            "health": getattr(entity, "health_now", None),
            "position": (
                getattr(entity, "x", None),
                getattr(entity, "y", None),
            ),
        }
        return summary

    def _summarise_plant(self, plant) -> Optional[Dict[str, Any]]:
        if plant is None:
            return None
        center = (plant.x + plant.width / 2, plant.y + plant.height / 2)
        distance = math.hypot(self.x - center[0], self.y - center[1])
        return {
            "position": center,
            "resource": getattr(plant, "resource", None),
            "size": (plant.width, plant.height),
            "distance": distance,
        }

    def debug_snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serialisable snapshot of the current lifeform state."""

        memory_dump: Dict[str, List[Any]] = {}
        for key, entries in self.memory.items():
            formatted_entries: List[Any] = []
            for entry in entries:
                if isinstance(entry, dict):
                    formatted_entries.append(dict(entry))
                else:
                    formatted_entries.append(str(entry))
            memory_dump[key] = formatted_entries

        snapshot: Dict[str, Any] = {
            "id": self.id,
            "dna_id": self.dna_id,
            "generation": self.generation,
            "diet": self.diet,
            "base_form": self.base_form,
            "base_form_label": self.base_form_label,
            "position": (self.x, self.y),
            "rect": (
                self.rect.x,
                self.rect.y,
                self.rect.width,
                self.rect.height,
            ),
            "velocity": (self.x_direction, self.y_direction),
            "speed": self.speed,
            "angle": self.angle,
            "health": {
                "current": self.health_now,
                "max": self.health,
                "wounded": self.wounded,
            },
            "energy": {
                "current": self.energy_now,
                "max": self.energy,
            },
            "hunger": self.hunger,
            "age": self.age,
            "longevity": self.longevity,
            "maturity": self.maturity,
            "combat": {
                "attack_now": self.attack_power_now,
                "attack_base": self.attack_power,
                "defence_now": self.defence_power_now,
                "defence_base": self.defence_power,
            },
            "morphology": {
                "size": (self.width, self.height),
                "base_size": (self.base_width, self.base_height),
                "mass": self.mass,
                "reach": self.reach,
                "perception_rays": self.perception_rays,
                "hearing_range": self.hearing_range,
                "maintenance_cost": self.maintenance_cost,
            },
            "targets": {
                "enemy": self._summarise_related(self.closest_enemy),
                "prey": self._summarise_related(self.closest_prey),
                "partner": self._summarise_related(self.closest_partner),
                "follower": self._summarise_related(self.closest_follower),
                "plant": self._summarise_plant(self.closest_plant),
            },
            "environment": {
                "biome": getattr(self.current_biome, "name", None),
                "effects": dict(self.environment_effects),
            },
            "social": {
                "in_group": self.in_group,
                "is_leader": self.is_leader,
                "leader_id": getattr(self.group_leader, "id", None),
                "group_size": len(self.group_neighbors),
                "group_strength": self.group_strength,
                "boid_tendency": self.boid_tendency,
                "social_tendency": self.social_tendency,
            },
            "behaviour": {
                "diet": self.diet,
                "foraging_focus": self._foraging_focus,
                "foraging": {
                    "is_foraging": self._foraging_focus,
                    "feeding_frames": self._feeding_frames,
                    "hunger": self.hunger,
                    "seek_threshold": settings.HUNGER_SEEK_THRESHOLD,
                    "relax_threshold": settings.HUNGER_RELAX_THRESHOLD,
                    "energy_ratio": self.energy_now / max(1, self.energy),
                    "meets_seek_threshold": self.hunger >= settings.HUNGER_SEEK_THRESHOLD,
                    "below_energy_trigger": self.energy_now < self.energy * 0.45,
                    "enemy_blocking": bool(
                        self.closest_enemy and self.closest_enemy.health_now > 0
                    ),
                    "closest_plant": self._summarise_plant(self.closest_plant),
                    "closest_prey": self._summarise_related(self.closest_prey),
                },
            },
            "reproduction": {
                "cooldown": self.reproduced_cooldown,
                "count": self.reproduced,
                "parents": list(self.parent_ids),
            },
            "memory": memory_dump,
            "development": {
                "skin_stage": self.skin_stage,
                "skin_label": describe_skin_stage(self.skin_stage).get("label"),
                "features": list(self.development_features),
            },
        }

        return snapshot


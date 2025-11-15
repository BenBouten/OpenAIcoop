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
from typing import Any, Deque, Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector2

from ..config import settings
from ..dna.development import describe_skin_stage, ensure_development_plan
from ..morphology import MorphologyGenotype, MorphStats, compute_morph_stats
from ..simulation.state import SimulationState
from ..world.world import BiomeRegion
from . import reproduction

logger = logging.getLogger("evolution.simulation")


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

        # Core DNA / stats
        self.dna_id = dna_profile["dna_id"]
        self.base_width = int(dna_profile["width"])
        self.base_height = int(dna_profile["height"])
        base_color = tuple(int(c) for c in dna_profile["color"])
        self.health = int(dna_profile["health"])
        self.maturity = int(dna_profile["maturity"])
        self.vision = float(dna_profile["vision"])
        self.energy = int(dna_profile["energy"])
        self.longevity = int(dna_profile["longevity"])
        self.generation = generation
        self.morphology: MorphologyGenotype = MorphologyGenotype.from_mapping(
            dna_profile.get("morphology", {})
        )
        self.morph_stats: MorphStats = compute_morph_stats(
            self.morphology, (self.base_width, self.base_height)
        )
        self.development = ensure_development_plan(dna_profile.get("development"))
        self.skin_stage = int(self.development.get("skin_stage", 0))
        self.development_features: Tuple[str, ...] = tuple(
            self.development.get("features", [])
        )
        tinted = self._apply_pigment(base_color, self.morph_stats.pigment_tint)
        self.body_color = self._apply_skin_development(tinted)
        self.color = self.body_color

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
        self.mass = self.morph_stats.mass
        self.reach = self.morph_stats.reach
        self.maintenance_cost = self.morph_stats.maintenance_cost
        self.speed_multiplier = self.morph_stats.ground_speed_multiplier
        self.traction_multiplier = self.morph_stats.traction
        self.turn_rate = max(0.05, self.morph_stats.turn_rate)
        self.fov_threshold = self.morph_stats.fov_cosine_threshold

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
        self.defence_power = dna_profile["defence_power"]
        self.attack_power = dna_profile["attack_power"]
        self.attack_power_now = self.attack_power
        self.defence_power_now = self.defence_power

        # Vital stats
        self.age = 0.0
        self.hunger = 0.0
        self.wounded = 0.0
        self.health_now = float(self.health)
        self.energy_now = float(self.energy)
        self._feeding_frames = 0  # hoelang staat dit beest al “aan tafel”

        # Reproduction
        self.reproduced = 0
        self.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE

        # Perception targets
        self.closest_prey: Optional[Lifeform] = None
        self.closest_enemy: Optional[Lifeform] = None
        self.closest_partner: Optional[Lifeform] = None
        self.closest_follower: Optional[Lifeform] = None
        self.closest_plant = None  # Vegetation instance

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

        # Behaviour / traits
        self.diet = dna_profile.get("diet", "omnivore")
        self.social_tendency = float(dna_profile.get("social", 0.5))
        self.risk_tolerance = float(dna_profile.get("risk_tolerance", 0.5))
        self.restlessness = float(dna_profile.get("restlessness", 0.5))
        if not math.isfinite(self.restlessness):
            self.restlessness = 0.5
        self.restlessness = max(0.0, min(1.0, self.restlessness))

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

        if self._foraging_focus and self.hunger <= settings.HUNGER_RELAX_THRESHOLD:
            self._foraging_focus = False

        if self._foraging_focus:
            return True

        if self.hunger >= settings.HUNGER_SEEK_THRESHOLD:
            self._foraging_focus = True
            return True

        if self.energy_now < self.energy * 0.45:
            return True

        return False

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

    def _plant_center(self, plant: "Vegetation") -> Tuple[float, float]:
        return (plant.x + plant.width / 2, plant.y + plant.height / 2)

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
        """Return the center-to-center distance between the lifeform and a plant."""

        center_x = plant.x + plant.width / 2
        center_y = plant.y + plant.height / 2
        dx = self.rect.centerx - center_x
        dy = self.rect.centery - center_y
        return math.sqrt(dx * dx + dy * dy)

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
        self.sensory_range = max(0.0, float(self.vision))
        vision_range = self.sensory_range
        if vision_range <= 0:
            self.closest_enemy = None
            self.closest_prey = None
            self.closest_partner = None
            self.closest_follower = None
            self.closest_plant = None
            return

        vision_sq = vision_range * vision_range
        hearing_range = vision_range + max(0.0, self.hearing_range)
        hearing_sq = max(vision_sq, hearing_range * hearing_range)
        close_range = self.reach + max(self.width, self.height) * 0.5
        close_range_sq = max(9.0, close_range * close_range)
        forward = Vector2(self.x_direction, self.y_direction)
        if forward.length_squared() == 0:
            forward = Vector2(1, 0)
        else:
            forward = forward.normalize()
        threshold = max(0.05, min(0.95, self.fov_threshold))
        threshold_sq = threshold * threshold

        enemy_candidate = None
        prey_candidate = None
        partner_candidate = None
        follower_candidate = None
        plant_candidate = None

        enemy_distance = vision_sq
        prey_distance = vision_sq
        partner_distance = vision_sq
        follower_distance = vision_sq
        plant_distance = vision_sq

        for lifeform in self.state.lifeforms:
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
                if distance_sq <= 1e-6:
                    fov_ok = True
                else:
                    dot = forward.x * dx + forward.y * dy
                    if dot > 0 and dot * dot >= threshold_sq * distance_sq:
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

        for plant in self.state.plants:
            if plant.resource <= 0:
                continue

            center_x = plant.x + plant.width / 2
            center_y = plant.y + plant.height / 2
            dx = center_x - self.rect.centerx
            dy = center_y - self.rect.centery
            distance_sq = float(dx * dx + dy * dy)
            if distance_sq > vision_sq:
                continue
            in_close = distance_sq <= close_range_sq
            if not in_close:
                if distance_sq <= 1e-6:
                    pass
                else:
                    dot = forward.x * dx + forward.y * dy
                    if not (dot > 0 and dot * dot >= threshold_sq * distance_sq):
                        continue
            if distance_sq < plant_distance:
                plant_candidate = plant
                plant_distance = distance_sq

        self.closest_enemy = enemy_candidate
        self.closest_prey = prey_candidate
        self.closest_partner = partner_candidate
        self.closest_follower = follower_candidate if not self.is_leader else None
        self.closest_plant = plant_candidate

    def set_size(self) -> None:
        self.size = self.width * self.height * max(0.5, self.mass)
        if self.width < 1:
            self.width = 1
        if self.height < 1:
            self.height = 1

    def check_group(self) -> None:
        relevant_radius = min(self.vision, settings.GROUP_MAX_RADIUS)
        if relevant_radius <= 0:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0
            self.group_state_timer = 0
            return

        neighbors: List[Tuple[Lifeform, float]] = []
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
        elif self.group_state_timer > 0:
            self.group_state_timer -= 1
            self.in_group = True
        else:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0

    # ------------------------------------------------------------------
    # Stats / combat / lifecycle
    # ------------------------------------------------------------------
    def set_speed(self, average_maturity: Optional[float] = None) -> None:
        base_speed = (
            6
            - (self.hunger / 500)
            - (self.age / 1000)
            - (self.size / 250)
            - (self.wounded / 20)
        )
        base_speed += self.health_now / 200
        base_speed += self.energy / 100

        biome, effects = self.state.world.get_environment_context(
            self.x + self.width / 2,
            self.y + self.height / 2,
        )
        self.current_biome = biome
        self.environment_effects = effects
        base_speed *= float(effects["movement"])

        for plant in self.state.plants:
            if plant.resource <= 0:
                continue
            if plant.contains_point(self.rect.centerx, self.rect.centery):
                base_speed *= plant.movement_modifier_for(self)
                break

        if self.age < self.maturity:
            if average_maturity is None and self.state.lifeforms:
                average_maturity = sum(l.maturity for l in self.state.lifeforms) / len(
                    self.state.lifeforms
                )
            if average_maturity:
                factor = self.maturity / average_maturity
                base_speed *= factor / 10

        base_speed *= self.speed_multiplier
        base_speed *= self.traction_multiplier
        base_speed /= max(0.75, self.mass)

        base_speed = max(0.45, min(14.0, base_speed))
        pause_factor = getattr(self, "_wander_pause_speed_factor", 1.0)
        base_speed *= pause_factor
        base_speed = min(14.0, base_speed)
        base_speed = max(0.05, base_speed)
        self.speed = base_speed

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
        self.attack_power_now += (self.size - 50) * 0.8
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
        self.defence_power_now += (self.size - 50) * 0.8
        self.defence_power_now -= self.hunger * 0.1
        self.defence_power_now *= self.calculate_age_factor()
        defence_bonus = 1.0 + (self.traction_multiplier - 1.0) * 0.25
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
                "group_size": len(self.group_neighbors),
                "group_strength": self.group_strength,
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


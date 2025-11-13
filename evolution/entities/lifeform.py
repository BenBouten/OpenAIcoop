"""Lifeform entity logic extracted from the simulation module.

This class owns:
- DNA-based attributes and species characteristics
- Local memory (food, threats, partners, visited)
- Behaviour / AI decisions (who to flee, hunt, follow, etc.)
- Grouping logic, combat stats, reproduction and progression

Generic movement / collision resolution should be done in `movement.py`,
which calls into this class (e.g. `_update_behavior_state`, `_handle_close_interactions`).
"""

from __future__ import annotations

import logging
import math
import random
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple

import pygame
from pygame.math import Vector2

from ..config import settings
from ..simulation.state import SimulationState
from ..world.world import BiomeRegion
from .pheromones import Pheromone

logger = logging.getLogger("evolution.simulation")


class Lifeform:
    def __init__(
        self,
        state: SimulationState,
        x: float,
        y: float,
        dna_profile: dict,
        generation: int,
    ) -> None:
        self.state = state

        # Position & direction
        self.x = x
        self.y = y
        self.x_direction = 0.0
        self.y_direction = 0.0

        # Core DNA / stats
        self.dna_id = dna_profile["dna_id"]
        self.width = dna_profile["width"]
        self.height = dna_profile["height"]
        self.color = dna_profile["color"]
        self.health = dna_profile["health"]
        self.maturity = dna_profile["maturity"]
        self.vision = dna_profile["vision"]
        self.energy = dna_profile["energy"]
        self.longevity = dna_profile["longevity"]
        self.generation = generation

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
        self.angular_velocity = 0.1

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

        # Local memory buffers
        self.memory: Dict[str, Deque[dict]] = {
            "visited": deque(maxlen=settings.MEMORY_MAX_VISITED),
            "food": deque(maxlen=settings.MEMORY_MAX_FOOD),
            "threats": deque(maxlen=settings.MEMORY_MAX_THREATS),
            "partner": deque(maxlen=settings.MEMORY_MAX_PARTNERS),
        }

        # Wander / escape state
        initial_wander = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
        if initial_wander.length_squared() == 0:
            initial_wander = Vector2(1, 0)
        self.wander_direction = initial_wander.normalize()
        self.last_wander_update = 0
        self._stuck_frames = 0
        self._boundary_contact_frames = 0
        self._escape_timer = 0
        self._escape_vector = Vector2()

    # ------------------------------------------------------------------
    # Convenience: access to global notification context via state
    # ------------------------------------------------------------------
    @property
    def notification_context(self):
        return getattr(self.state, "notification_context", None)

    # ------------------------------------------------------------------
    # Behaviour / AI – decides desired direction (x/y) and wander state
    # ------------------------------------------------------------------
    def _update_behavior_state(self) -> None:
        """Compute the desired movement direction based on memory, threats, food, groups."""
        now = pygame.time.get_ticks()
        self._cleanup_memory(now)
        self._remember("visited", (self.x, self.y), now, weight=1.0)

        self.update_targets()
        self._record_current_observations(now)

        desired = Vector2()

        # Flee threats first
        threat_vector = self._compute_threat_vector(now)
        if threat_vector.length_squared() > 0:
            desired += threat_vector
        else:
            # Seek food / partners
            pursuit_vector = self._compute_pursuit_vector(now)
            desired += pursuit_vector
            if pursuit_vector.length_squared() == 0:
                desired += self._memory_target_vector(now)

        # Social / grouping & exploration
        desired += self._group_behavior_vector()
        desired += self._avoid_recent_positions(now)

        # If nothing decided: wander
        if desired.length_squared() == 0:
            desired = self._wander_vector(now)
            self.search = True
        else:
            self.search = False

        # If still nothing, keep current direction or default
        if desired.length_squared() == 0:
            desired = Vector2(self.x_direction, self.y_direction)
            if desired.length_squared() == 0:
                desired = Vector2(1, 0)

        desired = desired.normalize()
        self.wander_direction = desired
        self.x_direction = desired.x
        self.y_direction = desired.y

    def _handle_close_interactions(self) -> None:
        """
        Handle very short-range interactions:
        - Melee attacks vs enemy
        - Eating prey / plants
        - Reproduction with partner
        """
        context = self.notification_context

        # Enemy: attack in melee
        if self.closest_enemy and self.closest_enemy.health_now > 0:
            if self.distance_to(self.closest_enemy) < 5:
                damage = max(1, self.attack_power_now - self.closest_enemy.defence_power_now / 2)
                self.closest_enemy.health_now -= damage
                self.closest_enemy.wounded += 2

        # Prey: attack and eat
        if (
            self.closest_prey
            and self.closest_prey.health_now > 0
            and self._diet_prefers_meat()
            and self.closest_enemy is None
        ):
            if self.distance_to(self.closest_prey) < 5:
                damage = max(1, self.attack_power_now - self.closest_prey.defence_power_now / 2)
                self.closest_prey.health_now -= damage
                self.closest_prey.wounded += 3
                self.hunger = max(0, self.hunger - 40)
                if context:
                    context.action(f"{self.id} valt {self.closest_prey.id} aan")

        # Partner: reproduction
        if (
            self.closest_partner
            and self.closest_partner.health_now > 0
            and self.closest_partner.hunger < settings.HUNGER_CRITICAL_THRESHOLD
            and self._ready_to_reproduce()
        ):
            if self.distance_to(self.closest_partner) < 3:
                self.reproduce(self.closest_partner)

        # Plants: eat vegetation
        if (
            self.closest_plant
            and self.closest_enemy is None
            and self._diet_prefers_plants()
            and self.closest_plant.resource > 10
        ):
            if self.distance_to(self.closest_plant) < 3:
                if context:
                    context.action(f"{self.id} eet van een plant")
                self.closest_plant.apply_effect(self)
                self.closest_plant.decrement_resource(12)
                self.hunger = max(0, self.hunger - 60)

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------
    def _cleanup_memory(self, timestamp: int) -> None:
        for key, buffer in self.memory.items():
            while buffer and timestamp - buffer[0]["time"] > settings.MEMORY_DECAY_MS:
                buffer.popleft()

    def _remember(
        self,
        kind: str,
        position: Tuple[float, float],
        timestamp: int,
        weight: float = 1.0,
    ) -> None:
        if kind not in self.memory:
            return
        entry = {"pos": position, "time": timestamp, "weight": float(weight)}
        self.memory[kind].append(entry)

    def _recall(self, kind: str, timestamp: int) -> Optional[Tuple[float, float]]:
        buffer = self.memory.get(kind)
        if not buffer:
            return None

        candidates: List[Tuple[float, Tuple[float, float]]] = []
        for entry in buffer:
            age = timestamp - entry["time"]
            if age > settings.MEMORY_DECAY_MS:
                continue
            decay_factor = max(0.0, 1.0 - age / settings.MEMORY_DECAY_MS)
            weight = entry.get("weight", 1.0) * (0.5 + 0.5 * decay_factor)
            candidates.append((weight, entry["pos"]))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _record_current_observations(self, timestamp: int) -> None:
        if self.closest_enemy and self.closest_enemy.health_now > 0:
            self._remember(
                "threats",
                (self.closest_enemy.x, self.closest_enemy.y),
                timestamp,
                weight=1.0 + (1.0 - self.risk_tolerance),
            )

        if (
            self.closest_prey
            and self.closest_prey.health_now > 0
            and self._diet_prefers_meat()
        ):
            weight = max(20.0, self.attack_power_now + self.hunger)
            self._remember("food", (self.closest_prey.x, self.closest_prey.y), timestamp, weight=weight)

        if (
            self.closest_plant
            and self.closest_plant.resource > 0
            and self._diet_prefers_plants()
        ):
            weight = self.closest_plant.resource + max(0, self.hunger - 50)
            self._remember("food", self._plant_center(self.closest_plant), timestamp, weight=weight)

        if self.closest_partner and self.closest_partner.health_now > 0:
            partner_weight = 1.0 + self.social_tendency
            self._remember(
                "partner",
                (self.closest_partner.x, self.closest_partner.y),
                timestamp,
                weight=partner_weight,
            )

    # ------------------------------------------------------------------
    # Behaviour vectors (all DNA / trait dependent)
    # ------------------------------------------------------------------
    def _compute_threat_vector(self, timestamp: int) -> Vector2:
        if self.closest_enemy and self.closest_enemy.health_now > 0:
            direction, distance = self._direction_to_lifeform(self.closest_enemy)
            if distance > 0:
                strength = max(0.2, 1.0 - self.risk_tolerance * 0.8)
                return direction * -strength

        remembered_threat = self._recall("threats", timestamp)
        if remembered_threat:
            direction, distance = self._direction_to_point(remembered_threat)
            if distance > 0:
                strength = max(0.1, 1.0 - self.risk_tolerance)
                return direction * -strength

        return Vector2()

    def _compute_pursuit_vector(self, timestamp: int) -> Vector2:
        desired = Vector2()

        if self._should_seek_food():
            food_vector = self._immediate_food_vector()
            if food_vector.length_squared() == 0:
                remembered_food = self._recall("food", timestamp)
                if remembered_food:
                    direction, _ = self._direction_to_point(remembered_food)
                    desired += direction
            else:
                desired += food_vector
        else:
            desired += self._opportunistic_food_vector()

        if desired.length_squared() == 0 and self._ready_to_reproduce():
            if self.closest_partner and self.closest_partner.health_now > 0:
                direction, _ = self._direction_to_lifeform(self.closest_partner)
                desired += direction
            else:
                remembered_partner = self._recall("partner", timestamp)
                if remembered_partner:
                    direction, _ = self._direction_to_point(remembered_partner)
                    desired += direction

        return desired

    def _memory_target_vector(self, timestamp: int) -> Vector2:
        target = None
        if self._ready_to_reproduce():
            target = self._recall("partner", timestamp)
        if target is None and self._should_seek_food():
            target = self._recall("food", timestamp)
        if target is None:
            return Vector2()
        direction, _ = self._direction_to_point(target)
        return direction

    def _group_behavior_vector(self) -> Vector2:
        if not self.in_group or not self.group_neighbors:
            return Vector2()

        alignment = Vector2()
        cohesion_positions = Vector2()
        separation = Vector2()
        active_neighbors = 0

        for neighbor in self.group_neighbors:
            if neighbor.health_now <= 0:
                continue
            alignment += Vector2(neighbor.x_direction, neighbor.y_direction)
            cohesion_positions += Vector2(neighbor.x, neighbor.y)
            offset = Vector2(self.x - neighbor.x, self.y - neighbor.y)
            distance = offset.length()
            if 0 < distance < settings.BOID_SEPARATION_DISTANCE:
                separation += offset.normalize() * (1.0 - distance / settings.BOID_SEPARATION_DISTANCE)
            active_neighbors += 1

        if active_neighbors == 0:
            return Vector2()

        if alignment.length_squared() > 0:
            alignment = alignment.normalize()
        cohesion = (cohesion_positions / active_neighbors) - Vector2(self.x, self.y)
        if cohesion.length_squared() > 0:
            cohesion = cohesion.normalize()
        if separation.length_squared() > 0:
            separation = separation.normalize()

        influence = Vector2()
        influence += alignment * settings.BOID_ALIGNMENT_WEIGHT * self.social_tendency
        influence += cohesion * settings.BOID_COHESION_WEIGHT * self.social_tendency
        influence += separation * settings.BOID_SEPARATION_WEIGHT

        if self.closest_follower and not self.is_leader and self.closest_follower.health_now > 0:
            follow_direction, _ = self._direction_to_lifeform(self.closest_follower)
            influence += follow_direction * 0.35 * self.social_tendency

        return influence

    def _avoid_recent_positions(self, timestamp: int) -> Vector2:
        buffer = self.memory.get("visited")
        if not buffer:
            return Vector2()

        repulsion = Vector2()
        for entry in buffer:
            age = timestamp - entry["time"]
            if age > settings.RECENT_VISIT_MEMORY_MS:
                continue
            offset = Vector2(self.x - entry["pos"][0], self.y - entry["pos"][1])
            distance_sq = offset.length_squared()
            if distance_sq == 0:
                continue
            repulsion += offset / (distance_sq + 1)

        if repulsion.length_squared() == 0:
            return Vector2()

        return repulsion.normalize() * 0.4

    def _wander_vector(self, timestamp: int) -> Vector2:
        if timestamp - self.last_wander_update > settings.WANDER_INTERVAL_MS:
            jitter = random.uniform(-settings.WANDER_JITTER_DEGREES, settings.WANDER_JITTER_DEGREES)
            self.wander_direction = self.wander_direction.rotate(jitter)
            if self.wander_direction.length_squared() == 0:
                self.wander_direction = Vector2(1, 0)
            else:
                self.wander_direction = self.wander_direction.normalize()
            self.last_wander_update = timestamp

        noise = Vector2(random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2))
        wander = self.wander_direction + noise
        if wander.length_squared() == 0:
            wander = Vector2(1, 0)
        return wander.normalize()

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
    def _diet_prefers_plants(self) -> bool:
        return self.diet in ("herbivore", "omnivore")

    def _diet_prefers_meat(self) -> bool:
        return self.diet in ("carnivore", "omnivore")

    def _should_seek_food(self) -> bool:
        if self.hunger >= settings.HUNGER_SEEK_THRESHOLD:
            return True
        if self.energy_now < self.energy * 0.45:
            return True
        return False

    def _ready_to_reproduce(self) -> bool:
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

    def _immediate_food_vector(self) -> Vector2:
        candidates: List[Tuple[float, Vector2]] = []

        if (
            self.closest_plant
            and self._diet_prefers_plants()
            and self.closest_plant.resource > 0
            and self.closest_enemy is None
        ):
            direction, distance = self._direction_to_point(self._plant_center(self.closest_plant))
            if distance > 0:
                weight = self.closest_plant.resource + max(0, self.hunger - 80)
                score = weight / (distance + 1)
                candidates.append((score, direction))

        if (
            self.closest_prey
            and self._diet_prefers_meat()
            and self.closest_prey.health_now > 0
            and self.closest_enemy is None
        ):
            direction, distance = self._direction_to_lifeform(self.closest_prey)
            if distance > 0:
                weight = self.attack_power_now + max(30, self.hunger)
                score = weight / (distance + 1)
                candidates.append((score, direction))

        if not candidates:
            return Vector2()

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _opportunistic_food_vector(self) -> Vector2:
        if (
            self.closest_prey
            and self._diet_prefers_meat()
            and self.closest_enemy is None
        ):
            direction, distance = self._direction_to_lifeform(self.closest_prey)
            if distance > 0 and distance < max(12, self.vision * 0.6):
                return direction

        if (
            self.closest_plant
            and self._diet_prefers_plants()
            and self.closest_enemy is None
        ):
            direction, distance = self._direction_to_point(self._plant_center(self.closest_plant))
            if distance > 0 and distance < max(10, self.vision * 0.5):
                return direction

        return Vector2()

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
    def _can_partner_with(self, other: "Lifeform") -> bool:
        if other is self:
            return False
        if other.health_now <= 0:
            return False
        if other.dna_id != self.dna_id:
            return False
        if not self.is_adult() or not other.is_adult():
            return False
        return True

    def update_targets(self) -> None:
        vision_range = max(0, self.vision)
        if vision_range <= 0:
            self.closest_enemy = None
            self.closest_prey = None
            self.closest_partner = None
            self.closest_follower = None
            self.closest_plant = None
            return

        vision_sq = vision_range * vision_range

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

            distance_sq = self._distance_squared_to_lifeform(lifeform)
            if distance_sq > vision_sq:
                continue

            if not self.is_leader and lifeform.is_leader and distance_sq < follower_distance:
                follower_candidate = lifeform
                follower_distance = distance_sq

            if self._can_partner_with(lifeform):
                if distance_sq < partner_distance:
                    partner_candidate = lifeform
                    partner_distance = distance_sq
                continue

            if lifeform.dna_id == self.dna_id:
                # Avoid classifying the same species as prey or enemy.
                continue

            if lifeform.attack_power_now > self.defence_power_now:
                if distance_sq < enemy_distance:
                    enemy_candidate = lifeform
                    enemy_distance = distance_sq
                continue

            if lifeform.attack_power_now < self.defence_power_now:
                if distance_sq < prey_distance:
                    prey_candidate = lifeform
                    prey_distance = distance_sq

        for plant in self.state.plants:
            if plant.resource <= 0:
                continue

            center_x = plant.x + plant.width / 2
            center_y = plant.y + plant.height / 2
            distance_sq = self._distance_squared_to_point(center_x, center_y)
            if distance_sq > vision_sq:
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
        self.size = self.width * self.height
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
        self.speed = 6 - (self.hunger / 500) - (self.age / 1000) - (self.size / 250) - (
            self.wounded / 20
        )
        self.speed += self.health_now / 200
        self.speed += self.energy / 100

        biome, effects = self.state.world.get_environment_context(
            self.x + self.width / 2,
            self.y + self.height / 2,
        )
        self.current_biome = biome
        self.environment_effects = effects
        self.speed *= float(effects["movement"])

        if self.age < self.maturity:
            if average_maturity is None and self.state.lifeforms:
                average_maturity = sum(l.maturity for l in self.state.lifeforms) / len(
                    self.state.lifeforms
                )
            if average_maturity:
                factor = self.maturity / average_maturity
                self.speed *= factor / 10

        if self.speed < 1:
            self.speed = 1
        if self.speed > 12:
            self.speed = 12

    def handle_death(self) -> bool:
        if self.health_now > 0:
            return False

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

        if self.defence_power_now < 1:
            self.defence_power_now = 1
        if self.defence_power_now > 100:
            self.defence_power_now = 100

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
            return False

        child_dna_profile = {
            "dna_id": self.dna_id,
            "width": (self.width + partner.width) // 2,
            "height": (self.height + partner.height) // 2,
            "color": self.color,
            "health": (self.health + partner.health) // 2,
            "maturity": (self.maturity + partner.maturity) // 2,
            "vision": (self.vision + partner.vision) // 2,
            "defence_power": (self.defence_power + partner.defence_power) // 2,
            "attack_power": (self.attack_power + partner.attack_power) // 2,
            "energy": (self.energy + partner.energy) // 2,
            "longevity": (self.longevity + partner.longevity) // 2,
            "diet": self.diet,
            "social": (self.social_tendency + partner.social_tendency) / 2,
            "risk_tolerance": (self.risk_tolerance + partner.risk_tolerance) / 2,
        }

        if random.randint(0, 100) < settings.MUTATION_CHANCE:
            child_dna_profile["vision"] = max(
                settings.VISION_MIN,
                min(
                    settings.VISION_MAX,
                    child_dna_profile["vision"] + random.randint(-3, 3),
                ),
            )
            child_dna_profile["health"] = max(
                1, child_dna_profile["health"] + random.randint(-5, 5)
            )
            child_dna_profile["maturity"] = max(
                settings.MIN_MATURITY,
                min(
                    settings.MAX_MATURITY,
                    child_dna_profile["maturity"] + random.randint(-10, 10),
                ),
            )
            child_dna_profile["energy"] = max(
                1, child_dna_profile["energy"] + random.randint(-3, 3)
            )
            child_dna_profile["longevity"] = max(
                100, child_dna_profile["longevity"] + random.randint(-20, 20)
            )
            child_dna_profile["social"] = min(
                1.0,
                max(0.0, child_dna_profile["social"] + random.uniform(-0.05, 0.05)),
            )
            child_dna_profile["risk_tolerance"] = min(
                1.0,
                max(
                    0.0,
                    child_dna_profile["risk_tolerance"]
                    + random.uniform(-0.05, 0.05),
                ),
            )

        child = Lifeform(self.state, self.x, self.y, child_dna_profile, self.generation + 1)
        child.color = self.color
        self.state.lifeforms.append(child)

        player = getattr(self.state, "player", None)
        if player:
            player.on_birth()

        context = self.notification_context
        if context:
            context.action(f"Nieuwe levensvorm geboren uit {self.id}")

        logger.info(
            "Lifeform %s reproduced with %s producing %s at (%.1f, %.1f)",
            self.id,
            partner.id,
            child.id,
            self.x,
            self.y,
        )

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
        self.hunger += hunger_rate * settings.HUNGER_RATE_PER_SECOND * delta_time
        self.age += settings.AGE_RATE_PER_SECOND * delta_time
        self.energy_now += (
            settings.ENERGY_RECOVERY_PER_SECOND
            * delta_time
            * float(effects["energy"])
        )
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
    # Visual trail / pheromones
    # ------------------------------------------------------------------
    def add_tail(self) -> None:
        pheromone = Pheromone(self.x, self.y, self.width, self.height, self.color, 100)
        self.state.pheromones.append(pheromone)

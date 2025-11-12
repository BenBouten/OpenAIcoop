"""Core simulation loop and entities for the evolution project."""
from __future__ import annotations

import datetime
import math
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pygame

from . import settings
from .camera import Camera
from .events import EventManager
from .notifications import NotificationManager
from .player import PlayerController
from .world import BiomeRegion, World


@dataclass
class NotificationContext:
    notification_manager: NotificationManager
    show_debug: bool = False
    show_action: bool = False

    def debug(self, message: str, duration: Optional[int] = None) -> None:
        if self.show_debug:
            self.notification_manager.add(message, settings.BLUE, duration)

    def action(self, message: str, duration: Optional[int] = None) -> None:
        if self.show_action:
            self.notification_manager.add(message, settings.SEA, duration)


notification_context = NotificationContext(NotificationManager())


class Lifeform:
    def __init__(self, x, y, dna_profile, generation):
        global lifeform_id_counter

        self.x = x
        self.y = y
        self.x_direction = 0
        self.y_direction = 0

        self.dna_id = dna_profile['dna_id']
        self.width = dna_profile['width']
        self.height = dna_profile['height']
        self.color = dna_profile['color']
        self.health = dna_profile['health']
        self.maturity = dna_profile['maturity']
        self.vision = dna_profile['vision']
        self.energy = dna_profile['energy']
        self.longevity = dna_profile['longevity']
        self.generation = generation

        self.initial_height = self.height
        self.initial_width = self.width

        self.id = str(self.dna_id) + "_" + str(lifeform_id_counter)
        lifeform_id_counter += 1

        self.dna_id_count = 0

        self.size = 0
        self.speed = 0
        self.angle = 0
        self.angular_velocity = 0.1

        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)

        self.defence_power = dna_profile['defence_power']
        self.attack_power = dna_profile['attack_power']

        self.attack_power_now = self.attack_power
        self.defence_power_now = self.defence_power

        self.age = 0
        self.hunger = 0
        self.wounded = 0
        self.health_now = self.health
        self.energy_now = self.energy

        self.reproduced = 0
        self.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE

        self.closest_prey = None
        self.closest_enemy = None
        self.closest_partner = None
        self.closest_follower = None
        self.closest_plant = None

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

        self.follow_range = 30

        self.is_leader = False

        self.search = False
        self.in_group = False
        self.group_neighbors = []
        self.group_center = None
        self.group_strength = 0
        self.group_state_timer = 0

    def movement(self):
        previous_position = (self.x, self.y)
        attempted_x = self.x + self.x_direction * self.speed
        attempted_y = self.y + self.y_direction * self.speed

        candidate_rect = self.rect.copy()
        candidate_rect.update(int(attempted_x), int(attempted_y), self.width, self.height)
        (
            resolved_x,
            resolved_y,
            hit_boundary_x,
            hit_boundary_y,
            collided,
        ) = world.resolve_entity_movement(candidate_rect, previous_position, (attempted_x, attempted_y))

        if collided:
            self.x_direction = -self.x_direction
            self.y_direction = -self.y_direction
        else:
            if hit_boundary_x:
                self.x_direction = -self.x_direction
            if hit_boundary_y:
                self.y_direction = -self.y_direction

        self.x, self.y = resolved_x, resolved_y
        self.rect.update(int(self.x), int(self.y), self.width, self.height)

        self.update_targets()

        if self.closest_enemy:
            notification_context.debug(f"{self.id} ziet vijand {self.closest_enemy.id}")
        if self.closest_prey:
            notification_context.debug(f"{self.id} heeft prooi {self.closest_prey.id}")
        if self.closest_partner:
            notification_context.debug(f"{self.id} heeft partner {self.closest_partner.id}")

        if self.closest_enemy and self.closest_enemy.health_now > 0:
            x_diff = self.closest_enemy.x - self.x
            y_diff = self.closest_enemy.y - self.y
            if math.hypot(x_diff, y_diff) < 5:
                damage = max(1, self.attack_power_now - self.closest_enemy.defence_power_now / 2)
                self.closest_enemy.health_now -= damage
                self.closest_enemy.wounded += 2
            if x_diff == 0 and y_diff == 0:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance

        if (
            self.closest_prey
            and self.closest_prey.health_now > 0
            and self.closest_enemy is None
            and self.closest_partner is None
            and self.closest_prey.hunger < 500
        ):
            x_diff = self.closest_prey.x - self.x
            y_diff = self.closest_prey.y - self.y
            if math.hypot(x_diff, y_diff) < 5:
                damage = max(1, self.attack_power_now - self.closest_prey.defence_power_now / 2)
                self.closest_prey.health_now -= damage
                self.closest_prey.wounded += 3
                self.hunger -= 40
                if self.hunger < 0:
                    self.hunger = 0
                notification_context.action(f"{self.id} valt {self.closest_prey.id} aan")
            if x_diff == 0 and y_diff == 0:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance

        if (
            self.closest_partner
            and self.closest_partner.health_now > 0
            and self.closest_enemy is None
            and self.closest_prey is None
            and self.closest_partner.hunger < 500
        ):
            x_diff = self.closest_partner.x - self.x
            y_diff = self.closest_partner.y - self.y
            if self.distance_to(self.closest_partner) < 3 and self.age > self.maturity and self.reproduced_cooldown == 0:
                self.reproduce(self.closest_partner)
            if x_diff == 0 and y_diff == 0:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance

        if self.closest_plant and self.hunger > 250 and not self.closest_enemy and not self.closest_partner and self.closest_plant.resource > 10:
            x_diff = self.closest_plant.x - self.x
            y_diff = self.closest_plant.y - self.y
            if self.distance_to(self.closest_plant) < 3:
                notification_context.action(f"{self.id} eet van een plant")
                self.closest_plant.apply_effect(self)
                self.closest_plant.decrement_resource(12)
                self.hunger -= 60
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance

        if self.in_group and not self.closest_enemy and not self.closest_prey and not self.closest_partner and not self.closest_plant and self.group_center:
            x_diff = self.group_center[0] - self.x
            y_diff = self.group_center[1] - self.y
            total_distance = math.hypot(x_diff, y_diff)
            if total_distance > self.follow_range:
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance
                self.search = False

        if not self.search and not self.closest_enemy and not self.closest_prey and not self.closest_partner and not self.closest_plant:
            notification_context.debug(f"{self.id} zoekt naar doelen")
            self.x_direction = random.uniform(-1, 1)
            self.y_direction = random.uniform(-1, 1)
            self.search = True

        if self.search:
            if self.closest_follower and not self.is_leader and self.closest_follower.closest_follower != self and self.hunger < 500:
                x_diff = self.closest_follower.x - self.x
                y_diff = self.closest_follower.y - self.y
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                if total_distance > 0:
                    if total_distance > self.follow_range:
                        self.x_direction = x_diff / total_distance
                        self.y_direction = y_diff / total_distance
                    else:
                        self.x_direction = -x_diff / total_distance
                        self.y_direction = -y_diff / total_distance
                else:
                    self.x_direction = random.uniform(-1, 1)
                    self.y_direction = random.uniform(-1, 1)
            elif random.randint(0, 100) < 25:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
            notification_context.debug(f"{self.id} zoekstatus: {self.search}")

    def add_tail(self):
        pheromone = Pheromone(self.x, self.y, self.width, self.height, self.color, 100)
        pheromones.append(pheromone)

    def distance_to(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx ** 2 + dy ** 2)

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

        for lifeform in lifeforms:
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

            if lifeform.attack_power_now > self.defence_power_now:
                if distance_sq < enemy_distance:
                    enemy_candidate = lifeform
                    enemy_distance = distance_sq
                continue

            if lifeform.attack_power_now < self.defence_power_now:
                if distance_sq < prey_distance:
                    prey_candidate = lifeform
                    prey_distance = distance_sq

        for plant in plants:
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

    def set_size(self):
        self.size = self.width * self.height
        if self.width < 1:
            self.width = 1
        if self.height < 1:
            self.height = 1

    def check_group(self):
        relevant_radius = min(self.vision, settings.GROUP_MAX_RADIUS)
        if relevant_radius <= 0:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0
            self.group_state_timer = 0
            return

        neighbors = []
        total_distance = 0
        total_x = self.x
        total_y = self.y

        for lifeform in lifeforms:
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
        elif self.group_state_timer > 0:
            self.group_state_timer -= 1
            self.in_group = True
        else:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0

    def set_speed(self):
        self.speed = 6 - (self.hunger / 500) - (self.age / 1000) - (self.size / 250) - (self.wounded / 20)
        self.speed += (self.health_now / 200)
        self.speed += (self.energy / 100)

        biome, effects = world.get_environment_context(self.x + self.width / 2, self.y + self.height / 2)
        self.current_biome = biome
        self.environment_effects = effects
        self.speed *= float(effects["movement"])

        if self.age < self.maturity and lifeforms:
            average_maturity = sum(l.maturity for l in lifeforms) / len(lifeforms)
            if average_maturity:
                factor = self.maturity / average_maturity
                self.speed *= (factor / 10)

        if self.speed < 1:
            self.speed = 1

        if self.speed > 12:
            self.speed = 12

    def draw(self, surface):
        if self.health_now > 0:
            if show_vision:
                pygame.draw.circle(surface, settings.GREEN, (self.x, self.y), self.vision, 1)

            rect = pygame.Surface((self.width, self.height))
            rect.set_colorkey(settings.BLACK)
            rect.fill(self.color)
            rect_rotated = pygame.transform.rotate(rect, self.angle)
            rect.get_rect()
            surface.blit(rect_rotated, (self.x, self.y))

            outline_copy = pygame.Surface((self.width + 4, self.height + 4))
            outline_copy.set_colorkey(settings.BLACK)
            red_value = int(self.attack_power_now * 2.55)
            blue_value = int(self.defence_power_now * 2.55)
            color = pygame.Color(red_value, 0, blue_value)
            pygame.draw.rect(outline_copy, color, (0, 0, self.width + 2, self.height + 2), 1)
            outline_copy = pygame.transform.rotate(outline_copy, self.angle)
            surface.blit(outline_copy, (self.x, self.y))

        else:
            notification_context.action(f"{self.id} is gestorven")
            lifeforms.remove(self)
            death_ages.append(self.age)

    def update_angle(self):
        self.angle = math.degrees(math.atan2(self.y_direction, self.x_direction))

    def calculate_age_factor(self):
        age_factor = 1
        if self.age > self.longevity:
            age_factor = age_factor * 0.9 ** (self.age - self.longevity)
        return age_factor

    def calculate_attack_power(self):
        self.attack_power_now = self.attack_power * (self.energy_now / 100)
        self.attack_power_now -= self.attack_power * (self.wounded / 100)
        self.attack_power_now += (self.size - 50) * 0.8
        self.attack_power_now -= (self.hunger * 0.1)
        self.attack_power_now *= self.calculate_age_factor()

        if self.attack_power_now < 1:
            self.attack_power_now = 1
        if self.attack_power_now > 100:
            self.attack_power_now = 100

    def calculate_defence_power(self):
        self.defence_power_now = self.defence_power * (self.energy_now / 100)
        self.defence_power_now -= self.defence_power * (self.wounded /100)
        self.defence_power_now += (self.size - 50) * 0.8
        self.defence_power_now -= (self.hunger * 0.1)
        self.defence_power_now *= self.calculate_age_factor()

        if self.defence_power_now < 1:
            self.defence_power_now = 1
        if self.defence_power_now > 100:
            self.defence_power_now = 100

    def grow(self):
        if self.age < self.maturity:
            factor = self.age / self.maturity
            self.height = self.initial_height * factor
            self.width = self.initial_width * factor

    def reproduce(self, partner):
        child_dna_profile = {
                'dna_id': self.dna_id,
                'width': (self.width + partner.width) // 2,
                'height': (self.height + partner.height) // 2,
                'color': self.color,
                'health': (self.health + partner.health) // 2,
                'maturity': (self.maturity + partner.maturity) // 2,
                'vision': (self.vision + partner.vision) // 2,
                'defence_power': (self.defence_power + partner.defence_power) // 2,
                'attack_power': (self.attack_power + partner.attack_power) // 2,
                'energy': (self.energy + partner.energy) // 2,
                'longevity': (self.longevity + partner.longevity) // 2
            }
        if random.randint(0, 100) < settings.MUTATION_CHANCE:
            child_dna_profile['vision'] = max(settings.VISION_MIN, min(settings.VISION_MAX, child_dna_profile['vision'] + random.randint(-3, 3)))
            child_dna_profile['health'] = max(1, child_dna_profile['health'] + random.randint(-5, 5))
            child_dna_profile['maturity'] = max(settings.MIN_MATURITY, min(settings.MAX_MATURITY, child_dna_profile['maturity'] + random.randint(-10, 10)))
            child_dna_profile['energy'] = max(1, child_dna_profile['energy'] + random.randint(-3, 3))
            child_dna_profile['longevity'] = max(100, child_dna_profile['longevity'] + random.randint(-20, 20))

        child = Lifeform(self.x, self.y, child_dna_profile, self.generation + 1)
        child.color = self.color
        lifeforms.append(child)
        player_controller.on_birth()
        notification_context.action(f"Nieuwe levensvorm geboren uit {self.id}")
        self.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE
        partner.reproduced_cooldown = settings.REPRODUCING_COOLDOWN_VALUE

    def progression(self):
        biome, effects = world.get_environment_context(self.x + self.width / 2, self.y + self.height / 2)
        self.current_biome = biome
        self.environment_effects = effects

        hunger_rate = environment_modifiers.get("hunger_rate", 1.0) * float(effects["hunger"])
        self.hunger += hunger_rate
        self.age += 1
        self.energy_now += 0.5 * float(effects["energy"])
        self.wounded -= 1
        self.health_now += float(effects["health"])

        if self.age > self.longevity:
            self.health_now -= 1
        if self.age > 10000:
            self.health_now -= 100

        if self.hunger > 500:
            self.health_now -= 0.1
        if self.hunger > 1000:
            self.health_now -= 1
        if self.wounded < 0:
            self.wounded = 0
        if self.energy_now < 1:
            self.energy_now = 1
        if self.energy_now > self.energy:
            self.energy_now = self.energy

        if self.health_now > self.health:
            self.health_now = self.health


class Pheromone:
    def __init__(self, x, y, width, height, color, strength):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.strength = strength

    def draw(self, surface):
        r = int(self.color[0] + (255 - self.color[0]) * (255 - self.strength) / 255)
        g = int(self.color[1] + (255 - self.color[1]) * (255 - self.strength) / 255)
        b = int(self.color[2] + (255 - self.color[2]) * (255 - self.strength) / 255)
        color = (r, g, b)
        pygame.draw.rect(surface, color, (self.x, self.y, self.width, self.height))


class Vegetation:
    def __init__(self, x, y, width, height, variant="normal"):
        self.x = x
        self.y = y

        self.width = width
        self.height = height
        self.base_size = self.width * self.height
        self.resource = 100
        self.variant = variant
        self.color = settings.GREEN
        self.regrowth_rate = 0.1

        if variant == "radiant":
            self.color = (150, 230, 255)
            self.resource = 140
            self.regrowth_rate = 0.05
        elif variant == "spore":
            self.color = (180, 120, 255)
            self.resource = 110
            self.regrowth_rate = 0.08
        elif variant == "fortified":
            self.color = (90, 200, 160)
            self.resource = 160
            self.regrowth_rate = 0.06

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, (self.x, self.y, self.width, self.height))

    def set_size(self):
        factor = max(0.1, self.resource / 100)
        self.width = int(self.base_size * factor ** 0.5)
        self.height = int(self.base_size * factor ** 0.5)

    def decrement_resource(self, amount):
        self.resource -= amount
        if self.resource < 0:
            self.resource = 0

    def regrow(self):
        biome_modifier = world.get_regrowth_modifier(self.x + self.width / 2, self.y + self.height / 2)
        growth = self.regrowth_rate * environment_modifiers.get("plant_regrowth", 1.0) * biome_modifier
        self.resource += growth
        max_resource = 200 if self.variant != "normal" else 120
        if self.resource > max_resource:
            self.resource = max_resource

    def apply_effect(self, lifeform):
        if self.variant == "radiant":
            lifeform.health_now = min(lifeform.health, lifeform.health_now + 60)
            lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + 40)
        elif self.variant == "spore":
            lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + 25)
            lifeform.vision = min(settings.VISION_MAX, lifeform.vision + 1)
        elif self.variant == "fortified":
            lifeform.health_now = min(lifeform.health, lifeform.health_now + 35)
            lifeform.defence_power = min(100, lifeform.defence_power + 1)
        else:
            lifeform.health_now = min(lifeform.health, lifeform.health_now + 30)
            lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + 20)


class Graph:
    def __init__(self):
        self.figure, self.axes = plt.subplots()
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")

    def update(self, death_ages_by_dna: Dict[int, List[int]]) -> None:
        self.axes.clear()
        dna_ids = []
        avg_ages = []
        for dna_id, ages in death_ages_by_dna.items():
            dna_ids.append(dna_id)
            avg_ages.append(sum(ages) / len(ages))
        self.axes.bar(dna_ids, avg_ages)
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")
        self.figure.canvas.draw()

    def draw(self, screen):
        plt.draw()
        graph_surface = pygame.surfarray.make_surface(self.figure)
        screen.blit(graph_surface, (0, 0))


world: World
camera: Camera
notification_manager: NotificationManager = notification_context.notification_manager
event_manager: EventManager
player_controller: PlayerController

lifeforms: List[Lifeform] = []
pheromones: List[Pheromone] = []
dna_profiles: List[dict] = []
plants: List[Vegetation] = []

dna_id_counts: Dict[int, int] = {}
dna_home_biome: Dict[int, Optional[BiomeRegion]] = {}

lifeform_id_counter = 0
death_ages: List[int] = []
latest_stats: Optional[Dict[str, float]] = None

environment_modifiers: Dict[str, float] = {"plant_regrowth": 1.0, "hunger_rate": 1.0}

show_debug = False
show_leader = False
show_action = False
show_vision = False
show_dna_id = True
show_dna_info = False

start_time = datetime.datetime.now()
clock = pygame.time.Clock()
fps = settings.FPS


def reset_list_values():
    global lifeforms, dna_profiles, pheromones, plants, death_ages, latest_stats
    lifeforms = []
    dna_profiles = []
    pheromones = []
    plants = []
    death_ages = []
    latest_stats = None
    world.regenerate()
    notification_manager.clear()
    event_manager.reset()
    event_manager.schedule_default_events()
    player_controller.reset()
    environment_modifiers["plant_regrowth"] = 1.0
    environment_modifiers["hunger_rate"] = 1.0
    camera.reset()


def _normalize(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 0.5
    return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))


def determine_home_biome(dna_profile, biomes: List[BiomeRegion]) -> Optional[BiomeRegion]:
    if not biomes:
        return None

    size = (dna_profile['width'] + dna_profile['height']) / 2
    min_size = (settings.MIN_WIDTH + settings.MIN_HEIGHT) / 2
    max_size = (settings.MAX_WIDTH + settings.MAX_HEIGHT) / 2

    size_norm = _normalize(size, min_size, max_size)
    heat_tolerance = _normalize(dna_profile['energy'], 60, 120)
    hydration_dependence = 1.0 - heat_tolerance
    resilience = (
        _normalize(dna_profile['health'], 1, 220)
        + _normalize(dna_profile['defence_power'], 1, 110)
    ) / 2
    mobility = (
        _normalize(dna_profile['vision'], settings.VISION_MIN, settings.VISION_MAX)
        + (1.0 - size_norm)
    ) / 2
    longevity_factor = _normalize(dna_profile['longevity'], 800, 5200)
    aggression = _normalize(dna_profile['attack_power'], 1, 110)

    preferred_biome = None
    preferred_score = -1.0

    for biome in biomes:
        name = biome.name.lower()
        score = 0.0
        if "woestijn" in name:
            score = (
                heat_tolerance * 0.55
                + resilience * 0.25
                + aggression * 0.15
                + mobility * 0.1
                - hydration_dependence * 0.2
            )
        elif "toendra" in name:
            score = (
                (1.0 - heat_tolerance) * 0.35
                + longevity_factor * 0.35
                + resilience * 0.2
                + hydration_dependence * 0.1
            )
        elif "bos" in name:
            score = (
                mobility * 0.35
                + hydration_dependence * 0.2
                + resilience * 0.25
                + (1.0 - size_norm) * 0.1
                + aggression * 0.1
            )
        elif "rivier" in name or "delta" in name or "moeras" in name:
            score = (
                hydration_dependence * 0.45
                + mobility * 0.2
                + resilience * 0.2
                + longevity_factor * 0.15
            )
        elif "steppe" in name:
            score = (
                mobility * 0.3
                + heat_tolerance * 0.25
                + resilience * 0.2
                + aggression * 0.15
                + longevity_factor * 0.1
            )
        else:
            score = (
                resilience * 0.3
                + mobility * 0.25
                + longevity_factor * 0.2
                + (1.0 - abs(heat_tolerance - 0.5)) * 0.25
            )

        if score > preferred_score:
            preferred_biome = biome
            preferred_score = score

    return preferred_biome


def reset_dna_profiles():
    dna_profiles.clear()
    dna_home_biome.clear()
    for dna_id in range(settings.N_DNA_PROFILES):
        dna_profile = {
            'dna_id': dna_id,
            'width': random.randint(settings.MIN_WIDTH, settings.MAX_WIDTH),
            'height': random.randint(settings.MIN_HEIGHT, settings.MAX_HEIGHT),
            'color': (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            'health': random.randint(1, 200),
            'maturity': random.randint(settings.MIN_MATURITY, settings.MAX_MATURITY),
            'vision': random.randint(settings.VISION_MIN, settings.VISION_MAX),
            'defence_power': random.randint(1, 70),
            'attack_power': random.randint(1, 70),
            'energy': random.randint(80, 100),
            'longevity': random.randint(1000, 5000)
        }
        dna_profiles.append(dna_profile)
        if world.biomes:
            dna_home_biome[dna_profile['dna_id']] = determine_home_biome(dna_profile, world.biomes)
        else:
            dna_home_biome[dna_profile['dna_id']] = None


def init_lifeforms():
    spawn_positions_by_dna = {profile['dna_id']: [] for profile in dna_profiles}

    for _ in range(settings.N_LIFEFORMS):
        dna_profile = random.choice(dna_profiles)
        generation = 1

        preferred_biome = dna_home_biome.get(dna_profile['dna_id'])
        other_positions = [
            pos
            for dna_id, positions in spawn_positions_by_dna.items()
            if dna_id != dna_profile['dna_id']
            for pos in positions
        ]

        spawn_attempts = 0
        while True:
            x, y, biome = world.random_position(
                dna_profile['width'],
                dna_profile['height'],
                preferred_biome=preferred_biome,
                avoid_positions=other_positions,
                min_distance=320,
                biome_padding=40,
            )
            center = (x + dna_profile['width'] / 2, y + dna_profile['height'] / 2)
            same_species_positions = spawn_positions_by_dna.setdefault(dna_profile['dna_id'], [])
            too_close_same = any(
                math.hypot(center[0] - px, center[1] - py) < 160 for px, py in same_species_positions
            )
            if not too_close_same or spawn_attempts > 120:
                same_species_positions.append(center)
                break
            spawn_attempts += 1

        lifeform = Lifeform(x, y, dna_profile, generation)
        lifeform.current_biome = biome
        lifeforms.append(lifeform)


def init_vegetation():
    for _ in range(settings.N_VEGETATION):
        width = 20
        height = 20
        biome = random.choice(world.biomes) if world.biomes else None
        spawn_x, spawn_y, _ = world.random_position(width, height, preferred_biome=biome)

        weights = [0.65, 0.15, 0.12, 0.08]
        if biome:
            if "Woestijn" in biome.name:
                weights = [0.5, 0.05, 0.15, 0.3]
            elif "Bos" in biome.name:
                weights = [0.45, 0.25, 0.15, 0.15]
            elif "Rivier" in biome.name:
                weights = [0.35, 0.25, 0.25, 0.15]
            elif "Toendra" in biome.name:
                weights = [0.55, 0.25, 0.1, 0.1]

        variant = random.choices([
            "normal",
            "radiant",
            "spore",
            "fortified"
        ], weights=weights)[0]

        plant = Vegetation(int(spawn_x), int(spawn_y), width, height, variant)
        plants.append(plant)


def count_dna_ids(lifeforms: List[Lifeform]):
    dna_counts: Dict[int, int] = {}
    for lifeform in lifeforms:
        dna_id = lifeform.dna_id
        dna_counts[dna_id] = dna_counts.get(dna_id, 0) + 1
    return dna_counts


def get_attribute_value(lifeforms: List[Lifeform], dna_id: int, attribute: str):
    total_attribute_value = 0
    count = 0
    for lifeform in lifeforms:
        if lifeform.dna_id == dna_id:
            total_attribute_value += getattr(lifeform, attribute)
            count += 1
    if count == 0:
        return None
    return total_attribute_value / count


def collect_population_stats(formatted_time_passed: str):
    stats = {
        "lifeform_count": len(lifeforms),
        "formatted_time": formatted_time_passed,
        "average_health": 0,
        "average_vision": 0,
        "average_gen": 0,
        "average_hunger": 0,
        "average_size": 0,
        "average_age": 0,
        "average_maturity": 0,
        "average_speed": 0,
        "average_cooldown": 0,
        "death_age_avg": sum(death_ages) / len(death_ages) if death_ages else 0,
        "dna_count": count_dna_ids(lifeforms)
    }

    if lifeforms:
        count = len(lifeforms)
        stats["average_health"] = sum(l.health_now for l in lifeforms) / count
        stats["average_vision"] = sum(l.vision for l in lifeforms) / count
        stats["average_gen"] = sum(l.generation for l in lifeforms) / count
        stats["average_hunger"] = sum(l.hunger for l in lifeforms) / count
        stats["average_size"] = sum(l.size for l in lifeforms) / count
        stats["average_age"] = sum(l.age for l in lifeforms) / count
        stats["average_maturity"] = sum(l.maturity for l in lifeforms) / count
        stats["average_speed"] = sum(l.speed for l in lifeforms) / count
        stats["average_cooldown"] = sum(l.reproduced_cooldown for l in lifeforms) / count

    return stats


def draw_stats_panel(surface, font_small, font_large, stats):
    text_lines = [
        f"Number of Lifeforms: {stats['lifeform_count']}",
        f"Total time passed: {stats['formatted_time']}",
        f"Average health: {int(stats['average_health'])}",
        f"Average vision: {int(stats['average_vision'])}",
        f"Average generation: {int(stats['average_gen'])}",
        f"Average hunger: {int(stats['average_hunger'])}",
        f"Average size: {int(stats['average_size'])}",
        f"Average age: {int(stats['average_age'])}",
        f"Average age of dying: {int(stats['death_age_avg'])}",
        f"Average maturity age: {int(stats['average_maturity'])}",
        f"Average speed: {round(stats['average_speed'], 2)}",
        f"Average reproduction cooldown: {round(stats['average_cooldown'])}",
        f"Total of DNA id's: {len(dna_profiles)}",
        "Alive lifeforms: "
    ]

    for idx, line in enumerate(text_lines):
        text_surface = font_small.render(line, True, settings.BLACK)
        surface.blit(text_surface, (50, 20 + idx * 20))

    y_offset = 300
    dna_count_sorted = sorted(stats['dna_count'].items(), key=lambda item: item[1], reverse=True)
    for dna_id, count in dna_count_sorted:
        text = font_large.render(f"Nr. per dna_{dna_id}: {count}", True, settings.BLACK)
        surface.blit(text, (50, y_offset))
        y_offset += 35

        if show_dna_info:
            for attribute in ["health", "vision", "attack_power_now", "defence_power_now", "speed", "maturity", "size", "longevity", "energy"]:
                attribute_value = get_attribute_value(lifeforms, dna_id, attribute)
                if attribute_value is not None:
                    text = font_small.render(f"{attribute}: {round(attribute_value, 2)}", True, settings.BLACK)
                    surface.blit(text, (50, y_offset))
                    y_offset += 20


def run() -> None:
    global world, camera, notification_manager, event_manager, player_controller
    pygame.init()
    screen = pygame.display.set_mode((settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT))
    pygame.display.set_caption("Evolution Sim")

    world_surface = pygame.Surface((settings.WORLD_WIDTH, settings.WORLD_HEIGHT))

    world = World(settings.WORLD_WIDTH, settings.WORLD_HEIGHT)
    camera = Camera(settings.WINDOW_WIDTH, settings.WINDOW_HEIGHT, settings.WORLD_WIDTH, settings.WORLD_HEIGHT)
    camera.center_on(settings.WORLD_WIDTH / 2, settings.WORLD_HEIGHT / 2)

    notification_manager = notification_context.notification_manager
    event_manager = EventManager(notification_manager, environment_modifiers)
    player_controller = PlayerController(notification_manager, dna_profiles, lifeforms)

    reset_dna_profiles()
    init_lifeforms()
    init_vegetation()
    event_manager.schedule_default_events()
    player_controller.reset()
    graph = Graph()

    running = True
    starting_screen = True
    paused = True

    global show_debug, show_leader, show_action, show_vision, show_dna_id, show_dna_info

    while running:
        clock.tick(fps)
        start_button = pygame.Rect(settings.WINDOW_WIDTH - 260, settings.WINDOW_HEIGHT // 2 - 30, 200, 60)
        reset_button = pygame.Rect(30, settings.WINDOW_HEIGHT - 60, 180, 40)
        show_dna_button = pygame.Rect(reset_button.left, reset_button.top - 40, 24, 24)
        show_dna_info_button = pygame.Rect(show_dna_button.right + 10, show_dna_button.top, 24, 24)

        if starting_screen:
            screen.fill(settings.BACKGROUND)
            title_font = pygame.font.Font(None, 48)
            info_font = pygame.font.Font(None, 26)
            button_font = pygame.font.Font(None, 30)

            pygame.draw.rect(screen, settings.GREEN, start_button)
            pygame.draw.rect(screen, settings.BLACK, start_button, 3)

            start_text = button_font.render("Start", True, settings.BLACK)
            text_rect = start_text.get_rect(center=start_button.center)
            screen.blit(start_text, text_rect)

            title_surface = title_font.render("Evolution Sim", True, settings.BLACK)
            screen.blit(title_surface, (50, 40))

            instructions = [
                "Gebruik WASD of de pijltjestoetsen om de camera te bewegen.",
                "Houd Shift ingedrukt om sneller te scrollen.",
                "Druk op M om het genlab te openen of sluiten.",
            ]
            for idx, line in enumerate(instructions):
                info_surface = info_font.render(line, True, settings.BLACK)
                screen.blit(info_surface, (50, 110 + idx * 32))
            notification_manager.update()
            notification_manager.draw(screen, info_font)
        else:
            font1_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus8-Regular.ttf"
            expanded_path1 = os.path.expanduser(font1_path)
            font2_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus-Bold.ttf"
            expanded_path2 = os.path.expanduser(font2_path)

            font = pygame.font.Font(expanded_path1, 12)
            font2 = pygame.font.Font(expanded_path1, 18)
            font3 = pygame.font.Font(expanded_path2, 22)

            keys = pygame.key.get_pressed()
            horizontal = (keys[pygame.K_d] - keys[pygame.K_a])
            vertical = (keys[pygame.K_s] - keys[pygame.K_w])
            if not player_controller.management_mode:
                horizontal += keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
                vertical += keys[pygame.K_DOWN] - keys[pygame.K_UP]
            boost = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            camera.move(horizontal, vertical, boost)

            if not paused:
                world.update(pygame.time.get_ticks())
                world.draw(world_surface)

                current_time = datetime.datetime.now()
                time_passed = current_time - start_time
                formatted_time_passed = datetime.timedelta(seconds=int(time_passed.total_seconds()))
                formatted_time_passed = str(formatted_time_passed).split(".")[0]

                if death_ages:
                    death_age_avg = sum(death_ages) / len(death_ages)

                for plant in plants:
                    plant.set_size()
                    plant.regrow()
                    plant.draw(world_surface)

                for pheromone in list(pheromones):
                    pheromone.strength -= 10
                    if pheromone.strength <= 0:
                        pheromones.remove(pheromone)
                        continue
                    pheromone.draw(world_surface)

                for lifeform in list(lifeforms):
                    lifeform.set_speed()
                    lifeform.calculate_attack_power()
                    lifeform.calculate_defence_power()
                    lifeform.check_group()
                    lifeform.progression()
                    lifeform.movement()
                    lifeform.update_angle()
                    lifeform.grow()
                    lifeform.set_size()
                    lifeform.add_tail()
                    lifeform.draw(world_surface)

                    if show_debug:
                        text = font.render(
                            f"Health: {lifeform.health_now} ID: {lifeform.id} "
                            f"cooldown {lifeform.reproduced_cooldown} "
                            f"gen: {lifeform.generation} "
                            f"dna_id {lifeform.dna_id} "
                            f"hunger: {lifeform.hunger} "
                            f"age: {lifeform.age} ",
                            True,
                            (0, 0, 0),
                        )
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 30)))
                    if show_dna_id:
                        text = font2.render(f"{lifeform.dna_id}", True, (0, 0, 0))
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 10)))
                    if show_leader and lifeform.is_leader:
                        text = font.render("L", True, (0, 0, 0))
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 30)))
                    if show_action:
                        text = font.render(
                            f"Current target, enemy: {lifeform.closest_enemy.id if lifeform.closest_enemy is not None else None}"
                            f", prey: {lifeform.closest_prey.id if lifeform.closest_prey is not None else None}, partner: "
                            f"{lifeform.closest_partner.id if lifeform.closest_partner is not None else None}, is following: "
                            f"{lifeform.closest_follower.id if lifeform.closest_follower is not None else None} ",
                            True,
                            settings.BLACK,
                        )
                        world_surface.blit(text, (int(lifeform.x), int(lifeform.y - 20)))
                    if lifeform.reproduced_cooldown > 0:
                        lifeform.reproduced_cooldown -= 1

                stats = collect_population_stats(formatted_time_passed)
                global latest_stats
                latest_stats = stats
                event_manager.schedule_default_events()
                event_manager.update(pygame.time.get_ticks(), stats, player_controller)
                notification_manager.update()

                screen.blit(world_surface, (0, 0), area=camera.viewport)
                world.draw_weather_overview(screen, font2)
                draw_stats_panel(screen, font2, font3, stats)

                pygame.draw.rect(screen, settings.GREEN, reset_button)
                pygame.draw.rect(screen, settings.BLACK, reset_button, 2)
                pygame.draw.rect(screen, settings.GREEN, show_dna_button)
                pygame.draw.rect(screen, settings.BLACK, show_dna_button, 2)
                pygame.draw.rect(screen, settings.GREEN, show_dna_info_button)
                pygame.draw.rect(screen, settings.BLACK, show_dna_info_button, 2)

                reset_label = font.render("Reset", True, settings.BLACK)
                screen.blit(reset_label, (reset_button.x + 28, reset_button.y + 6))
                dna_label = font.render("DNA", True, settings.BLACK)
                screen.blit(dna_label, (show_dna_button.right + 8, show_dna_button.y + 4))
                dna_info_label = font.render("Info", True, settings.BLACK)
                screen.blit(dna_info_label, (show_dna_info_button.right + 8, show_dna_info_button.y + 4))
                if latest_stats:
                    draw_stats_panel(screen, font2, font3, latest_stats)
                notification_manager.draw(screen, font)
                player_controller.draw_overlay(screen, font2)
                event_manager.draw(screen, font2)

        pygame.display.flip()

        if not paused and not starting_screen and len(lifeforms) > 1:
            pass

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_n:
                    x = random.randint(0, max(0, world.width - 1))
                    y = random.randint(0, max(0, world.height - 1))

                    generation = 1

                    dna_profile = random.choice(dna_profiles)

                    lifeform = Lifeform(x, y, dna_profile, generation)
                    if random.randint(0, 100) < 10:
                        lifeform.is_leader = True
                    lifeforms.append(lifeform)

                elif event.key == pygame.K_b:
                    show_debug = not show_debug
                    notification_context.show_debug = show_debug
                elif event.key == pygame.K_l:
                    show_leader = not show_leader
                elif event.key == pygame.K_s:
                    show_action = not show_action
                    notification_context.show_action = show_action
                elif event.key == pygame.K_v:
                    show_vision = not show_vision
                elif event.key == pygame.K_d:
                    show_dna_id = not show_dna_id
                elif event.key == pygame.K_m:
                    player_controller.toggle_management()
                elif player_controller.management_mode:
                    if event.key == pygame.K_RIGHT:
                        player_controller.cycle_profile(1)
                    elif event.key == pygame.K_LEFT:
                        player_controller.cycle_profile(-1)
                    elif event.key == pygame.K_UP:
                        player_controller.adjust_attribute(1)
                    elif event.key == pygame.K_DOWN:
                        player_controller.adjust_attribute(-1)
                    elif event.key == pygame.K_TAB:
                        direction = -1 if (event.mod & pygame.KMOD_SHIFT) else 1
                        player_controller.cycle_attribute(direction)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if start_button.collidepoint(event.pos):
                    notification_manager.add("Simulatie gestart", settings.GREEN)
                    starting_screen = False
                    paused = False
                    camera.reset()
                    notification_manager.add("Gebruik WASD of pijltjes om de camera te bewegen (Shift = snel)", settings.BLUE)
                if reset_button.collidepoint(event.pos):
                    reset_list_values()
                    reset_dna_profiles()
                    init_lifeforms()
                    init_vegetation()
                    notification_manager.add("Simulatie gereset", settings.BLUE)
                    starting_screen = True
                    paused = True
                if show_dna_button.collidepoint(event.pos):
                    notification_manager.add("DNA-ID overlay gewisseld", settings.SEA)
                    show_dna_id = not show_dna_id
                if show_dna_info_button.collidepoint(event.pos):
                    show_dna_info = not show_dna_info

    pygame.quit()

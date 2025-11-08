import datetime
import math
import os
import random
import itertools
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import matplotlib.pyplot as plt
import pygame

pygame.init()
screen = pygame.display.set_mode((1900, 1000))
# screen = pygame.Surface((1400, 750), pygame.SRCALPHA)
pygame.display.set_caption("Evolution Sim")



# Colors
white = [255, 255, 255]
black = (0, 0, 0)
green = (124, 252, 184)
red = (255, 150, 150)
blue = (150, 255, 150)
sea = (194, 252, 250)


@dataclass
class WeatherPattern:
    name: str
    temperature: int
    precipitation: str
    movement_modifier: float = 1.0
    hunger_modifier: float = 1.0
    regrowth_modifier: float = 1.0
    energy_modifier: float = 1.0
    health_tick: float = 0.0
    duration_range: Tuple[int, int] = (15000, 30000)

    def random_duration(self) -> int:
        return random.randint(*self.duration_range)


@dataclass
class Barrier:
    rect: pygame.Rect
    color: Tuple[int, int, int] = (90, 90, 90)
    label: str = ""


@dataclass
class WaterBody:
    kind: str
    segments: List[pygame.Rect]
    color: Tuple[int, int, int] = (70, 140, 220)

    def collides(self, rect: pygame.Rect) -> bool:
        return any(segment.colliderect(rect) for segment in self.segments)


@dataclass
class BiomeRegion:
    name: str
    rect: pygame.Rect
    color: Tuple[int, int, int]
    weather_patterns: List[WeatherPattern]
    movement_modifier: float = 1.0
    hunger_modifier: float = 1.0
    regrowth_modifier: float = 1.0
    energy_modifier: float = 1.0
    health_modifier: float = 0.0
    active_weather: Optional[WeatherPattern] = None
    weather_expires_at: int = 0

    def update_weather(self, now_ms: int) -> None:
        if self.active_weather is None or now_ms >= self.weather_expires_at:
            self.active_weather = random.choice(self.weather_patterns)
            self.weather_expires_at = now_ms + self.active_weather.random_duration()

    def get_effects(self) -> dict:
        weather = self.active_weather
        if weather is None:
            weather = WeatherPattern(
                name="Stabiel",
                temperature=20,
                precipitation="helder"
            )
        return {
            "movement": self.movement_modifier * weather.movement_modifier,
            "hunger": self.hunger_modifier * weather.hunger_modifier,
            "regrowth": self.regrowth_modifier * weather.regrowth_modifier,
            "energy": self.energy_modifier * weather.energy_modifier,
            "health": self.health_modifier + weather.health_tick,
            "temperature": weather.temperature,
            "precipitation": weather.precipitation,
            "weather_name": weather.name,
        }


class World:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.background_color = (228, 222, 208)
        self.barriers: List[Barrier] = []
        self.water_bodies: List[WaterBody] = []
        self.biomes: List[BiomeRegion] = []
        self._generate()

    def _generate(self) -> None:
        self.barriers.clear()
        self.water_bodies.clear()
        self.biomes.clear()
        self._create_border_barriers()
        self._create_interior_barriers()
        self._create_water_bodies()
        self._create_biomes()

    def regenerate(self) -> None:
        self._generate()

    def _create_border_barriers(self) -> None:
        border_thickness = 12
        self.barriers.extend([
            Barrier(pygame.Rect(0, 0, self.width, border_thickness)),
            Barrier(pygame.Rect(0, 0, border_thickness, self.height)),
            Barrier(pygame.Rect(0, self.height - border_thickness, self.width, border_thickness)),
            Barrier(pygame.Rect(self.width - border_thickness, 0, border_thickness, self.height)),
        ])

    def _create_interior_barriers(self) -> None:
        ridge_rect = pygame.Rect(self.width // 3, 140, 40, self.height - 280)
        canyon_rect = pygame.Rect(2 * self.width // 3, self.height // 2, 30, self.height // 2 - 60)
        self.barriers.extend([
            Barrier(ridge_rect, (120, 110, 95), "rotsrug"),
            Barrier(canyon_rect, (110, 100, 85), "canyon"),
        ])

    def _create_water_bodies(self) -> None:
        sea_rect = pygame.Rect(40, self.height - 220, self.width // 2, 220)
        sea = WaterBody("sea", [sea_rect], color=(64, 140, 200))

        river_segments: List[pygame.Rect] = []
        segment_width = 32
        x = self.width - 220
        y = 0
        while y < self.height:
            segment = pygame.Rect(x, y, segment_width, 140)
            river_segments.append(segment)
            x += random.randint(-80, 60)
            x = max(self.width // 3, min(self.width - segment_width - 40, x))
            y += 120
        river = WaterBody("river", river_segments, color=(60, 150, 210))

        delta_segments: List[pygame.Rect] = []
        for idx, segment in enumerate(river_segments[-3:]):
            offset = idx * 50
            delta_segments.append(pygame.Rect(segment.x - offset, segment.bottom - 60, segment_width + 100, 80))
        delta = WaterBody("delta", delta_segments, color=(70, 170, 220))

        self.water_bodies.extend([sea, river, delta])

    def _create_biomes(self) -> None:
        temperate_patterns = [
            WeatherPattern("Zonnig", 23, "helder", movement_modifier=1.05, hunger_modifier=0.9, regrowth_modifier=1.15, energy_modifier=1.1),
            WeatherPattern("Lichte regen", 18, "regen", movement_modifier=0.95, hunger_modifier=1.0, regrowth_modifier=1.35, energy_modifier=0.95),
            WeatherPattern("Mist", 15, "mist", movement_modifier=0.85, hunger_modifier=1.05, regrowth_modifier=1.2, energy_modifier=0.9, duration_range=(12000, 20000)),
        ]
        forest_patterns = [
            WeatherPattern("Dichte mist", 14, "mist", movement_modifier=0.8, hunger_modifier=1.1, regrowth_modifier=1.4, energy_modifier=0.9),
            WeatherPattern("Regenstorm", 16, "storm", movement_modifier=0.7, hunger_modifier=1.15, regrowth_modifier=1.55, energy_modifier=0.85, health_tick=-0.2, duration_range=(10000, 18000)),
            WeatherPattern("Zwoel", 22, "bewolkt", movement_modifier=0.9, hunger_modifier=1.05, regrowth_modifier=1.2, energy_modifier=1.0),
        ]
        desert_patterns = [
            WeatherPattern("Hitteslag", 36, "droog", movement_modifier=0.7, hunger_modifier=1.35, regrowth_modifier=0.6, energy_modifier=0.7, health_tick=-0.3, duration_range=(12000, 20000)),
            WeatherPattern("Koele nacht", 20, "helder", movement_modifier=1.05, hunger_modifier=0.95, regrowth_modifier=0.8, energy_modifier=1.1),
            WeatherPattern("Zandstorm", 32, "storm", movement_modifier=0.55, hunger_modifier=1.45, regrowth_modifier=0.5, energy_modifier=0.6, health_tick=-0.4, duration_range=(8000, 15000)),
        ]
        tundra_patterns = [
            WeatherPattern("Sneeuw", -4, "sneeuw", movement_modifier=0.65, hunger_modifier=1.25, regrowth_modifier=0.7, energy_modifier=0.8, health_tick=-0.2),
            WeatherPattern("Heldere kou", -10, "helder", movement_modifier=0.75, hunger_modifier=1.1, regrowth_modifier=0.5, energy_modifier=0.85),
            WeatherPattern("Dooi", 2, "regen", movement_modifier=0.85, hunger_modifier=1.0, regrowth_modifier=0.9, energy_modifier=0.9),
        ]
        marsh_patterns = [
            WeatherPattern("Damp", 19, "mist", movement_modifier=0.8, hunger_modifier=1.05, regrowth_modifier=1.5, energy_modifier=0.95),
            WeatherPattern("Zware regen", 17, "regen", movement_modifier=0.75, hunger_modifier=1.0, regrowth_modifier=1.6, energy_modifier=0.9, health_tick=0.1),
            WeatherPattern("Helder", 21, "helder", movement_modifier=0.95, hunger_modifier=0.95, regrowth_modifier=1.2, energy_modifier=1.05),
        ]

        self.biomes = [
            BiomeRegion(
                "Rivierdelta",
                pygame.Rect(self.width // 3 - 80, self.height // 2 - 160, self.width // 2 + 40, 320),
                (120, 200, 150),
                marsh_patterns,
                movement_modifier=0.85,
                hunger_modifier=0.95,
                regrowth_modifier=1.4,
                energy_modifier=0.95,
                health_modifier=0.05,
            ),
            BiomeRegion(
                "Bosrand",
                pygame.Rect(60, 60, self.width // 3 - 20, self.height // 2),
                (80, 170, 120),
                forest_patterns,
                movement_modifier=0.8,
                hunger_modifier=0.9,
                regrowth_modifier=1.5,
                energy_modifier=1.0,
                health_modifier=0.02,
            ),
            BiomeRegion(
                "Steppe",
                pygame.Rect(self.width // 3 + 20, 100, self.width // 3 + 160, self.height // 2 - 40),
                (180, 200, 120),
                temperate_patterns,
                movement_modifier=1.05,
                hunger_modifier=0.95,
                regrowth_modifier=1.0,
                energy_modifier=1.1,
            ),
            BiomeRegion(
                "Woestijnrand",
                pygame.Rect(self.width // 2 + 120, self.height - 320, self.width // 2 - 160, 240),
                (210, 190, 120),
                desert_patterns,
                movement_modifier=0.75,
                hunger_modifier=1.3,
                regrowth_modifier=0.6,
                energy_modifier=0.8,
                health_modifier=-0.1,
            ),
            BiomeRegion(
                "Toendra",
                pygame.Rect(self.width - 420, 40, 360, 260),
                (180, 210, 220),
                tundra_patterns,
                movement_modifier=0.7,
                hunger_modifier=1.2,
                regrowth_modifier=0.65,
                energy_modifier=0.85,
                health_modifier=-0.05,
            ),
        ]

    def update(self, now_ms: int) -> None:
        for biome in self.biomes:
            biome.update_weather(now_ms)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(self.background_color)
        for biome in self.biomes:
            overlay = pygame.Surface((biome.rect.width, biome.rect.height), pygame.SRCALPHA)
            overlay.fill((*biome.color, 80))
            surface.blit(overlay, biome.rect.topleft)

        for water in self.water_bodies:
            for segment in water.segments:
                pygame.draw.rect(surface, water.color, segment)

        for barrier in self.barriers:
            pygame.draw.rect(surface, barrier.color, barrier.rect)

    def draw_weather_overview(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        panel_width = 320
        panel_height = 26 + 20 * len(self.biomes)
        panel = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
        panel.fill((255, 255, 255, 170))
        surface.blit(panel, (surface.get_width() // 2 - panel_width // 2, 12))

        title = font.render("Weer per biome", True, black)
        surface.blit(title, (surface.get_width() // 2 - title.get_width() // 2, 20))

        y_offset = 46
        for biome in self.biomes:
            effects = biome.get_effects()
            text = font.render(
                f"{biome.name}: {effects['weather_name']} ({effects['temperature']}°C, {effects['precipitation']})",
                True,
                black,
            )
            surface.blit(text, (surface.get_width() // 2 - panel_width // 2 + 10, y_offset))
            y_offset += 20

    def get_biome_at(self, x: float, y: float) -> Optional[BiomeRegion]:
        point = (int(x), int(y))
        for biome in self.biomes:
            if biome.rect.collidepoint(point):
                return biome
        if self.biomes:
            return self.biomes[0]
        return None

    def get_environment_context(self, x: float, y: float) -> Tuple[Optional[BiomeRegion], dict]:
        biome = self.get_biome_at(x, y)
        effects = biome.get_effects() if biome else {
            "movement": 1.0,
            "hunger": 1.0,
            "regrowth": 1.0,
            "energy": 1.0,
            "health": 0.0,
            "temperature": 20,
            "precipitation": "helder",
            "weather_name": "Stabiel",
        }
        return biome, effects

    def get_regrowth_modifier(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return effects["regrowth"]

    def get_hunger_modifier(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return effects["hunger"]

    def get_energy_modifier(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return effects["energy"]

    def get_health_tick(self, x: float, y: float) -> float:
        _, effects = self.get_environment_context(x, y)
        return effects["health"]

    def is_blocked(self, rect: pygame.Rect, include_water: bool = True) -> bool:
        for barrier in self.barriers:
            if rect.colliderect(barrier.rect):
                return True
        if include_water:
            for water in self.water_bodies:
                if water.collides(rect):
                    return True
        return False

    def resolve_entity_movement(
        self,
        entity_rect: pygame.Rect,
        previous_pos: Tuple[float, float],
        attempted_pos: Tuple[float, float],
    ) -> Tuple[float, float, bool, bool, bool]:
        attempt_x, attempt_y = attempted_pos
        max_x = self.width - entity_rect.width
        max_y = self.height - entity_rect.height
        clamped_x = max(0.0, min(max_x, attempt_x))
        clamped_y = max(0.0, min(max_y, attempt_y))
        hit_boundary_x = not math.isclose(clamped_x, attempt_x, abs_tol=1e-3)
        hit_boundary_y = not math.isclose(clamped_y, attempt_y, abs_tol=1e-3)

        entity_rect.update(int(clamped_x), int(clamped_y), entity_rect.width, entity_rect.height)

        collided = False
        if self.is_blocked(entity_rect):
            collided = True
            clamped_x, clamped_y = previous_pos
            entity_rect.update(int(clamped_x), int(clamped_y), entity_rect.width, entity_rect.height)

        return clamped_x, clamped_y, hit_boundary_x, hit_boundary_y, collided

    def random_position(
        self,
        width: int,
        height: int,
        preferred_biome: Optional[BiomeRegion] = None,
        avoid_water: bool = True,
    ) -> Tuple[float, float, Optional[BiomeRegion]]:
        attempts = 0
        x = random.randint(0, max(1, self.width - width))
        y = random.randint(0, max(1, self.height - height))
        while attempts < 160:
            biome = preferred_biome or random.choice(self.biomes)
            spawn_rect = biome.rect if biome else pygame.Rect(0, 0, self.width, self.height)
            x = random.randint(spawn_rect.left, max(spawn_rect.left, spawn_rect.right - width))
            y = random.randint(spawn_rect.top, max(spawn_rect.top, spawn_rect.bottom - height))
            candidate = pygame.Rect(x, y, width, height)
            if candidate.right > self.width or candidate.bottom > self.height:
                attempts += 1
                continue
            if self.is_blocked(candidate, include_water=avoid_water):
                attempts += 1
                continue
            return float(x), float(y), self.get_biome_at(candidate.centerx, candidate.centery)
        return float(x), float(y), self.get_biome_at(x, y)


world = World(screen.get_width(), screen.get_height())


@dataclass
class Notification:
    message: str
    color: tuple
    frames_left: int


class NotificationManager:
    def __init__(self):
        self.notifications = []

    def add(self, message, color=black, duration=None):
        if duration is None:
            duration = fps * 3 if 'fps' in globals() else 180
        self.notifications.append(Notification(message, color, duration))

    def clear(self):
        self.notifications.clear()

    def update(self):
        for notification in list(self.notifications):
            notification.frames_left -= 1
            if notification.frames_left <= 0:
                self.notifications.remove(notification)

    def draw(self, surface, font):
        y_offset = 20
        for notification in self.notifications[-6:]:
            text_surface = font.render(notification.message, True, notification.color)
            surface.blit(text_surface, (surface.get_width() - text_surface.get_width() - 40, y_offset))
            y_offset += 20


@dataclass
class Event:
    name: str
    description: str
    duration_ms: int
    objective: dict
    reward: dict
    environment_effects: dict = field(default_factory=dict)
    start_time: int = None
    completed: bool = False
    failed: bool = False
    applied_effects: dict = field(default_factory=dict)

    def time_left(self, current_time):
        if self.start_time is None:
            return self.duration_ms
        remaining = self.duration_ms - (current_time - self.start_time)
        return max(0, remaining)


class EventManager:
    def __init__(self):
        self.events = []
        self.active_event = None

    def schedule_default_events(self):
        if self.events:
            return
        famine = Event(
            name="Drought Alert",
            description="Houd de gemiddelde honger onder 350 terwijl de vegetatie traag groeit.",
            duration_ms=90_000,
            objective={"metric": "average_hunger", "type": "below", "value": 350},
            reward={"dna_points": 45},
            environment_effects={"plant_regrowth": 0.6}
        )
        defence = Event(
            name="Groeispurt",
            description="Vergroot de populatie tot 120 levensvormen.",
            duration_ms=120_000,
            objective={"metric": "lifeform_count", "type": "above", "value": 120},
            reward={"dna_points": 60},
            environment_effects={"hunger_rate": 1.2}
        )
        harmony = Event(
            name="Veiligheidsprotocol",
            description="Bereik een gemiddelde gezondheid van minstens 140.",
            duration_ms=75_000,
            objective={"metric": "average_health", "type": "above", "value": 140},
            reward={"dna_points": 35}
        )
        self.events = [famine, defence, harmony]

    def start_next_event(self, current_time):
        if self.active_event or not self.events:
            return
        self.active_event = self.events.pop(0)
        self.active_event.start_time = current_time
        self._apply_environment_effects(self.active_event)
        notification_manager.add(f"Nieuwe missie: {self.active_event.name}", blue)
        notification_manager.add(self.active_event.description, blue)

    def _apply_environment_effects(self, event):
        for key, value in event.environment_effects.items():
            environment_modifiers[key] = environment_modifiers.get(key, 1.0) * value
        event.applied_effects = event.environment_effects.copy()

    def _revert_environment_effects(self, event):
        for key, value in event.applied_effects.items():
            environment_modifiers[key] = environment_modifiers.get(key, 1.0) / value if value else environment_modifiers.get(key, 1.0)
        event.applied_effects.clear()

    def update(self, current_time, stats, player_controller):
        if not self.active_event:
            self.start_next_event(current_time)
            return

        event = self.active_event
        if event.completed or event.failed:
            self._revert_environment_effects(event)
            self.active_event = None
            self.start_next_event(current_time)
            return

        metric_value = stats.get(event.objective.get("metric"))
        target = event.objective.get("value")
        comparison_type = event.objective.get("type")

        if metric_value is not None:
            if comparison_type == "below" and metric_value <= target:
                self.complete_event(player_controller)
                return
            if comparison_type == "above" and metric_value >= target:
                self.complete_event(player_controller)
                return

        if current_time - event.start_time >= event.duration_ms:
            self.fail_event()

    def complete_event(self, player_controller):
        if not self.active_event or self.active_event.completed:
            return
        self.active_event.completed = True
        notification_manager.add(f"Missie voltooid: {self.active_event.name}", green)
        player_controller.apply_reward(self.active_event.reward)

    def fail_event(self):
        if not self.active_event or self.active_event.failed:
            return
        self.active_event.failed = True
        notification_manager.add(f"Missie mislukt: {self.active_event.name}", red)

    def draw(self, surface, font):
        if not self.active_event:
            return
        event = self.active_event
        current_time = pygame.time.get_ticks()
        remaining_seconds = int(event.time_left(current_time) / 1000)
        lines = [event.name, event.description, f"Doel: {event.objective['metric']} {event.objective['type']} {event.objective['value']}", f"Tijd resterend: {remaining_seconds}s"]
        x = surface.get_width() - 420
        y = surface.get_height() - 140
        for line in lines:
            text_surface = font.render(line, True, black)
            surface.blit(text_surface, (x, y))
            y += 20

    def reset(self):
        if self.active_event:
            self._revert_environment_effects(self.active_event)
        self.active_event = None
        self.events = []


class PlayerController:
    def __init__(self):
        self.resources = {"dna_points": 120}
        self.management_mode = False
        self.selected_profile = 0
        self.attributes = ["health", "vision", "attack_power", "defence_power", "energy", "longevity"]
        self.selected_attribute_index = 0

    def reset(self):
        self.resources = {"dna_points": 120}
        self.management_mode = False
        self.selected_profile = 0
        self.selected_attribute_index = 0

    def toggle_management(self):
        self.management_mode = not self.management_mode
        state = "geopend" if self.management_mode else "gesloten"
        notification_manager.add(f"Genlab {state}.")

    def cycle_profile(self, dna_profiles, direction):
        if not dna_profiles:
            return
        self.selected_profile = (self.selected_profile + direction) % len(dna_profiles)

    def cycle_attribute(self, direction):
        self.selected_attribute_index = (self.selected_attribute_index + direction) % len(self.attributes)

    def adjust_attribute(self, dna_profiles, direction):
        if not dna_profiles:
            return
        profile = dna_profiles[self.selected_profile]
        attribute = self.attributes[self.selected_attribute_index]
        cost = 6
        modifier = 3 * direction
        if direction > 0:
            if self.resources["dna_points"] < cost:
                notification_manager.add("Onvoldoende DNA-punten.", red)
                return
            profile[attribute] += modifier
            self.resources["dna_points"] -= cost
            notification_manager.add(f"DNA {profile['dna_id']}: +{modifier} {attribute}.", green)
        else:
            new_value = max(1, profile[attribute] + modifier)
            profile[attribute] = new_value
            self.resources["dna_points"] += cost // 2
            notification_manager.add(f"DNA {profile['dna_id']}: -{abs(modifier)} {attribute} voor punten.", blue)

        for lifeform in lifeforms:
            if lifeform.dna_id == profile['dna_id']:
                setattr(lifeform, attribute, profile[attribute])
                if attribute == "health":
                    lifeform.health_now = min(lifeform.health, lifeform.health_now)
                if attribute == "energy":
                    lifeform.energy_now = min(lifeform.energy, lifeform.energy_now)

    def apply_reward(self, reward):
        points = reward.get("dna_points", 0)
        if points:
            self.resources["dna_points"] += points
            notification_manager.add(f"Beloning: {points} DNA-punten ontvangen!", green)

    def on_birth(self):
        self.resources["dna_points"] += 1

    def draw_overlay(self, surface, font):
        panel_x = surface.get_width() - 220
        panel_y = 20
        pygame.draw.rect(surface, (240, 240, 240), (panel_x - 10, panel_y - 10, 200, 120), border_radius=6)
        pygame.draw.rect(surface, black, (panel_x - 10, panel_y - 10, 200, 120), 2, border_radius=6)
        dna_text = font.render(f"DNA-punten: {self.resources['dna_points']}", True, black)
        surface.blit(dna_text, (panel_x, panel_y))
        if self.management_mode and dna_profiles:
            profile = dna_profiles[self.selected_profile]
            attribute = self.attributes[self.selected_attribute_index]
            lines = [
                f"Genlab actief",
                f"Profiel: {profile['dna_id']}",
                f"Attribuut: {attribute}",
                f"Waarde: {profile[attribute]}"
            ]
            y_offset = panel_y + 20
            for line in lines:
                text_surface = font.render(line, True, black)
                surface.blit(text_surface, (panel_x, y_offset))
                y_offset += 20


environment_modifiers = {"plant_regrowth": 1.0, "hunger_rate": 1.0}

notification_manager = NotificationManager()
event_manager = EventManager()
player_controller = PlayerController()


def debug_log(message):
    duration = fps if 'fps' in globals() else 180
    if 'show_debug' in globals() and show_debug:
        notification_manager.add(message, blue, duration=duration)


def action_log(message):
    duration = fps * 2 if 'fps' in globals() else 360
    if 'show_action' in globals() and show_action:
        notification_manager.add(message, sea, duration=duration)

# Variabele range instellen
n_lifeforms = 100  # number of life forms
n_vegetation = 100  # number of vegetation
n_dna_profiles = 10  # number of dna profiles
max_lifeforms = 150  # max number of life forms
mutation_chance = 5  # ?% chance of mutation
reproducing_cooldown_value = 80

dna_change_threshold = 0.1  # Change the DNA ID if the DNA has changed more than 50% from the original initialization
color_change_threshold = 0.1

group_min_neighbors = 3
group_max_radius = 120
group_cohesion_threshold = 0.35
group_persistence_frames = 45
group_maturity_ratio = 0.6

max_width = 20
min_width = 8

max_height = 20
min_height = 8

min_maturity = 100
max_maturity = 500

vision_min = 10
vision_max = 80

degrade_tipping = 3000

lifeform_id_counter = 0

background = white

# Lege lijst voor levensvorm-objecten
lifeforms = []
pheromones = []
dna_profiles = []
plants = []

dna_id_counts = {}
dna_home_biome = {}


death_ages = []
death_age_avg = 0

total_health = 0
total_vision = 0
total_gen = 0
total_hunger = 0
total_size = 0
total_age = 0
total_maturity = 0
total_speed = 0
total_cooldown = 0

total_spawned_lifeforms = 0

start_time = datetime.datetime.now()
total_time = 0

# Set the frame rate to ? FPS
fps = 30

# Create a clock object
clock = pygame.time.Clock()


starting_screen = True
paused = True
show_debug = False
show_leader = False
show_action = False
show_vision = False
show_dna_id = True
show_dna_info = False

########################################################################################################################

# Klasse voor levensvorm-objecten




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
        self.reproduced_cooldown = reproducing_cooldown_value

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

        if self.closest_enemy:
            debug_log(f"{self.id} ziet vijand {self.closest_enemy.id}")
        if self.closest_prey:
            debug_log(f"{self.id} heeft prooi {self.closest_prey.id}")
        if self.closest_partner:
            debug_log(f"{self.id} heeft partner {self.closest_partner.id}")

        # Check if the object has reached the edges of the screen
        # Iterate over all lifeform objects in the lifeforms list
        for lifeform in lifeforms:
            if self.distance_to(lifeform) < self.vision and lifeform != self:
                # Update closest enemy if necessary
                if self.size < lifeform.size and self.dna_id != lifeform.dna_id and (
                    self.closest_enemy is None or self.distance_to(lifeform) < self.distance_to(self.closest_enemy)):
                        self.closest_enemy = lifeform
                        debug_log(f"{self.id} markeert {self.closest_enemy.id} als vijand")
                        self.search = False

                # Update closest prey if necessary
                elif self.size >= lifeform.size and self.dna_id != lifeform.dna_id and (
                        self.closest_prey is None or self.distance_to(lifeform) < self.distance_to(self.closest_prey)):
                    self.closest_prey = lifeform
                    debug_log(f"{self.id} markeert {self.closest_prey.id} als prooi")
                    self.search = False

                # Update closest partner if necessary
                elif lifeform.maturity < lifeform.age and \
                    self.maturity < self.age and \
                    lifeform.dna_id == self.dna_id and \
                    lifeform.health_now > 50 and \
                    (self.closest_partner is None or self.distance_to(lifeform) < self.distance_to(self.closest_partner)):
                    self.closest_partner = lifeform
                    debug_log(f"{self.id} vindt partner {self.closest_partner.id}")
                    self.search = False

                #update closest follower if necessary
                elif lifeform.dna_id == self.dna_id and lifeform.is_leader or lifeform.closest_follower:
                    self.closest_follower = lifeform

        for plant in plants:
            if self.distance_to(plant) < self.vision and self.hunger > 250:
                self.closest_plant = plant

        # Perform check if closest life forms are still within vision, otherwise reset them to none
        if self.closest_enemy and self.closest_enemy.health_now <= 1 or self.closest_enemy and self.distance_to(self.closest_enemy) > self.vision:
            debug_log(f"{self.id} verliest vijand uit zicht")
            self.closest_enemy = None
        if self.closest_prey and self.closest_prey.health_now <= 1 or self.closest_prey and self.distance_to(self.closest_prey) > self.vision:
            debug_log(f"{self.id} verliest prooi uit zicht")
            self.closest_prey = None
        if self.closest_partner and self.closest_partner.health_now <= 1 or self.closest_partner and self.distance_to(self.closest_partner) > self.vision:
            debug_log(f"{self.id} verliest partner uit zicht")
            self.closest_partner = None
        if self.closest_follower and self.closest_follower.health_now <= 20 or self.closest_follower and self.distance_to(self.closest_follower) > self.vision:
            debug_log(f"{self.id} verliest volger uit zicht")
            self.closest_follower = None
        if self.closest_plant and self.closest_plant.resource <= 1 or self.closest_plant and self.distance_to(self.closest_plant) > self.vision:
            debug_log(f"{self.id} verliest plant uit zicht")
            self.closest_plant = None



        # If an enemy object was found, move away from it
        if self.closest_enemy and not self.in_group:
            debug_log(f"{self.id} vlucht voor vijand")
            x_diff = self.closest_enemy.x - self.x
            y_diff = self.closest_enemy.y - self.y
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = -x_diff / total_distance
                self.y_direction = -y_diff / total_distance
                #
                # total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                # target_angle = math.atan2(y_diff, x_diff)
                #
                # angle_diff = target_angle - self.angle
                # angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                #
                # if abs(angle_diff) > self.angular_velocity:
                #     angle_diff = math.copysign(self.angular_velocity, angle_diff)
                #
                # self.angle += angle_diff
                # self.x_direction = -math.cos(self.angle)
                # self.y_direction = -math.sin(self.angle)

        if self.closest_enemy and self.distance_to(self.closest_enemy) < 3:
            if self.in_group and self.hunger > 250:
                attack = self.attack_power_now
                self.health_now += attack
                self.closest_enemy.health_now -= self.defence_power_now
                self.energy_now -= 2
                self.hunger -= 25
                action_log(f"{self.id} verdedigt zich succesvol")
            else:
                attack = self.closest_enemy.attack_power_now - (0.2 * self.defence_power_now)
                self.energy_now -= 10
                self.health_now -= attack
                self.wounded += 25
                action_log(f"{self.id} raakt gewond")

        if self.closest_enemy and self.in_group:
            debug_log(f"{self.id} valt vijand aan met groep")
            x_diff = self.closest_enemy.x - self.x
            y_diff = self.closest_enemy.y - self.y
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance
        else:
            if random.randint(0, 100) < 5:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)


        # If a prey object was found, move towards it
        if self.closest_prey and not self.closest_enemy and not self.closest_partner and self.hunger > 500 and self.age > self.maturity:
            debug_log(f"{self.id} jaagt op {self.closest_prey.id}")
            x_diff = self.closest_prey.x - self.x
            y_diff = self.closest_prey.y - self.y
            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance
        if self.closest_prey and not self.closest_enemy and self.distance_to(self.closest_prey) < 3 and self.hunger > 500:
            if not self.closest_prey.in_group:
                action_log(f"{self.id} eet {self.closest_prey.id}")
                self.health_now += self.attack_power_now
                self.closest_prey.health_now -= self.attack_power_now
                self.hunger -= 50
                self.energy_now += 25
            else:
                self.closest_prey.health_now -= self.defence_power_now
                self.energy_now -= 1000 / self.closest_prey.attack_power_now
                self.health_now -= 1000 / self.defence_power_now

        # If a partner object was found, move towards it and reproduce if close enough
        if self.reproduced_cooldown == 0 and not self.closest_enemy and self.closest_partner and self.hunger < 500 and self.age > self.maturity:
            debug_log(f"{self.id} zoekt partner {self.closest_partner.id}")
            x_diff = self.closest_partner.x - self.x
            y_diff = self.closest_partner.y - self.y
            if len(lifeforms) < max_lifeforms and self.distance_to(self.closest_partner) < 3:
                self.reproduce(self.closest_partner)
                self.reproduced += 1
                self.reproduced_cooldown = reproducing_cooldown_value
                self.energy_now -= 50
                self.health_now -= 50
                self.hunger += 50
                action_log(f"{self.id} plant zich voort")

            if x_diff == 0 and y_diff == 0:
                self.x_direction = 0
                self.y_direction = 0
            else:
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                self.x_direction = x_diff / total_distance
                self.y_direction = y_diff / total_distance

        # If a plant object was found, move towards it and eat if close enough
        if self.closest_plant and self.hunger > 250 and not self.closest_enemy and not self.closest_partner and self.closest_plant.resource > 10:
            x_diff = self.closest_plant.x - self.x
            y_diff = self.closest_plant.y - self.y
            if self.distance_to(self.closest_plant) < 3:
                action_log(f"{self.id} eet van een plant")
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

        # If there is no target nearby, start searching
        if not self.search and not self.closest_enemy and not self.closest_prey and not self.closest_partner and not self.closest_plant:
            debug_log(f"{self.id} zoekt naar doelen")
            self.x_direction = random.uniform(-1, 1)
            self.y_direction = random.uniform(-1, 1)
            self.search = True

        if self.search:
            if self.closest_follower and not self.is_leader and self.closest_follower.closest_follower != self and self.hunger < 500:
                x_diff = self.closest_follower.x - self.x
                y_diff = self.closest_follower.y - self.y
                total_distance = math.sqrt(x_diff ** 2 + y_diff ** 2)
                if total_distance > 0:
                    if total_distance > self.follow_range:  # Check if the distance is outside of the follow range
                        self.x_direction = x_diff / total_distance
                        self.y_direction = y_diff / total_distance
                    else:  # If the distance is within the follow range, adjust the direction to move away from the leader
                        self.x_direction = -x_diff / total_distance
                        self.y_direction = -y_diff / total_distance
                else:
                    self.x_direction = random.uniform(-1, 1)
                    self.y_direction = random.uniform(-1, 1)



            elif random.randint(0, 100) < 25:
                self.x_direction = random.uniform(-1, 1)
                self.y_direction = random.uniform(-1, 1)
                # self.x_direction = (self.x_direction + random.uniform(-0.1, 0.1))
                # self.y_direction = (self.y_direction + random.uniform(-0.1, 0.1))

            debug_log(f"{self.id} zoekstatus: {self.search}")

    def add_tail(self):
        # add a pheromone trail
        pheromone = Pheromone(self.x, self.y, self.width, self.height, self.color, 100)
        pheromones.append(pheromone)


    def distance_to(self, other):
        # Calculate the distance between two Lifeform objects
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx ** 2 + dy ** 2)


    def set_size(self):
        self.size = self.width * self.height
        if self.width < 1:
            self.width = 1
        if self.height < 1:
            self.height = 1

    def check_group(self):
        relevant_radius = min(self.vision, group_max_radius)
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
            if lifeform.age < lifeform.maturity * group_maturity_ratio:
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
        if neighbor_count >= group_min_neighbors:
            avg_distance = total_distance / neighbor_count if neighbor_count else 0
            radius = max(relevant_radius, 1)
            cohesion = max(0.0, min(1.0, 1 - (avg_distance / radius)))
            self.group_strength = cohesion * (neighbor_count / group_min_neighbors)
            self.group_center = (
                total_x / (neighbor_count + 1),
                total_y / (neighbor_count + 1)
            )
            if cohesion >= group_cohesion_threshold:
                qualified = True
        else:
            self.group_strength = 0
            self.group_center = None

        if qualified:
            self.in_group = True
            self.group_state_timer = group_persistence_frames
        elif self.group_state_timer > 0:
            self.group_state_timer -= 1
            self.in_group = True
        else:
            self.in_group = False
            self.group_neighbors = []
            self.group_center = None
            self.group_strength = 0

    def set_speed(self):
        global average_maturity
        # Calculate the speed based on the size of the Lifeform object
        self.speed = 6 - (self.hunger / 500) - (self.age / 1000) - (self.size / 250) - (self.wounded / 20)
        self.speed += (self.health_now / 200)
        self.speed += (self.energy / 100)

        biome, effects = world.get_environment_context(self.x + self.width / 2, self.y + self.height / 2)
        self.current_biome = biome
        self.environment_effects = effects
        self.speed *= effects["movement"]


        if self.age < self.maturity:
            average_maturity = total_maturity / len(lifeforms)
            if average_maturity != 0:
                factor = self.maturity / average_maturity
                self.speed *= (factor / 10)

        # Constrain the speed value to a certain range
        if self.speed < 1:
            self.speed = 1

        if self.speed > 12:
            self.speed = 12

    def draw(self, surface):
        if self.health_now > 0:
            if show_vision:
                pygame.draw.circle(surface, green, (self.x, self.y), self.vision, 1)

            # pygame.draw.rect(surface, self.color, (self.x, self.y, self.width, self.height))
            # Create a copy of the rect surface to rotate
            rect = pygame.Surface((self.width, self.height))
            rect.set_colorkey(black)
            rect.fill(self.color)
            rect_rotated = pygame.transform.rotate(rect, self.angle)
            rect.get_rect()
            surface.blit(rect_rotated, (self.x, self.y))

            # Create a separate surface for the outline
            outline_copy = pygame.Surface((self.width + 4, self.height + 4))
            outline_copy.set_colorkey(black)
            red_value = int(self.attack_power_now * 2.55)
            blue_value = int(self.defence_power_now * 2.55)
            color = pygame.Color(red_value, 0, blue_value)
            pygame.draw.rect(outline_copy, color, (0, 0, self.width + 2, self.height + 2), 1)
            outline_copy = pygame.transform.rotate(outline_copy, self.angle)
            surface.blit(outline_copy, (self.x, self.y))


            # pygame.draw.rect(surface, color, (self.x, self.y, self.width + 2, self.height + 2), 2)


        else:
            action_log(f"{self.id} is gestorven")
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
        # Create a new DNA profile by mixing the attributes of the two parent Lifeform objects
        child_dna_profile = {
                'dna_id': self.dna_id,  # Assign a new ID to the child Lifeform object
                'width': (self.width + partner.width) // 2,  # Average the width of the two parent Lifeform objects
                'height': (self.height + partner.height) // 2,  # Average the height of the two parent Lifeform objects
                'color': ((self.color[0] + partner.color[0]) // 2, (self.color[1] + partner.color[1]) // 2, (self.color[2] + partner.color[2]) // 2),
                # Mix the colors of the two parent Lifeform objects
                'health': (self.health + partner.health) // 2,  # Average the health of the two parent Lifeform objects
                'maturity': (self.maturity + partner.maturity) // 2,
                    # Average the maturity of the two parent Lifeform objects
                'vision': (self.vision + partner.vision) // 2,  # Average the vision of the two parent Lifeform objects
                'defence_power': (self.defence_power + partner.defence_power) // 2,
                'attack_power': (self.attack_power + partner.attack_power) // 2,
                'energy': (self.energy + partner.energy) // 2,
                'longevity': (self.longevity + partner.longevity) // 2
                }

        # Check if a mutation should occur for each attribute

        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['width'] += random.randint(-10, 10)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['height'] += random.randint(-10, 10)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['color'] = (
                random.randint(0, 255),
                random.randint(0, 255),
                random.randint(0, 255)
            )
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['health'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['maturity'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['vision'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['defence_power'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['attack_power'] += random.randint(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['energy'] += random.uniform(-100, 100)
        if random.randint(0, 100) < mutation_chance:
            child_dna_profile['longevity'] += random.randint(-250, 250)

        # check if values wont go to 0:

        if child_dna_profile['health'] < 1:
            child_dna_profile['health'] = 1
        if child_dna_profile['maturity'] < 1:
            child_dna_profile['maturity'] = 1
        if child_dna_profile['vision'] < 1:
            child_dna_profile['vision'] = 1
        if child_dna_profile['defence_power'] < 1:
            child_dna_profile['defence_power'] = 1
        if child_dna_profile['defence_power'] > 100:
            child_dna_profile['defence_power'] = 100
        if child_dna_profile['attack_power'] < 1:
            child_dna_profile['attack_power'] = 1
        if child_dna_profile['attack_power'] > 100:
            child_dna_profile['attack_power'] = 100
        if child_dna_profile['energy'] < 1:
            child_dna_profile['energy'] = 1
        if child_dna_profile['energy'] > 100:
            child_dna_profile['energy'] = 100
        if child_dna_profile['longevity'] < 1:
            child_dna_profile['longevity'] = 1

        # Calculate the percentage of DNA change from the original initialization
        dna_change = 0
        color_change = 0

        for attribute, value in child_dna_profile.items():
            debug_log(f"DNA {self.dna_id} voortplanting start")
            original_value = 0
            dna_id_check = next((profile for profile in dna_profiles if profile["dna_id"] == self.dna_id), None)
            if dna_id_check is not None:
                debug_log(f"DNA-match gevonden: {dna_id_check}")
                original_value = dna_id_check[attribute]
            debug_log(f"Ouderwaarden voor DNA {self.dna_id}: {original_value}")
            if isinstance(value, tuple):  # Check if the attribute is a color tuple
                color_change = sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(original_value)
                dna_change += sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(original_value)
                if color_change > color_change_threshold:
                    child_dna_profile["dna_id"] = create_dna_id(parent_dna_id=self.dna_id)
                else:
                    pass
            else:
                if original_value != 0:
                    dna_change += abs(original_value - value) / original_value
                else:
                    # Handle the case where the original value is zero
                    # For example, you could skip the calculation for this attribute
                    pass
        debug_log(f"DNA mutatie-index: {dna_change}")
        dna_change /= len(child_dna_profile)  # Calculate the average DNA change
        debug_log(f"DNA mutatie na normalisatie: {dna_change}")

        # Create a new Lifeform object with the mixed DNA profile

        # Change the DNA ID of the child Lifeform object if the DNA has changed more than a certain amount

        # if dna_change > dna_change_threshold:
        #
        #     child_lifeform.dna_id = len(dna_profiles)  # Assign a new DNA ID to the child Lifeform object
        #     dna_profiles.append(child_dna_profile)  # Add the new DNA profile to the dna_profiles list
        #     print("New dna_id: " + str(child_lifeform.dna_id))

        # Compare the child's DNA profile to the initial DNA profile
        if dna_change > dna_change_threshold or color_change > color_change_threshold:
            found = False
            for profile in dna_profiles:
                dna_change_between = 0
                color_change_between = 0
                for attribute, value in child_dna_profile.items():
                    original_value = profile[attribute]
                    if isinstance(value, tuple):  # Check if the attribute is a color tuple
                        dna_change_between += sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(
                            original_value)
                        color_change_between += sum([abs(v - ov) for v, ov in zip(value, original_value)]) / sum(
                            original_value)
                    else:
                        if original_value != 0:
                            dna_change_between += abs(original_value - value) / original_value
                        else:
                            # Handle the case where the original value is zero
                            # For example, you could skip the calculation for this attribute
                            pass
                dna_change_between /= len(child_dna_profile)
                debug_log(f"DNA {profile['dna_id']} afwijking {dna_change_between}")
                # Check if the dna_change_between is less than the threshold and the dna_id is not the parent's dna_id
                if dna_change_between < dna_change_threshold or color_change_between < color_change_threshold and profile["dna_id"] != self.dna_id:
                    debug_log(f"DNA {self.dna_id} wijkt weinig af, behoud profielen")
                    child_dna_profile = profile
                    found = True
                    debug_log(f"Beschikbare DNA-profielen: {[profile['dna_id'] for profile in dna_profiles]}")
            if not found:
                parent_dna_id = self.dna_id
                if parent_dna_id in dna_id_counts:
                    dna_id_counts[parent_dna_id] += 1
                else:
                    dna_id_counts[parent_dna_id] = 1
                child_dna_id = create_dna_id(parent_dna_id)
                child_dna_profile["dna_id"] = child_dna_id
                dna_profiles.append(child_dna_profile)

        child_lifeform = Lifeform(self.x, self.y, child_dna_profile, (self.generation + 1))
        if random.randint(0, 100) < 10:
            child_lifeform.is_leader = True
        lifeforms.append(child_lifeform)
        if player_controller:
            player_controller.on_birth()

            # if not found:
            #     child_lifeform.dna_id = len(dna_profiles)  # Assign a new DNA ID to the child Lifeform object
            #     dna_profiles.append(child_dna_profile)  # Add the new DNA profile to the dna_profiles list
            #     print("New dna_id: " + str(child_lifeform.dna_id))

    def progression(self):
        biome, effects = world.get_environment_context(self.x + self.width / 2, self.y + self.height / 2)
        self.current_biome = biome
        self.environment_effects = effects

        hunger_rate = environment_modifiers.get("hunger_rate", 1.0) * effects["hunger"]
        self.hunger += hunger_rate
        self.age += 1
        self.energy_now += 0.5 * effects["energy"]
        self.wounded -= 1
        self.health_now += effects["health"]

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



########################################################################################################################


class Pheromone:
    def __init__(self, x, y, width, height, color, strength):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.strength = strength

    def draw(self):
        # Calculate the new color values based on the strength value
        r = int(self.color[0] + (255 - self.color[0]) * (255 - self.strength) / 255)
        g = int(self.color[1] + (255 - self.color[1]) * (255 - self.strength) / 255)
        b = int(self.color[2] + (255 - self.color[2]) * (255 - self.strength) / 255)
        color = (r, g, b)
        pygame.draw.rect(screen, color, (self.x, self.y, self.width, self.height))

class Vegetation:
    def __init__(self, x, y, width, height, variant="normal"):
        self.x = x
        self.y = y

        self.width = width
        self.height = height
        self.base_size = self.width * self.height
        self.resource = 100
        self.variant = variant
        self.color = green
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

    def draw(self):
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))

    def set_size(self):
        # Calculate the new width and height based on the resource value
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
            lifeform.vision = min(vision_max, lifeform.vision + 1)
        elif self.variant == "fortified":
            lifeform.health_now = min(lifeform.health, lifeform.health_now + 35)
            lifeform.defence_power = min(100, lifeform.defence_power + 1)
        else:
            lifeform.health_now = min(lifeform.health, lifeform.health_now + 30)
            lifeform.energy_now = min(lifeform.energy, lifeform.energy_now + 20)


########################################################################################################################

class Graph:
    def __init__(self):
        self.figure, self.axes = plt.subplots()
        self.dna_ids = []
        self.avg_ages = []

    def update_data(self, death_ages):
        self.axes.clear()
        self.dna_ids = []
        self.avg_ages = []
        for dna_id in death_ages:
            self.dna_ids.append(dna_id)
            self.avg_ages.append(sum(death_ages[dna_id]) / len(death_ages[dna_id]))
        self.axes.bar(self.dna_ids, self.avg_ages)
        self.axes.set_xlabel("DNA ID")
        self.axes.set_ylabel("Average Age at Death")
        self.axes.set_title("Average Age at Death by DNA ID")
        self.figure.canvas.draw()

    def draw(self, screen):
        plt.draw()
        # convert the figure to a surface
        graph_surface = pygame.surfarray.make_surface(self.figure)
        screen.blit(graph_surface, (x, y))

########################################################################################################################

def reset_list_values():
    global lifeforms
    global dna_profiles
    global pheromones
    global plants
    global death_ages

    lifeforms = []
    dna_profiles = []
    pheromones = []
    plants = []
    death_ages = []
    world.regenerate()
    notification_manager.clear()
    event_manager.reset()
    event_manager.schedule_default_events()
    player_controller.reset()
    environment_modifiers["plant_regrowth"] = 1.0
    environment_modifiers["hunger_rate"] = 1.0



def reset_dna_profiles():
    dna_home_biome.clear()
    for i in range(n_dna_profiles):
        dna_profile = {
            'dna_id': i,
            'width': random.randint(min_width, max_width),
            'height': random.randint(min_height, max_height),
            'color': (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)),
            'health': random.randint(1, 200),
            'maturity': random.randint(min_maturity, max_maturity),
            'vision': random.randint(vision_min, vision_max),
            'defence_power': random.randint(1, 70),
            'attack_power': random.randint(1, 70),
            'energy': random.randint(80, 100),
            'longevity': random.randint(1000, 5000)
        }
        dna_profiles.append(dna_profile)
        if world.biomes:
            dna_home_biome[dna_profile['dna_id']] = random.choice(world.biomes)
        else:
            dna_home_biome[dna_profile['dna_id']] = None

# # Levensvorm-objecten maken met behulp van een for-lus
# for i in range(n_lifeforms):
#     x = (random.randint(0, screen.get_width()))
#     y = (random.randint(0, screen.get_height()))
#
#     generation = 1
#
#     dna_profile = random.choice(dna_profiles)
#     id = len(lifeforms)
#
#
#     lifeform = Lifeform(x, y, id, dna_profile, generation)
#     lifeforms.append(lifeform)
#     for lifeform in lifeforms:
#         if random.randint(0, 100) < 10:
#             lifeform.leader = True
def create_dna_id(parent_dna_id):
    if parent_dna_id in dna_id_counts:
        dna_id_counts[parent_dna_id] += 1
    else:
        dna_id_counts[parent_dna_id] = 1
    return int(f"{parent_dna_id}{dna_id_counts[parent_dna_id]}")


def init_lifeforms():

    for i in range(n_lifeforms):

        dna_profile = random.choice(dna_profiles)
        generation = 1

        preferred_biome = dna_home_biome.get(dna_profile['dna_id'])
        x, y, biome = world.random_position(dna_profile['width'], dna_profile['height'], preferred_biome=preferred_biome)

        lifeform = Lifeform(x, y, dna_profile, generation)
        lifeform.current_biome = biome
        lifeforms.append(lifeform)

def init_vegetation():
    for i in range(n_vegetation):
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

def count_dna_ids(lifeforms):
    dna_counts = {}
    for lifeform in lifeforms:
        dna_id = lifeform.dna_id
        if dna_id in dna_counts:
            dna_counts[dna_id] += 1
        else:
            dna_counts[dna_id] = 1
    return dna_counts


def get_attribute_value(lifeforms, dna_id, attribute):
    total_attribute_value = 0
    count = 0
    for lifeform in lifeforms:
        if lifeform.dna_id == dna_id:
            total_attribute_value += getattr(lifeform, attribute)
            count += 1
    if count:
        return total_attribute_value / count
    else:
        return None


def get_average_rect(lifeforms, dna_id):
    total_width = 0
    total_height = 0
    total_red = 0
    total_green = 0
    total_blue = 0
    count = 0
    for lifeform in lifeforms:
        if lifeform.dna_id == dna_id:
            rect = lifeform.rect
            total_width += rect.width
            total_height += rect.height
            color = rect.color
            total_red += color[0]
            total_green += color[1]
            total_blue += color[2]
            count += 1
    if count > 0:
        average_width = total_width / count
        average_height = total_height / count
        average_red = total_red / count
        average_green = total_green / count
        average_blue = total_blue / count
        average_color = (average_red, average_green, average_blue)
        return (average_width, average_height, average_color)
    else:
        return None

def collect_population_stats(formatted_time_passed):
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
        text_surface = font_small.render(line, True, black)
        surface.blit(text_surface, (50, 20 + idx * 20))

    y_offset = 300
    dna_count_sorted = sorted(stats['dna_count'].items(), key=lambda item: item[1], reverse=True)
    for dna_id, count in dna_count_sorted:
        text = font_large.render(f"Nr. per dna_{dna_id}: {count}", True, black)
        surface.blit(text, (50, y_offset))
        y_offset += 35

        if show_dna_info:
            for attribute in ["health", "vision", "attack_power_now", "defence_power_now", "speed", "maturity", "size", "longevity", "energy"]:
                attribute_value = get_attribute_value(lifeforms, dna_id, attribute)
                if attribute_value is not None:
                    text = font_small.render(f"{attribute}: {round(attribute_value, 2)}", True, black)
                    surface.blit(text, (50, y_offset))
                    y_offset += 20
######################################################################################################################


reset_dna_profiles()
init_lifeforms()
init_vegetation()
event_manager.schedule_default_events()
player_controller.reset()
graph = Graph()

running = True
starting_screen = True

########################################Start Screen###################################################################
while running:
    start_button = pygame.Rect(900, 400, 150, 50)  # Create the button rectangle
    reset_button = pygame.Rect(50, 900, 150, 50)
    show_dna_button = pygame.Rect(50, 800, 20, 20)
    show_dna_info_button = pygame.Rect(50, 780, 20, 20)

    if starting_screen:
        screen.fill(background)

        pygame.draw.rect(screen, green, start_button)  # Draw the button
        pygame.draw.rect(screen, black, start_button, 3)

        # Create the text for the button
        start_text = "Start"
        font = pygame.font.Font(None, 30)
        text_surface = font.render(start_text, True, black)
        text_rect = text_surface.get_rect()
        text_rect.center = start_button.center  # Center the text inside the button

        screen.blit(text_surface, text_rect)  # Draw the text on the screen

        pygame.display.flip()

##############################################Game running#############################################################

    if not paused:
        # Set fonts
        font1_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus8-Regular.ttf"
        expanded_path1 = os.path.expanduser(font1_path)
        font2_path = "~/AppData/Local/Microsoft/Windows/Fonts/8bitOperatorPlus-Bold.ttf"
        expanded_path2 = os.path.expanduser(font2_path)

        font = pygame.font.Font(expanded_path1, 12)
        font2 = pygame.font.Font(expanded_path1, 18)
        font3 = pygame.font.Font(expanded_path2, 22)

        # Limit the loop to the specified frame rate
        clock.tick(fps)

        world.update(pygame.time.get_ticks())
        world.draw(screen)
        world.draw_weather_overview(screen, font2)

        current_time = datetime.datetime.now()
        time_passed = current_time - start_time
        formatted_time_passed = datetime.timedelta(seconds=int(time_passed.total_seconds()))
        formatted_time_passed = str(formatted_time_passed).split(".")[0]

        if death_ages:
            death_age_avg = sum(death_ages) / len(death_ages)

        dna_count = count_dna_ids(lifeforms)


        # # update graph data
        # graph.update_data(death_ages)
        # graph.draw(screen)
        # pygame.display.flip()
        for plant in plants:
            plant.set_size()
            plant.regrow()
            plant.draw()

        for pheromone in pheromones:
            pheromone.strength -= 10
            if pheromone.strength == 0:
                pheromones.remove(pheromone)
            pheromone.draw()

        # Levensvorm-objecten tekenen met behulp van een for-lus

        for lifeform in lifeforms:

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
            lifeform.draw(screen)


            if show_debug:
                text = font.render(f"Health: {lifeform.health_now} ID: {lifeform.id} "
                                    f"cooldown {lifeform.reproduced_cooldown} "
                                    f"gen: {lifeform.generation} "
                                    f"dna_id {lifeform.dna_id} "
                                    # f"speed: {lifeform.speed} "
                                    f"hunger: {lifeform.hunger} "
                                    f"age: {lifeform.age} ",
                                    True,
                                    (0, 0, 0))
                screen.blit(text, (lifeform.x, lifeform.y - 30))
            if show_dna_id:
                text = font2.render(f"{lifeform.dna_id}", True, (0, 0, 0))
                screen.blit(text, (lifeform.x, lifeform.y - 10))
            if show_leader:
                if lifeform.is_leader:
                    text = font.render(f"L", True, (0, 0, 0))
                    screen.blit(text, (lifeform.x, lifeform.y - 30))
            if show_action:
                text = font.render(
                    f"Current target, enemy: {lifeform.closest_enemy.id if lifeform.closest_enemy is not None else None}"
                    f", prey: {lifeform.closest_prey.id if lifeform.closest_prey is not None else None}, partner: "
                    f"{lifeform.closest_partner.id if lifeform.closest_partner is not None else None}, is following: "
                    f"{lifeform.closest_follower.id if lifeform.closest_follower is not None else None} ", True, black)
                screen.blit(text, (lifeform.x, lifeform.y - 20))
            if lifeform.reproduced_cooldown > 0:
                lifeform.reproduced_cooldown -= 1
        stats = collect_population_stats(formatted_time_passed)
        event_manager.schedule_default_events()
        event_manager.update(pygame.time.get_ticks(), stats, player_controller)
        draw_stats_panel(screen, font2, font3, stats)

        pygame.draw.rect(screen, green, reset_button)  # Draw the button
        pygame.draw.rect(screen, black, reset_button, 3)
        pygame.draw.rect(screen, green, show_dna_button)
        pygame.draw.rect(screen, black, show_dna_button, 2)
        pygame.draw.rect(screen, green, show_dna_info_button)
        pygame.draw.rect(screen, black, show_dna_info_button, 2)

        event_manager.draw(screen, font2)
        notification_manager.update()
        notification_manager.draw(screen, font)
        player_controller.draw_overlay(screen, font2)


        pygame.display.flip()

        if len(lifeforms) > 1:
            total_health = 0
            health_avg = 0
            total_vision = 0
            average_vision = 0
            total_gen = 0
            average_gen = 0
            total_hunger = 0
            average_hunger = 0
            total_size = 0
            average_size = 0
            total_age = 0
            average_age = 0
            total_maturity = 0
            average_maturity = 0
            total_speed = 0
            average_speed = 0
            total_cooldown = 0
            average_cooldown = 0


    elif paused:
        # Display the pause message
        pause_text = "sim paused"
        font = pygame.font.Font(None, 20)
        text_surface = font.render(pause_text, True, black)
        text_rect = text_surface.get_rect()
        text_rect.center = (250, 250)

        screen.blit(text_surface, text_rect)
        notification_manager.update()
        notification_manager.draw(screen, font)
        player_controller.draw_overlay(screen, font)
        event_manager.draw(screen, font)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_p:
                # Toggle the paused state when the 'p' key is pressed
                if paused:
                    paused = False
                else:
                    paused = True
            elif event.key == pygame.K_n:
                x = (random.randint(0, screen.get_width()))
                y = (random.randint(0, screen.get_height()))

                generation = 1

                dna_profile = random.choice(dna_profiles)

                lifeform = Lifeform(x, y, dna_profile, generation)
                if random.randint(0, 100) < 10:
                    lifeform.is_leader = True
                lifeforms.append(lifeform)

            elif event.key == pygame.K_b:
                if not show_debug:
                    show_debug = True
                else:
                    show_debug = False
            elif event.key == pygame.K_l:
                if not show_leader:
                    show_leader = True
                else:
                    show_leader = False
            elif event.key == pygame.K_s:
                if not show_action:
                    show_action = True
                else:
                    show_action = False
            elif event.key == pygame.K_v:
                if not show_vision:
                    show_vision = True
                else:
                    show_vision = False
            elif event.key == pygame.K_d:
                show_dna_id = not show_dna_id
            elif event.key == pygame.K_m:
                player_controller.toggle_management()
            elif player_controller.management_mode:
                if event.key == pygame.K_RIGHT:
                    player_controller.cycle_profile(dna_profiles, 1)
                elif event.key == pygame.K_LEFT:
                    player_controller.cycle_profile(dna_profiles, -1)
                elif event.key == pygame.K_UP:
                    player_controller.adjust_attribute(dna_profiles, 1)
                elif event.key == pygame.K_DOWN:
                    player_controller.adjust_attribute(dna_profiles, -1)
                elif event.key == pygame.K_TAB:
                    direction = -1 if (event.mod & pygame.KMOD_SHIFT) else 1
                    player_controller.cycle_attribute(direction)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if start_button.collidepoint(event.pos):
                notification_manager.add("Simulatie gestart", green)
                starting_screen = False  # Set the starting screen flag to False to start the simulation
                paused = False
            if reset_button.collidepoint(event.pos):
                reset_list_values()
                reset_dna_profiles()
                init_lifeforms()
                init_vegetation()
                notification_manager.add("Simulatie gereset", blue)
                starting_screen = True
                paused = True
            if show_dna_button.collidepoint(event.pos):
                notification_manager.add("DNA-ID overlay gewisseld", sea)
                if not show_dna_id:
                    show_dna_id = True
                else:
                    show_dna_id = False
            if show_dna_info_button.collidepoint(event.pos):
                if not show_dna_info:
                    show_dna_info = True
                else:
                    show_dna_info = False


pygame.quit()

"""Mission event system for the evolution simulation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pygame

from ..config import settings
from .notifications import NotificationManager


@dataclass
class Event:
    name: str
    description: str
    duration_ms: int
    objective: Dict[str, object]
    reward: Dict[str, object]
    environment_effects: Dict[str, float] = field(default_factory=dict)
    start_time: Optional[int] = None
    completed: bool = False
    failed: bool = False
    applied_effects: Dict[str, float] = field(default_factory=dict)

    def time_left(self, current_time: int) -> int:
        if self.start_time is None:
            return self.duration_ms
        remaining = self.duration_ms - (current_time - self.start_time)
        return max(0, remaining)


class EventManager:
    def __init__(self, notification_manager: NotificationManager, environment_modifiers: Dict[str, float]):
        self.notification_manager = notification_manager
        self.environment_modifiers = environment_modifiers
        self.events: List[Event] = []
        self.active_event: Optional[Event] = None

    def schedule_default_events(self) -> None:
        if self.events:
            return
        famine = Event(
            name="Drought Alert",
            description="Houd de gemiddelde honger onder 350 terwijl de vegetatie traag groeit.",
            duration_ms=90_000,
            objective={"metric": "average_hunger", "type": "below", "value": 350},
            reward={"dna_points": 45},
            environment_effects={"plant_regrowth": 0.6},
        )
        defence = Event(
            name="Groeispurt",
            description="Vergroot de populatie tot 120 levensvormen.",
            duration_ms=120_000,
            objective={"metric": "lifeform_count", "type": "above", "value": 120},
            reward={"dna_points": 60},
            environment_effects={"hunger_rate": 1.2},
        )
        harmony = Event(
            name="Veiligheidsprotocol",
            description="Bereik een gemiddelde gezondheid van minstens 140.",
            duration_ms=75_000,
            objective={"metric": "average_health", "type": "above", "value": 140},
            reward={"dna_points": 35},
        )
        self.events = [famine, defence, harmony]

    def start_next_event(self, current_time: int) -> None:
        if self.active_event or not self.events:
            return
        self.active_event = self.events.pop(0)
        self.active_event.start_time = current_time
        self._apply_environment_effects(self.active_event)
        self.notification_manager.add(f"Nieuwe missie: {self.active_event.name}", settings.BLUE)
        self.notification_manager.add(self.active_event.description, settings.BLUE)

    def _apply_environment_effects(self, event: Event) -> None:
        for key, value in event.environment_effects.items():
            self.environment_modifiers[key] = self.environment_modifiers.get(key, 1.0) * value
        event.applied_effects = event.environment_effects.copy()

    def _revert_environment_effects(self, event: Event) -> None:
        for key, value in event.applied_effects.items():
            if value:
                self.environment_modifiers[key] = self.environment_modifiers.get(key, 1.0) / value
        event.applied_effects.clear()

    def update(self, current_time: int, stats: Dict[str, float], player_controller) -> None:
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

        if current_time - (event.start_time or current_time) >= event.duration_ms:
            self.fail_event()

    def complete_event(self, player_controller) -> None:
        if not self.active_event or self.active_event.completed:
            return
        self.active_event.completed = True
        self.notification_manager.add(f"Missie voltooid: {self.active_event.name}", settings.GREEN)
        player_controller.apply_reward(self.active_event.reward)

    def fail_event(self) -> None:
        if not self.active_event or self.active_event.failed:
            return
        self.active_event.failed = True
        self.notification_manager.add(f"Missie mislukt: {self.active_event.name}", settings.RED)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if not self.active_event:
            return
        event = self.active_event
        current_time = pygame.time.get_ticks()
        remaining_seconds = int(event.time_left(current_time) / 1000)
        lines = [
            event.name,
            event.description,
            f"Doel: {event.objective['metric']} {event.objective['type']} {event.objective['value']}",
            f"Tijd resterend: {remaining_seconds}s",
        ]
        x = surface.get_width() - 420
        y = surface.get_height() - 140
        for line in lines:
            text_surface = font.render(line, True, settings.BLACK)
            surface.blit(text_surface, (x, y))
            y += 20

    def reset(self) -> None:
        if self.active_event:
            self._revert_environment_effects(self.active_event)
        self.active_event = None
        self.events = []

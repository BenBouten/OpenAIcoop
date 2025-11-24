"""Runtime telemetry helpers for movement/combat diagnostics."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

from pygame.math import Vector2

from ..config import settings


@dataclass(slots=True)
class MovementSample:
    tick: int
    lifeform_id: str
    dna_id: str
    position: tuple[float, float]
    velocity: tuple[float, float]
    desired: tuple[float, float]
    thrust: float
    effort: float
    hunger: float
    energy: float
    attack: float
    defence: float
    size: float
    mass: float
    behavior: str
    has_food_target: bool
    depth: float
    closest_enemy_id: Optional[str]
    closest_prey_id: Optional[str]
    threat_distance: Optional[float]
    prey_distance: Optional[float]
    energy_ratio: float
    adrenaline: float
    is_fleeing: bool
    is_hunting: bool
    move_away: Optional[tuple[float, float]]
    search_pattern: Optional[str]
    predator_count: int


@dataclass(slots=True)
class CombatSample:
    tick: int
    attacker_id: str
    defender_id: str
    damage: float
    attacker_attack: float
    defender_defence: float
    attacker_energy: float
    defender_energy: float


@dataclass(slots=True)
class EventSample:
    tick: int
    category: str
    entity_id: str
    event_type: str
    details: dict


@dataclass(slots=True)
class ReproductionSample:
    tick: int
    parent_1_id: str
    parent_2_id: str
    parent_1_dna: str
    parent_2_dna: str
    offspring_dna: str
    is_new_profile: bool
    dna_change: float
    color_change: float
    mutations: list[str]
    offspring_color: tuple[int, int, int]


class TelemetrySink:
    """Buffered JSONL telemetry writer with background flushing."""

    def __init__(self, kind: str, *, directory: Optional[Path] = None, flush_interval: int = 32) -> None:
        base = directory or Path(settings.LOG_DIRECTORY) / "telemetry"
        base.mkdir(parents=True, exist_ok=True)
        # Use timestamp in filename to avoid overwriting
        timestamp = int(time.time())
        self.path = base / f"{kind}_{timestamp}.jsonl"
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._flush_interval = max(1, flush_interval)
        self._counter = 0

    def write(self, payload: MovementSample | CombatSample | EventSample | ReproductionSample) -> None:
        with self._lock:
            self._buffer.append(asdict(payload))
            self._counter += 1
            if self._counter >= self._flush_interval:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            self._counter = 0
            return
        with self.path.open("a", encoding="utf-8") as handle:
            for row in self._buffer:
                handle.write(json.dumps(row, ensure_ascii=False) + os.linesep)
        self._buffer.clear()
        self._counter = 0


_movement_sink: Optional[TelemetrySink] = None
_combat_sink: Optional[TelemetrySink] = None
_event_sink: Optional[TelemetrySink] = None
_reproduction_sink: Optional[TelemetrySink] = None


def enable_telemetry(kind: str = "all") -> None:
    global _movement_sink, _combat_sink, _event_sink, _reproduction_sink
    if kind in ("movement", "all") and _movement_sink is None:
        _movement_sink = TelemetrySink("movement")
    if kind in ("combat", "all") and _combat_sink is None:
        _combat_sink = TelemetrySink("combat")
    if kind in ("events", "all") and _event_sink is None:
        _event_sink = TelemetrySink("events")
    if kind in ("reproduction", "all") and _reproduction_sink is None:
        _reproduction_sink = TelemetrySink("reproduction")


_last_movement_log: dict[str, int] = {}

def movement_sample(
    *,
    tick: int,
    lifeform,
    desired: Vector2,
    thrust: float,
    effort: float,
) -> None:
    if _movement_sink is None:
        return

    # Sampling: Only log every 60 ticks (approx 1 sec) per entity
    # unless they are in a critical state (e.g. fleeing/hunting)
    lid = getattr(lifeform, "id", "")
    last_tick = _last_movement_log.get(lid, -999)
    
    mode = getattr(lifeform, "current_behavior_mode", "idle")
    interval = 60
    if mode in ("flee", "hunt"):
        interval = 15 # Higher resolution for combat/chase
        
    if tick - last_tick < interval:
        return
        
    _last_movement_log[lid] = tick

    sample = MovementSample(
        tick=tick,
        lifeform_id=lid,
        dna_id=str(getattr(lifeform, "dna_id", "")),
        position=(lifeform.x, lifeform.y),
        velocity=(lifeform.velocity.x, lifeform.velocity.y),
        desired=(desired.x, desired.y),
        thrust=thrust,
        effort=effort,
        hunger=lifeform.hunger,
        energy=lifeform.energy_now,
        attack=getattr(lifeform, "attack_power_now", 0.0),
        defence=getattr(lifeform, "defence_power_now", 0.0),
        size=getattr(lifeform, "size", 0.0),
        mass=getattr(lifeform, "mass", 0.0),
        behavior=mode,
        has_food_target=bool(lifeform.closest_plant or lifeform.closest_prey),
        depth=lifeform.y,
        closest_enemy_id=getattr(getattr(lifeform, "closest_enemy", None), "id", None),
        closest_prey_id=getattr(getattr(lifeform, "closest_prey", None), "id", None),
        threat_distance=_entity_distance(lifeform, getattr(lifeform, "closest_enemy", None)),
        prey_distance=_entity_distance(lifeform, getattr(lifeform, "closest_prey", None)),
        energy_ratio=lifeform.energy_now / max(1.0, float(getattr(lifeform, "energy", 1.0))),
        adrenaline=float(getattr(lifeform, "adrenaline_factor", getattr(lifeform, "adrenaline", 0.0))),
        is_fleeing=bool(getattr(lifeform, "is_fleeing", False)),
        is_hunting=bool(getattr(lifeform, "is_hunting", False)),
        move_away=_compute_move_away(lifeform, getattr(lifeform, "closest_enemy", None)),
        search_pattern=getattr(lifeform, "search_pattern", None),
        predator_count=int(getattr(lifeform, "nearby_predators_count", 0)),
    )
    _movement_sink.write(sample)


def combat_sample(
    *,
    tick: int,
    attacker,
    defender,
    damage: float,
) -> None:
    if _combat_sink is None:
        return
    sample = CombatSample(
        tick=tick,
        attacker_id=getattr(attacker, "id", ""),
        defender_id=getattr(defender, "id", ""),
        damage=damage,
        attacker_attack=getattr(attacker, "attack_power_now", 0.0),
        defender_defence=getattr(defender, "defence_power_now", 0.0),
        attacker_energy=attacker.energy_now,
        defender_energy=defender.energy_now,
    )
    _combat_sink.write(sample)


def log_event(
    category: str,
    event_type: str,
    entity_id: str = "SYSTEM",
    details: dict = None,
    tick: int = 0
) -> None:
    """Log a generic event."""
    if _event_sink is None:
        return
    
    # Auto-detect tick if not provided (requires pygame initialized)
    if tick == 0:
        try:
            import pygame
            tick = pygame.time.get_ticks()
        except:
            pass
            
    sample = EventSample(
        tick=tick,
        category=category,
        entity_id=entity_id,
        event_type=event_type,
        details=details or {}
    )
    _event_sink.write(sample)


def reproduction_sample(
    *,
    tick: int,
    parent_1_id: str,
    parent_2_id: str,
    parent_1_dna: str,
    parent_2_dna: str,
    offspring_dna: str,
    is_new_profile: bool,
    dna_change: float,
    color_change: float,
    mutations: list[str],
    offspring_color: tuple[int, int, int],
) -> None:
    if _reproduction_sink is None:
        return
    sample = ReproductionSample(
        tick=tick,
        parent_1_id=parent_1_id,
        parent_2_id=parent_2_id,
        parent_1_dna=parent_1_dna,
        parent_2_dna=parent_2_dna,
        offspring_dna=offspring_dna,
        is_new_profile=is_new_profile,
        dna_change=dna_change,
        color_change=color_change,
        mutations=mutations,
        offspring_color=offspring_color,
    )
    _reproduction_sink.write(sample)


def flush_all() -> None:
    if _movement_sink:
        _movement_sink.flush()
    if _combat_sink:
        _combat_sink.flush()
    if _event_sink:
        _event_sink.flush()
    if _reproduction_sink:
        _reproduction_sink.flush()


def _entity_center(entity) -> Optional[tuple[float, float]]:
    if entity is None:
        return None
    rect = getattr(entity, "rect", None)
    if rect is not None:
        return float(rect.centerx), float(rect.centery)
    x = getattr(entity, "x", None)
    y = getattr(entity, "y", None)
    if x is None or y is None:
        return None
    return float(x), float(y)


def _entity_distance(source, target) -> Optional[float]:
    source_center = _entity_center(source)
    target_center = _entity_center(target)
    if source_center is None or target_center is None:
        return None
    dx = target_center[0] - source_center[0]
    dy = target_center[1] - source_center[1]
    return (dx * dx + dy * dy) ** 0.5


def _compute_move_away(lifeform, closest_enemy) -> Optional[tuple[float, float]]:
    self_center = _entity_center(lifeform)
    enemy_center = _entity_center(closest_enemy)
    if self_center is None or enemy_center is None:
        return None
    dx = self_center[0] - enemy_center[0]
    dy = self_center[1] - enemy_center[1]
    distance = (dx * dx + dy * dy) ** 0.5
    if distance <= 0:
        return 0.0, 0.0
    return dx / distance, dy / distance


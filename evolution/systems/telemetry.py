"""Runtime telemetry helpers for movement/combat diagnostics."""

from __future__ import annotations

import json
import os
import threading
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


class TelemetrySink:
    """Buffered JSONL telemetry writer with background flushing."""

    def __init__(self, kind: str, *, directory: Optional[Path] = None, flush_interval: int = 32) -> None:
        base = directory or Path(settings.LOG_DIRECTORY) / "telemetry"
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / f"{kind}.jsonl"
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._flush_interval = max(1, flush_interval)
        self._counter = 0

    def write(self, payload: MovementSample | CombatSample) -> None:
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


def enable_telemetry(kind: str = "movement") -> None:
    global _movement_sink, _combat_sink
    if kind in ("movement", "all") and _movement_sink is None:
        _movement_sink = TelemetrySink("movement")
    if kind in ("combat", "all") and _combat_sink is None:
        _combat_sink = TelemetrySink("combat")


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
    sample = MovementSample(
        tick=tick,
        lifeform_id=getattr(lifeform, "id", ""),
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
        behavior=getattr(lifeform, "current_behavior_mode", "unknown"),
        has_food_target=bool(lifeform.closest_plant or lifeform.closest_prey),
        depth=lifeform.y,
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


def flush_all() -> None:
    if _movement_sink:
        _movement_sink.flush()
    if _combat_sink:
        _combat_sink.flush()


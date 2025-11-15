"""Localised floating effects for lifeform interactions."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple
from typing import Iterable, List, Tuple

import pygame
from pygame.math import Vector2

Color = Tuple[int, int, int]

DEFAULT_TEXT_COLOR: Color = (240, 240, 240)
HEAL_COLOR: Color = (110, 220, 170)
DAMAGE_COLOR: Color = (255, 95, 95)
ENERGY_COLOR: Color = (255, 215, 120)
DEATH_COLOR: Color = (120, 120, 120)
BIRTH_COLOR: Color = (255, 150, 220)


@dataclass
class FloatingLabel:
    """A bit of text that drifts upwards and fades out."""

    text: str
    position: Vector2
    velocity: Vector2
    color: Color
    time_left: float
    duration: float

    def update(self, delta: float) -> None:
        self.position += self.velocity * delta
        self.velocity *= 0.9
        # Encourage the label to float upwards slowly.
        self.velocity.y -= 7.0 * delta
        self.velocity *= 0.88
        # Encourage the label to float upwards slowly.
        self.velocity.y -= 6.0 * delta
        self.time_left -= delta

    @property
    def alpha(self) -> int:
        ratio = max(0.0, min(1.0, self.time_left / self.duration))
        return int(255 * ratio)


@dataclass
class ConfettiParticle:
    """Small colourful particle for celebratory effects."""

    position: Vector2
    velocity: Vector2
    color: Color
    time_left: float
    duration: float
    size: int = field(default=3)

    def update(self, delta: float) -> None:
        self.position += self.velocity * delta
        self.velocity *= 0.9
        # Let the particle gently fall downwards over time.
        self.velocity.y += 14.0 * delta
        self.velocity.y += 12.0 * delta
        self.time_left -= delta

    @property
    def alpha(self) -> int:
        ratio = max(0.0, min(1.0, self.time_left / self.duration))
        return int(200 * ratio)


class EffectManager:
    """Tracks temporary on-screen effects such as floating text and confetti."""

    MAX_LABELS = 120
    MAX_PARTICLES = 420

    def __init__(self, font: Optional[pygame.font.Font] = None) -> None:
        self.labels: List[FloatingLabel] = []
        self.confetti: List[ConfettiParticle] = []
        self._font = font or pygame.font.Font(None, 20)
        self._confetti_cache: Dict[Tuple[int, Color], pygame.Surface] = {}

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def set_font(self, font: pygame.font.Font) -> None:
        """Replace the font used for labels."""

        self._font = font

    def clear(self) -> None:
        self.labels.clear()
        self.confetti.clear()

    # ------------------------------------------------------------------
    # Effect spawners
    # ------------------------------------------------------------------
    def spawn_text(
        self,
        position: Tuple[float, float],
        text: str,
        *,
        color: Color = DEFAULT_TEXT_COLOR,
        duration: float = 2.0,
        jitter: float = 3.0,
        upward_velocity: Tuple[float, float] = (-6.0, -18.0),
    ) -> None:
        """Spawn a floating label with custom styling."""

        origin = Vector2(position)
        jitter_vec = Vector2(
            random.uniform(-jitter, jitter),
            random.uniform(-jitter * 0.6, jitter * 0.6),
        )
        velocity = Vector2(
            random.uniform(upward_velocity[0], -upward_velocity[0]),
            random.uniform(upward_velocity[1] * 1.2, upward_velocity[1]),
        )
        label = FloatingLabel(
            text=text,
            position=origin + jitter_vec,
            velocity=velocity,
            color=color,
            time_left=duration,
            duration=duration,
        )
        self.labels.append(label)
        if len(self.labels) > self.MAX_LABELS:
            self.labels = self.labels[-self.MAX_LABELS :]

    def spawn_damage_label(
        self,
        position: Tuple[float, float],
        amount: float,
        *,
        color: Color = DAMAGE_COLOR,
    ) -> None:
        text = f"-{int(round(amount))}"
        self.spawn_text(position, text, color=color)

    def spawn_heal_label(
        self,
        position: Tuple[float, float],
        amount: float,
        *,
        color: Color = HEAL_COLOR,
    ) -> None:
        text = f"+{int(round(amount))}"
        self.spawn_text(position, text, color=color)

    def spawn_energy_label(
        self,
        position: Tuple[float, float],
        amount: float,
    ) -> None:
        text = f"+{int(round(amount))}E"
        self.spawn_text(position, text, color=ENERGY_COLOR)

    def spawn_status_label(
        self,
        position: Tuple[float, float],
        text: str,
        *,
        color: Color = DEFAULT_TEXT_COLOR,
    ) -> None:
        self.spawn_text(position, text, color=color)

    def spawn_woohoo(self, position: Tuple[float, float]) -> None:
        self.spawn_status_label(position, "Woohoo!", color=BIRTH_COLOR)
        self.spawn_confetti(
            position,
            palette=[
                (255, 120, 200),
                (255, 190, 120),
                (140, 200, 255),
                (200, 255, 180),
            ],
            strength=28,
        )

    def spawn_birth(self, position: Tuple[float, float]) -> None:
        self.spawn_status_label(position, "New life!", color=BIRTH_COLOR)
        self.spawn_confetti(
            position,
            palette=[
                (255, 150, 220),
                (120, 200, 255),
                (200, 255, 200),
            ],
            count=18,
            strength=26,
        )

    def spawn_death(self, position: Tuple[float, float]) -> None:
        self.spawn_status_label(position, "RIP", color=DEATH_COLOR)
        self.spawn_confetti(
            position,
            palette=[(80, 80, 80), (140, 140, 140), (60, 60, 60)],
            count=10,
            strength=14,
        )

    def spawn_confetti(
        self,
        position: Tuple[float, float],
        palette: Iterable[Color],
        *,
        count: int = 14,
        strength: float = 22.0,
        duration: float = 2.0,
    ) -> None:
        origin = Vector2(position)
        colors = list(palette) or [(255, 255, 255)]
        for _ in range(count):
            angle = random.uniform(0, 360)
            speed = random.uniform(strength * 0.4, strength)
            velocity = Vector2()
            velocity.from_polar((speed, angle))
            particle = ConfettiParticle(
                position=origin.copy(),
                velocity=velocity,
                color=random.choice(colors),
                time_left=duration,
                duration=duration,
                size=random.randint(2, 4),
            )
            self.confetti.append(particle)
        if len(self.confetti) > self.MAX_PARTICLES:
            self.confetti = self.confetti[-self.MAX_PARTICLES :]

    # ------------------------------------------------------------------
    # Update & draw
    # ------------------------------------------------------------------
    def update(self, delta: float) -> None:
        if not (self.labels or self.confetti):
            return

        alive_labels: List[FloatingLabel] = []
        for label in self.labels:
            label.update(delta)
            if label.time_left > 0:
                alive_labels.append(label)
        self.labels = alive_labels

        alive_particles: List[ConfettiParticle] = []
        for particle in self.confetti:
            particle.update(delta)
            if particle.time_left > 0:
                alive_particles.append(particle)
        self.confetti = alive_particles

    def draw(self, surface: pygame.Surface) -> None:
        if not (self.labels or self.confetti):
            return

        for label in self.labels:
            text_surface = self._font.render(label.text, True, label.color)
            text_surface.set_alpha(label.alpha)
            surface.blit(
                text_surface,
                (label.position.x - text_surface.get_width() / 2, label.position.y),
            )

        for particle in self.confetti:
            alpha = particle.alpha
            if alpha <= 0:
                continue
            sprite = self._get_confetti_sprite(particle.size, particle.color)
            sprite.set_alpha(alpha)
            surface.blit(
                sprite,
                (
                    particle.position.x - particle.size,
                    particle.position.y - particle.size,
                ),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_confetti_sprite(self, radius: int, color: Color) -> pygame.Surface:
        key = (radius, color)
        sprite = self._confetti_cache.get(key)
        if sprite is None:
            diameter = radius * 2
            sprite = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            pygame.draw.circle(
                sprite,
                (*color, 255),
                (radius, radius),
                radius,
            )
            self._confetti_cache[key] = sprite
        return sprite.copy()


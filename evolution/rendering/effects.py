"""Localised floating effects for lifeform interactions."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple

import pygame
from pygame.math import Vector2

Color = Tuple[int, int, int]


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
        self.velocity.y += 12.0 * delta
        self.time_left -= delta

    @property
    def alpha(self) -> int:
        ratio = max(0.0, min(1.0, self.time_left / self.duration))
        return int(200 * ratio)


class EffectManager:
    """Tracks temporary on-screen effects such as floating text and confetti."""

    def __init__(self) -> None:
        self.labels: List[FloatingLabel] = []
        self.confetti: List[ConfettiParticle] = []
        self._font = pygame.font.Font(None, 20)

    def clear(self) -> None:
        self.labels.clear()
        self.confetti.clear()

    # ------------------------------------------------------------------
    # Effect spawners
    # ------------------------------------------------------------------
    def spawn_damage_label(
        self,
        position: Tuple[float, float],
        amount: float,
        color: Color = (255, 90, 90),
    ) -> None:
        text = f"-{int(round(amount))}"
        self._spawn_label(position, text, color)
        self.spawn_confetti(position, palette=[color, (255, 188, 88), (255, 140, 140)])

    def spawn_bite_label(
        self,
        position: Tuple[float, float],
        text: str,
        color: Color = (120, 220, 160),
    ) -> None:
        self._spawn_label(position, text, color)
        self.spawn_confetti(position, palette=[color, (180, 255, 200), (120, 180, 255)])

    def spawn_woohoo(self, position: Tuple[float, float]) -> None:
        self._spawn_label(position, "Woohoo!", (255, 120, 200))
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

    def spawn_confetti(
        self,
        position: Tuple[float, float],
        palette: Iterable[Color],
        count: int = 14,
        strength: float = 22.0,
    ) -> None:
        origin = Vector2(position)
        colors = list(palette)
        if not colors:
            colors = [(255, 255, 255)]
        for _ in range(count):
            angle = random.uniform(0, 360)
            speed = random.uniform(strength * 0.35, strength)
            velocity = Vector2()
            velocity.from_polar((speed, angle))
            particle = ConfettiParticle(
                position=origin.copy(),
                velocity=velocity,
                color=random.choice(colors),
                time_left=2.0,
                duration=2.0,
                size=random.randint(2, 4),
            )
            self.confetti.append(particle)

    # ------------------------------------------------------------------
    # Update & draw
    # ------------------------------------------------------------------
    def update(self, delta: float) -> None:
        for label in list(self.labels):
            label.update(delta)
            if label.time_left <= 0:
                self.labels.remove(label)
        for particle in list(self.confetti):
            particle.update(delta)
            if particle.time_left <= 0:
                self.confetti.remove(particle)

    def draw(self, surface: pygame.Surface) -> None:
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
            diameter = particle.size * 2
            blob = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            pygame.draw.circle(
                blob,
                (*particle.color, alpha),
                (particle.size, particle.size),
                particle.size,
            )
            surface.blit(
                blob,
                (particle.position.x - particle.size, particle.position.y - particle.size),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _spawn_label(
        self,
        position: Tuple[float, float],
        text: str,
        color: Color,
    ) -> None:
        origin = Vector2(position)
        jitter = Vector2(random.uniform(-3.0, 3.0), random.uniform(-2.0, 2.0))
        velocity = Vector2(random.uniform(-6.0, 6.0), random.uniform(-22.0, -16.0))
        label = FloatingLabel(
            text=text,
            position=origin + jitter,
            velocity=velocity,
            color=color,
            time_left=2.0,
            duration=2.0,
        )
        self.labels.append(label)


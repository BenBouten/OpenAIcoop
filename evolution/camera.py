"""Camera utilities for viewport management."""
from __future__ import annotations

import pygame


class Camera:
    def __init__(self, width: int, height: int, world_width: int, world_height: int, base_speed: int = 16):
        self.viewport = pygame.Rect(0, 0, width, height)
        self.world_rect = pygame.Rect(0, 0, world_width, world_height)
        self.base_speed = base_speed

    def move(self, dx: float, dy: float, boost: bool = False) -> None:
        if dx == 0 and dy == 0:
            return
        speed = self.base_speed * (2 if boost else 1)
        self.viewport.x += int(dx * speed)
        self.viewport.y += int(dy * speed)
        self.viewport.clamp_ip(self.world_rect)

    def center_on(self, x: float, y: float) -> None:
        self.viewport.center = (int(x), int(y))
        self.viewport.clamp_ip(self.world_rect)

    def reset(self) -> None:
        self.center_on(self.world_rect.width / 2, self.world_rect.height / 2)

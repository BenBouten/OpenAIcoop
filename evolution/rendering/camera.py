"""Camera utilities for viewport management."""
from __future__ import annotations

from typing import Optional, Tuple

import pygame


class Camera:
    def __init__(
        self,
        width: int,
        height: int,
        world_width: int,
        world_height: int,
        base_speed: int = 16,
        *,
        min_zoom: float = 0.5,
        max_zoom: float = 3.0,
        zoom_step: float = 0.1,
    ) -> None:
        self.window_width = width
        self.window_height = height
        self.viewport = pygame.Rect(0, 0, width, height)
        self.world_rect = pygame.Rect(0, 0, world_width, world_height)
        self.base_speed = base_speed
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.zoom_step = zoom_step
        self.zoom = 1.0

    # ------------------------------------------------------------------
    # Movement & positioning
    # ------------------------------------------------------------------
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
        self.set_zoom(1.0)
        self.center_on(self.world_rect.width / 2, self.world_rect.height / 2)

    def set_window_size(self, width: int, height: int) -> None:
        center = self.viewport.center
        self.window_width = max(1, width)
        self.window_height = max(1, height)
        self._update_viewport_size()
        self.center_on(*center)

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------
    def set_zoom(
        self,
        zoom: float,
        anchor_world: Optional[Tuple[float, float]] = None,
        anchor_screen: Optional[Tuple[float, float]] = None,
    ) -> None:
        zoom = max(self.min_zoom, min(self.max_zoom, zoom))
        if anchor_screen is None:
            anchor_screen = (self.window_width / 2, self.window_height / 2)
        if anchor_world is None:
            anchor_world = self.screen_to_world(anchor_screen)
        self.zoom = zoom
        self._update_viewport_size()
        scale_x = self.viewport.width / self.window_width
        scale_y = self.viewport.height / self.window_height
        left = anchor_world[0] - anchor_screen[0] * scale_x
        top = anchor_world[1] - anchor_screen[1] * scale_y
        self.viewport.left = int(left)
        self.viewport.top = int(top)
        self.viewport.clamp_ip(self.world_rect)

    def adjust_zoom(
        self,
        delta_steps: float,
        anchor_world: Optional[Tuple[float, float]] = None,
        anchor_screen: Optional[Tuple[float, float]] = None,
    ) -> None:
        target = self.zoom + delta_steps * self.zoom_step
        self.set_zoom(target, anchor_world=anchor_world, anchor_screen=anchor_screen)

    def _update_viewport_size(self) -> None:
        width = max(1, int(self.window_width / self.zoom))
        height = max(1, int(self.window_height / self.zoom))
        width = min(width, self.world_rect.width)
        height = min(height, self.world_rect.height)
        self.viewport.width = width
        self.viewport.height = height

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------
    def screen_to_world(self, position: Tuple[float, float]) -> Tuple[float, float]:
        scale_x = self.viewport.width / self.window_width
        scale_y = self.viewport.height / self.window_height
        world_x = self.viewport.left + position[0] * scale_x
        world_y = self.viewport.top + position[1] * scale_y
        return world_x, world_y

    def world_to_screen(self, position: Tuple[float, float]) -> Tuple[int, int]:
        scale_x = self.window_width / self.viewport.width
        scale_y = self.window_height / self.viewport.height
        screen_x = int((position[0] - self.viewport.left) * scale_x)
        screen_y = int((position[1] - self.viewport.top) * scale_y)
        return screen_x, screen_y

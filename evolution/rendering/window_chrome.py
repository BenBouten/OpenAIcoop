"""Reusable helpers for movable and resizable overlay windows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

import pygame


SurfaceSize = Tuple[int, int]


def _display_size() -> SurfaceSize:
    surface = pygame.display.get_surface()
    if surface is not None:
        return surface.get_width(), surface.get_height()
    return 1920, 1080


@dataclass
class WindowChrome:
    """Track drag and resize interactions for a floating window."""

    rect: pygame.Rect
    min_size: SurfaceSize = (200, 160)
    _dragging: bool = field(default=False, init=False)
    _resizing: bool = field(default=False, init=False)
    _drag_offset: Tuple[int, int] = field(default=(0, 0), init=False)
    _resize_origin: Tuple[int, int] = field(default=(0, 0), init=False)
    _initial_size: SurfaceSize = field(default=(0, 0), init=False)
    _geometry_dirty: bool = field(default=False, init=False)

    def handle_event(
        self, event: pygame.event.Event, header_rect: Optional[pygame.Rect]
    ) -> Tuple[bool, bool]:
        """Handle mouse events; returns (consumed, geometry_changed)."""

        consumed = False
        geometry_changed = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if header_rect and header_rect.collidepoint(event.pos):
                self._dragging = True
                self._drag_offset = (event.pos[0] - self.rect.x, event.pos[1] - self.rect.y)
                consumed = True
            elif self.resize_handle.collidepoint(event.pos):
                self._resizing = True
                self._resize_origin = event.pos
                self._initial_size = (self.rect.width, self.rect.height)
                consumed = True
        elif event.type == pygame.MOUSEMOTION:
            if self._dragging:
                new_x = event.pos[0] - self._drag_offset[0]
                new_y = event.pos[1] - self._drag_offset[1]
                if (new_x, new_y) != (self.rect.x, self.rect.y):
                    self.rect.update(new_x, new_y, self.rect.width, self.rect.height)
                    self._clamp_within_display()
                    geometry_changed = True
                consumed = True
            elif self._resizing:
                delta_x = event.pos[0] - self._resize_origin[0]
                delta_y = event.pos[1] - self._resize_origin[1]
                width = max(self.min_size[0], self._initial_size[0] + delta_x)
                height = max(self.min_size[1], self._initial_size[1] + delta_y)
                if width != self.rect.width or height != self.rect.height:
                    self.rect.width = width
                    self.rect.height = height
                    self._clamp_within_display()
                    geometry_changed = True
                consumed = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging or self._resizing:
                self._dragging = False
                self._resizing = False
                consumed = True

        if geometry_changed:
            self._geometry_dirty = True

        return consumed, geometry_changed

    @property
    def resize_handle(self) -> pygame.Rect:
        return pygame.Rect(self.rect.right - 18, self.rect.bottom - 18, 16, 16)

    def consume_geometry_changed(self) -> bool:
        changed = self._geometry_dirty
        self._geometry_dirty = False
        return changed

    def mark_geometry_dirty(self) -> None:
        self._geometry_dirty = True

    def clamp_to_display(self) -> None:
        self._clamp_within_display()

    def _clamp_within_display(self) -> None:
        width, height = _display_size()
        max_width = max(self.min_size[0], width)
        max_height = max(self.min_size[1], height)
        self.rect.width = min(self.rect.width, max_width)
        self.rect.height = min(self.rect.height, max_height)
        self.rect.x = max(0, min(self.rect.x, width - self.rect.width))
        self.rect.y = max(0, min(self.rect.y, height - self.rect.height))


def draw_resize_grip(surface: pygame.Surface, chrome: WindowChrome) -> None:
    """Render a simple resize grip in the lower-right corner of a window."""

    grip = chrome.resize_handle
    pygame.draw.rect(surface, (160, 160, 160), grip, border_radius=3)
    pygame.draw.line(surface, (90, 90, 90), grip.bottomleft, grip.topright, 2)
    pygame.draw.line(surface, (90, 90, 90), grip.bottomleft, grip.midtop, 2)

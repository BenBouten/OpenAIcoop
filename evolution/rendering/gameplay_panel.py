"""Lightweight gameplay settings panel with slider widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Tuple

import pygame


@dataclass
class SliderConfig:
    """Configuration for a slider binding."""

    key: str
    label: str
    min_value: float
    max_value: float
    start_value: float
    step: float
    value_format: str
    callback: Callable[[float], None]


class Slider:
    """Minimal slider widget that supports dragging and callbacks."""

    def __init__(self, config: SliderConfig, width: int) -> None:
        self.config = config
        self.width = width
        self.height = 52
        self.value = float(config.start_value)
        self.dragging = False

        self._label_pos: Tuple[int, int] = (0, 0)
        self._track_rect = pygame.Rect(0, 0, width, 6)
        self._handle_rect = pygame.Rect(0, 0, 12, 18)

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(
            self._label_pos[0],
            self._label_pos[1],
            self.width,
            self.height,
        )

    def set_position(self, x: int, y: int) -> None:
        self._label_pos = (x, y)
        track_y = y + 26
        self._track_rect = pygame.Rect(x, track_y, self.width, 6)
        self._update_handle_rect()

    def _update_handle_rect(self) -> None:
        ratio = 0.0
        if self.config.max_value != self.config.min_value:
            ratio = (self.value - self.config.min_value) / (
                self.config.max_value - self.config.min_value
            )
        ratio = max(0.0, min(1.0, ratio))
        handle_x = int(self._track_rect.x + ratio * self._track_rect.width)
        self._handle_rect = pygame.Rect(handle_x - 6, self._track_rect.y - 6, 12, 18)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        label_surface = font.render(self.config.label, True, (30, 30, 30))
        surface.blit(label_surface, self._label_pos)

        track_rect = self._track_rect
        pygame.draw.rect(surface, (210, 210, 210), track_rect, border_radius=3)

        fill_width = int((self.value - self.config.min_value) / (
            self.config.max_value - self.config.min_value or 1
        ) * track_rect.width)
        if fill_width > 0:
            fill_rect = pygame.Rect(track_rect.x, track_rect.y, fill_width, track_rect.height)
            pygame.draw.rect(surface, (80, 160, 120), fill_rect, border_radius=3)

        pygame.draw.rect(surface, (50, 50, 50), track_rect, 1, border_radius=3)
        pygame.draw.rect(surface, (80, 160, 120), self._handle_rect, border_radius=4)
        pygame.draw.rect(surface, (40, 40, 40), self._handle_rect, 1, border_radius=4)

        display_value = self.config.value_format.format(value=self.value)
        value_surface = font.render(display_value, True, (40, 40, 40))
        value_pos = (track_rect.right + 12, track_rect.y - value_surface.get_height() // 2 + 3)
        surface.blit(value_surface, value_pos)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._track_rect.collidepoint(event.pos) or self._handle_rect.collidepoint(event.pos):
                self.dragging = True
                self._update_value_from_pos(event.pos[0])
                return True
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self._update_value_from_pos(event.pos[0])
            return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False
            self._update_value_from_pos(event.pos[0])
            return True
        return False

    def _update_value_from_pos(self, mouse_x: int) -> None:
        ratio = (mouse_x - self._track_rect.x) / float(self._track_rect.width or 1)
        ratio = max(0.0, min(1.0, ratio))
        value = self.config.min_value + ratio * (
            self.config.max_value - self.config.min_value
        )
        step = self.config.step
        if step > 0:
            value = round(value / step) * step
        value = max(self.config.min_value, min(self.config.max_value, value))
        if abs(value - self.value) > 1e-6:
            self.value = value
            self._update_handle_rect()
            self.config.callback(value)


class GameplaySettingsPanel:
    """Sidebar panel with a collection of slider widgets."""

    def __init__(
        self,
        rect: pygame.Rect,
        font: pygame.font.Font,
        heading_font: pygame.font.Font,
        slider_configs: List[SliderConfig],
    ) -> None:
        self.rect = rect
        self.font = font
        self.heading_font = heading_font
        self._sliders: List[Slider] = []

        slider_width = rect.width - 70
        y_offset = rect.top + 60
        for config in slider_configs:
            slider = Slider(config, slider_width)
            slider.set_position(rect.left + 20, y_offset)
            self._sliders.append(slider)
            y_offset += slider.height

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if event.type == pygame.MOUSEBUTTONDOWN and not self.rect.collidepoint(event.pos):
                return False
        consumed = False
        for slider in self._sliders:
            if slider.handle_event(event):
                consumed = True
        return consumed

    def draw(self, surface: pygame.Surface) -> None:
        panel_surface = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        panel_surface.fill((255, 255, 255, 220))
        surface.blit(panel_surface, self.rect.topleft)
        pygame.draw.rect(surface, (60, 60, 60), self.rect, 1)

        heading = self.heading_font.render("Gameplay Settings", True, (20, 20, 20))
        heading_pos = (
            self.rect.left + (self.rect.width - heading.get_width()) // 2,
            self.rect.top + 20,
        )
        surface.blit(heading, heading_pos)

        for slider in self._sliders:
            slider.draw(surface, self.font)

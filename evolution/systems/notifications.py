"""Notification overlay utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

from ..config import settings

Color = Tuple[int, int, int]


@dataclass
class Notification:
    message: str
    color: Color
    frames_left: int


class NotificationManager:
    def __init__(self):
        self.notifications: List[Notification] = []

    def add(self, message: str, color: Color = settings.BLACK, duration: Optional[int] = None) -> None:
        if duration is None:
            duration = settings.FPS * 3
        self.notifications.append(Notification(message, color, duration))

    def clear(self) -> None:
        self.notifications.clear()

    def update(self) -> None:
        for notification in list(self.notifications):
            notification.frames_left -= 1
            if notification.frames_left <= 0:
                self.notifications.remove(notification)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, limit: int = 6) -> None:
        y_offset = 20
        for notification in self.notifications[-limit:]:
            text_surface = font.render(notification.message, True, notification.color)
            surface.blit(text_surface, (surface.get_width() - text_surface.get_width() - 40, y_offset))
            y_offset += 20

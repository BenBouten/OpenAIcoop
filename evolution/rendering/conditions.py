"""Simple rendering condition helpers to avoid expensive work when off-screen."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from pygame import Rect


@dataclass
class RenderBounds:
    """Viewport bounds and padding to cull off-screen work."""

    rect: Rect
    padding: int = 64

    def expanded(self) -> Rect:
        bounds = self.rect.inflate(self.padding * 2, self.padding * 2)
        bounds.topleft = (self.rect.left - self.padding, self.rect.top - self.padding)
        return bounds

    def contains(self, pos: Tuple[float, float], width: int, height: int) -> bool:
        area = self.expanded()
        return area.colliderect(Rect(int(pos[0]), int(pos[1]), width, height))


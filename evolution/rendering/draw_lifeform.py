"""Lifeform rendering helpers."""

from __future__ import annotations

import pygame

from .sprite_cache import lifeform_sprite_cache


def _centered_position(lifeform, sprite: pygame.Surface) -> tuple[int, int]:
    width_diff = sprite.get_width() - lifeform.width
    height_diff = sprite.get_height() - lifeform.height
    x = int(lifeform.x - width_diff / 2)
    y = int(lifeform.y - height_diff / 2)
    return x, y


def draw_lifeform(surface, lifeform, settings):
    """Draw a lifeform body and status outline onto ``surface``."""
    if lifeform.health_now <= 0:
        return

    body = lifeform_sprite_cache.get_body(lifeform)
    surface.blit(body, _centered_position(lifeform, body))

    outline = pygame.Surface((lifeform.width + 4, lifeform.height + 4))
    outline.set_colorkey(settings.BLACK)
    red_value = int(max(0, min(255, lifeform.attack_power_now * 2.55)))
    blue_value = int(max(0, min(255, lifeform.defence_power_now * 2.55)))
    color = pygame.Color(red_value, 0, blue_value)
    pygame.draw.rect(outline, color, (0, 0, lifeform.width + 2, lifeform.height + 2), 1)
    outline = pygame.transform.rotate(outline, lifeform.angle)
    surface.blit(outline, _centered_position(lifeform, outline))


def draw_lifeform_vision(surface, lifeform, settings):
    """Draw the vision radius indicator for a lifeform."""
    if lifeform.health_now <= 0:
        return

    pygame.draw.circle(
        surface,
        settings.GREEN,
        (int(lifeform.rect.centerx), int(lifeform.rect.centery)),
        int(getattr(lifeform, "sensory_range", lifeform.vision)),
        1,
    )

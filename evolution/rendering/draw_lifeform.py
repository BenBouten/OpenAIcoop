"""Lifeform rendering helpers."""

from __future__ import annotations

import pygame


def draw_lifeform(surface, lifeform, settings):
    """Draw a lifeform body and status outline onto ``surface``."""
    if lifeform.health_now <= 0:
        return

    body = pygame.Surface((lifeform.width, lifeform.height))
    body.set_colorkey(settings.BLACK)
    body.fill(lifeform.color)
    body = pygame.transform.rotate(body, lifeform.angle)
    surface.blit(body, (lifeform.x, lifeform.y))

    outline = pygame.Surface((lifeform.width + 4, lifeform.height + 4))
    outline.set_colorkey(settings.BLACK)
    red_value = int(max(0, min(255, lifeform.attack_power_now * 2.55)))
    blue_value = int(max(0, min(255, lifeform.defence_power_now * 2.55)))
    color = pygame.Color(red_value, 0, blue_value)
    pygame.draw.rect(outline, color, (0, 0, lifeform.width + 2, lifeform.height + 2), 1)
    outline = pygame.transform.rotate(outline, lifeform.angle)
    surface.blit(outline, (lifeform.x, lifeform.y))


def draw_lifeform_vision(surface, lifeform, settings):
    """Draw the vision radius indicator for a lifeform."""
    if lifeform.health_now <= 0:
        return

    pygame.draw.circle(surface, settings.GREEN, (int(lifeform.x), int(lifeform.y)), int(lifeform.vision), 1)

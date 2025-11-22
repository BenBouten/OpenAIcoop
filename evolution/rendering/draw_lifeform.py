"""Lifeform rendering helpers."""

from __future__ import annotations

import pygame

from .sprite_cache import lifeform_sprite_cache

# Threshold below which no darkening is applied (effectively full brightness)
_MIN_DARKNESS_THRESHOLD = 0.99


def _centered_position(lifeform, sprite: pygame.Surface) -> tuple[int, int]:
    width_diff = sprite.get_width() - lifeform.width
    height_diff = sprite.get_height() - lifeform.height
    x = int(lifeform.x - width_diff / 2)
    y = int(lifeform.y - height_diff / 2)
    return x, y


def _calculate_depth_darkness(y_position: float, world_height: float) -> float:
    """Calculate darkness multiplier based on depth (0.0 = black, 1.0 = full brightness).

    Args:
        y_position: Y coordinate of the lifeform (0 = surface, world_height = bottom)
        world_height: Total height of the world

    Returns:
        Darkness multiplier from 1.0 (surface, full brightness) to 0.0 (abyss, complete darkness)
    """
    if world_height <= 0:
        return 1.0

    # Normalize depth: 0.0 at surface, 1.0 at bottom
    depth_ratio = y_position / world_height
    depth_ratio = max(0.0, min(1.0, depth_ratio))

    # Apply exponential curve for more realistic light falloff
    # Surface (0.0) -> 1.0 brightness
    # Middle (0.5) -> ~0.287 brightness (actual: (1-0.5)^1.8)
    # Bottom (1.0) -> 0.0 brightness (complete darkness)
    brightness = (1.0 - depth_ratio) ** 1.8

    return brightness


def _apply_depth_shading(sprite: pygame.Surface, darkness_factor: float) -> pygame.Surface:
    """Apply depth-based darkening to a sprite.

    Args:
        sprite: The original sprite surface
        darkness_factor: Brightness multiplier (0.0 = black, 1.0 = unchanged)

    Returns:
        A new surface with depth shading applied
    """
    if darkness_factor >= _MIN_DARKNESS_THRESHOLD:
        # No darkening needed
        return sprite

    # Create a copy to avoid modifying the cached sprite
    # Ensure it has SRCALPHA for proper blending
    darkened = sprite.copy()
    if not darkened.get_flags() & pygame.SRCALPHA:
        darkened = darkened.convert_alpha()

    # Create a black overlay with transparency based on darkness
    overlay = pygame.Surface(darkened.get_size(), pygame.SRCALPHA)
    alpha = int(255 * (1.0 - darkness_factor))
    overlay.fill((0, 0, 0, alpha))

    # Blend the overlay onto the sprite using standard alpha blending
    # This darkens the sprite by overlaying black with appropriate transparency
    darkened.blit(overlay, (0, 0))

    return darkened


def draw_lifeform(surface, lifeform, settings, world_height: float | None = None):
    """Draw a lifeform body and status outline onto ``surface``.

    Args:
        surface: Surface to draw on
        lifeform: The lifeform to draw
        settings: Game settings
        world_height: Total height of the world for depth-based darkening (optional)
    """
    if lifeform.health_now <= 0:
        return

    body = lifeform_sprite_cache.get_body(lifeform)

    # Apply depth-based darkening if world_height is provided
    if world_height is not None:
        darkness_factor = _calculate_depth_darkness(lifeform.y, world_height)
        body = _apply_depth_shading(body, darkness_factor)

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

"""Lifeform rendering helpers."""

from __future__ import annotations

import pygame

from ..config import settings
from .camera import Camera
from .conditions import RenderBounds
from .sprite_cache import lifeform_sprite_cache
from .modular_lifeform_renderer import modular_lifeform_renderer


# Threshold below which no darkening is applied (effectively full brightness)
_MIN_DARKNESS_THRESHOLD = 0.99

def _render_dimensions(lifeform) -> tuple[int, int]:
    if settings.USE_BODYGRAPH_SIZE:
        geometry = getattr(lifeform, "profile_geometry", {}) or getattr(lifeform, "body_geometry", {})
        width_m = geometry.get("width")
        height_m = geometry.get("height")
        if width_m is not None or height_m is not None:
            width_px = width_m if width_m is not None else getattr(lifeform, "width", 1)
            height_px = height_m if height_m is not None else getattr(lifeform, "height", 1)
            return (
                int(round(max(1.0, width_px * settings.BODY_PIXEL_SCALE if width_m is not None else width_px))),
                int(round(max(1.0, height_px * settings.BODY_PIXEL_SCALE if height_m is not None else height_px))),
            )
    return (
        int(round(max(1.0, getattr(lifeform, "width", 1)))),
        int(round(max(1.0, getattr(lifeform, "height", 1)))),
    )


def _centered_position(
    lifeform, sprite: pygame.Surface, reference: tuple[int, int], offset: tuple[int, int]
) -> tuple[int, int]:
    width_diff = sprite.get_width() - reference[0]
    height_diff = sprite.get_height() - reference[1]
    x = int(lifeform.x - width_diff / 2) - offset[0]
    y = int(lifeform.y - height_diff / 2) - offset[1]
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

    # Multiply RGB channels to darken while preserving the original alpha mask.
    # Using RGBA_MULT avoids drawing over transparent regions, preventing black
    # squares from appearing around sprites with per-pixel transparency.
    multiplier = int(255 * darkness_factor)
    darkened.fill((multiplier, multiplier, multiplier, 255), special_flags=pygame.BLEND_RGBA_MULT)

    return darkened


def draw_lifeform(
    surface,
    lifeform,
    settings,
    *,
    camera: Camera | None = None,
    render_bounds: RenderBounds | None = None,
    world_height: float | None = None,
    offset: tuple[int, int] = (0, 0),
):
    """Draw a lifeform body and status outline onto ``surface``."""
    if lifeform.health_now <= 0:
        return

    render_width, render_height = _render_dimensions(lifeform)
    if camera is not None:
        bounds = render_bounds or camera.render_bounds()
        if not bounds.contains((lifeform.x - render_width / 2, lifeform.y - render_height / 2), render_width, render_height):
            return

    body_graph = getattr(lifeform, "body_graph", None)
    if body_graph is not None:
        body, reference = modular_lifeform_renderer.render_surface(lifeform)
        # Rotate the body to match the lifeform's orientation
        # Note: We rotate the surface itself because the modular renderer draws in local space (mostly)
        # or at least the surface is generated axis-aligned to the body's base dimensions.
        body = pygame.transform.rotate(body, lifeform.angle)
    else:
        body = lifeform_sprite_cache.get_body(lifeform)
        reference = (render_width, render_height)

    if world_height is not None:
        darkness_factor = _calculate_depth_darkness(lifeform.y, world_height)
        body = _apply_depth_shading(body, darkness_factor)

    surface.blit(body, _centered_position(lifeform, body, reference, offset))

    outline = pygame.Surface((render_width + 4, render_height + 4))
    outline.set_colorkey(settings.BLACK)
    red_value = int(max(0, min(255, lifeform.attack_power_now * 2.55)))
    blue_value = int(max(0, min(255, lifeform.defence_power_now * 2.55)))
    color = pygame.Color(red_value, 0, blue_value)
    pygame.draw.rect(outline, color, (0, 0, render_width + 2, render_height + 2), 1)
    outline = pygame.transform.rotate(outline, lifeform.angle)
    surface.blit(
        outline,
        _centered_position(lifeform, outline, (render_width, render_height), offset),
    )


def draw_lifeform_vision(
    surface,
    lifeform,
    settings,
    *,
    camera: Camera | None = None,
    render_bounds: RenderBounds | None = None,
    offset: tuple[int, int] = (0, 0),
):
    """Draw the vision radius indicator for a lifeform."""
    if lifeform.health_now <= 0:
        return
    if camera is not None:
        bounds = render_bounds or camera.render_bounds(padding=128)
        radius = int(getattr(lifeform, "sensory_range", lifeform.vision))
        if not bounds.contains((lifeform.rect.centerx - radius, lifeform.rect.centery - radius), radius * 2, radius * 2):
            return

    pygame.draw.circle(
        surface,
        settings.GREEN,
        (
            int(lifeform.rect.centerx) - offset[0],
            int(lifeform.rect.centery) - offset[1],
        ),
        int(getattr(lifeform, "sensory_range", lifeform.vision)),
        1,
    )

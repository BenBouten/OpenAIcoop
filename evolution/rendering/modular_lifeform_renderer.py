"""Render modular BodyGraph creatures directly onto pygame surfaces."""

from __future__ import annotations

import pygame
from pygame import Surface
from pygame.math import Vector2

from ..config import settings
from ..entities.lifeform import Lifeform
from .modular_renderer import BodyGraphRenderer, ModularRendererState

# Cache renderer per surface size to reuse lists instead of reallocating each draw
_renderer_cache: dict[tuple[int, int], BodyGraphRenderer] = {}


def _get_renderer(surface: Surface, torso_color) -> BodyGraphRenderer:
    key = (surface.get_width(), surface.get_height())
    renderer = _renderer_cache.get(key)
    if renderer is None:
        renderer = BodyGraphRenderer(surface, torso_color, position_scale=settings.BODY_PIXEL_SCALE)
        _renderer_cache[key] = renderer
    else:
        renderer.surface = surface
        renderer.torso_color = torso_color
    return renderer


class ModularLifeformRenderer:
    """Helper that reuses BodyGraphRenderer to draw lifeforms in the sim."""

    def __init__(self, pixel_scale: float) -> None:
        self.pixel_scale = pixel_scale

    def _ensure_state(self, lifeform: Lifeform) -> ModularRendererState:
        graph = getattr(lifeform, "body_graph", None)
        if graph is None:
            raise ValueError("Lifeform missing body_graph; cannot render modular body")

        state: ModularRendererState | None = getattr(lifeform, "_modular_render_state", None)
        if state is None or state.graph is not graph:
            state = ModularRendererState(graph, lifeform.body_color)
            setattr(lifeform, "_modular_render_state", state)
        state.torso_color = lifeform.body_color
        return state

    def render_surface(self, lifeform: Lifeform) -> tuple[Surface, tuple[int, int]]:
        state = self._ensure_state(lifeform)
        state.refresh()
        thrust = getattr(lifeform, "physics", None) and getattr(lifeform.physics, "thrust_output", 0.0) or 0.0
        state.rebuild_world_poses(
            angular_velocity=getattr(lifeform, "angular_velocity", 0.0),
            thrust_output=thrust
        )
        base_width = max(1, getattr(lifeform, "base_width", lifeform.width))
        base_height = max(1, getattr(lifeform, "base_height", lifeform.height))
        # Increase margin significantly to allow for long tentacles (e.g. 6.0 length * 36 scale ~ 200px)
        margin = int(self.pixel_scale * 8.0) 
        surf_width = base_width + margin * 2
        surf_height = base_height + margin * 2
        surface = pygame.Surface(
            (surf_width, surf_height), flags=pygame.SRCALPHA, depth=32
        ).convert_alpha()
        surface.fill((0, 0, 0, 0))
        renderer = _get_renderer(surface, lifeform.body_color)
        renderer.set_debug_overlays(False)
        renderer.draw(state, Vector2(surf_width / 2, surf_height / 2))
        return surface, (surf_width, surf_height)


modular_lifeform_renderer = ModularLifeformRenderer(settings.BODY_PIXEL_SCALE)

"""Chunked rendering helpers for static world layers."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import pygame

from ...world.world import World


DEFAULT_CHUNK_SIZE = int(os.getenv("EVOLUTION_CHUNK_SIZE", "512"))


@dataclass(frozen=True, slots=True)
class Chunk:
    """A pre-rendered portion of the world background."""

    surface: pygame.Surface
    rect: pygame.Rect


class ChunkManager:
    """Manage static world chunks and visibility queries."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE) -> None:
        self.chunk_size = max(64, int(chunk_size))
        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self._world: World | None = None

    # ------------------------------------------------------------------
    # Build & streaming
    # ------------------------------------------------------------------
    def build_static_chunks(self, world: World) -> None:
        """Pre-render static layers (biomes/water/barriers) into chunks."""

        self._world = world
        self.chunks.clear()

        cols = math.ceil(world.width / self.chunk_size)
        rows = math.ceil(world.height / self.chunk_size)

        for cy in range(rows):
            for cx in range(cols):
                rect = pygame.Rect(
                    cx * self.chunk_size,
                    cy * self.chunk_size,
                    min(self.chunk_size, world.width - cx * self.chunk_size),
                    min(self.chunk_size, world.height - cy * self.chunk_size),
                )
                surface = pygame.Surface(rect.size)
                world.draw_static_region(surface, rect)
                self.chunks[(cx, cy)] = Chunk(surface=surface, rect=rect)

    def ensure_chunks(self, viewport: pygame.Rect, margin: int = 1) -> None:
        """Ensure chunks around the viewport exist (supports lazy streaming)."""

        if self._world is None:
            return

        missing: List[Tuple[int, int]] = []
        for coords in self._chunk_coords_for_rect(viewport, margin=margin):
            if coords not in self.chunks:
                missing.append(coords)

        if not missing:
            return

        for cx, cy in missing:
            rect = pygame.Rect(
                cx * self.chunk_size,
                cy * self.chunk_size,
                min(self.chunk_size, self._world.width - cx * self.chunk_size),
                min(self.chunk_size, self._world.height - cy * self.chunk_size),
            )
            surface = pygame.Surface(rect.size)
            self._world.draw_static_region(surface, rect)
            self.chunks[(cx, cy)] = Chunk(surface=surface, rect=rect)

    def unload_far_chunks(self, viewport: pygame.Rect, max_distance: int = 3) -> None:
        """Unload chunks that are more than ``max_distance`` away (optional)."""

        if not self.chunks:
            return

        keep: set[Tuple[int, int]] = set(
            self._chunk_coords_for_rect(viewport, margin=max_distance)
        )
        for key in list(self.chunks.keys()):
            if key not in keep:
                self.chunks.pop(key, None)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def get_visible_chunks(self, viewport_rect: pygame.Rect) -> List[Chunk]:
        """Return chunks that intersect the given viewport."""

        visible: List[Chunk] = []
        for coords in self._chunk_coords_for_rect(viewport_rect):
            chunk = self.chunks.get(coords)
            if chunk is not None:
                visible.append(chunk)
        return visible

    def chunk_coords_for_point(self, x: float, y: float) -> Tuple[int, int]:
        """Map a world coordinate to chunk grid coordinates."""

        return (int(x) // self.chunk_size, int(y) // self.chunk_size)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _chunk_coords_for_rect(
        self, rect: pygame.Rect, *, margin: int = 0
    ) -> Iterable[Tuple[int, int]]:
        start_x = max(0, rect.left // self.chunk_size - margin)
        start_y = max(0, rect.top // self.chunk_size - margin)
        end_x = rect.right // self.chunk_size + margin
        end_y = rect.bottom // self.chunk_size + margin

        for cy in range(start_y, end_y + 1):
            for cx in range(start_x, end_x + 1):
                yield (cx, cy)


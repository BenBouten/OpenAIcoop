"""Chunked rendering helpers for static world layers."""

from __future__ import annotations

import math
import os
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Mapping, Tuple

import pygame

from ...world.world import World


DEFAULT_CHUNK_SIZE = int(os.getenv("EVOLUTION_CHUNK_SIZE", "512"))


@dataclass(slots=True)
class Chunk:
    """A pre-rendered portion of the world background."""

    rect: pygame.Rect
    surface: pygame.Surface | None = None
    dirty_static: bool = False
    dirty_overlay: bool = False
    last_used: int = 0


class _EntityIndex:
    """Simple chunk-based lookup for entities with ``rect`` attributes."""

    def __init__(self, chunk_size: int) -> None:
        self.chunk_size = chunk_size
        self._by_type: Dict[str, Dict[Tuple[int, int], List[object]]] = {}

    def rebuild(self, entities: Mapping[str, Iterable[object]], *, coords_for_rect) -> None:
        self._by_type = {key: {} for key in entities.keys()}
        for entity_type, items in entities.items():
            bucket = self._by_type[entity_type]
            for obj in items:
                rect = getattr(obj, "rect", None)
                if rect is None:
                    continue
                for coords in coords_for_rect(rect):
                    bucket.setdefault(coords, []).append(obj)

    def entities_in_rect(
        self, rect: pygame.Rect, *, coords_for_rect, margin: int = 0
    ) -> Dict[str, List[object]]:
        results: Dict[str, List[object]] = {key: [] for key in self._by_type.keys()}
        seen: set[int] = set()
        for coords in coords_for_rect(rect, margin=margin):
            for entity_type, by_chunk in self._by_type.items():
                candidates = by_chunk.get(coords)
                if not candidates:
                    continue
                target = results[entity_type]
                for obj in candidates:
                    marker = id(obj)
                    if marker in seen:
                        continue
                    seen.add(marker)
                    target.append(obj)
        return results


class ChunkManager:
    """Manage static world chunks and visibility queries."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        *,
        streaming_enabled: bool = True,
        max_rebuilds_per_frame: int = 2,
    ) -> None:
        self.chunk_size = max(64, int(chunk_size))
        self.streaming_enabled = streaming_enabled
        self.max_rebuilds_per_frame = max(1, int(max_rebuilds_per_frame))
        self.culling_margin = 200

        self.chunks: Dict[Tuple[int, int], Chunk] = {}
        self._world: World | None = None
        self._dirty_queue: Deque[Tuple[int, int]] = deque()
        self._queued: set[Tuple[int, int]] = set()
        self._frame_index: int = 0
        self.rebuilds_this_frame: int = 0

        self._entity_index = _EntityIndex(self.chunk_size)

    # ------------------------------------------------------------------
    # Build & streaming
    # ------------------------------------------------------------------
    def begin_frame(self) -> None:
        self._frame_index += 1
        self.rebuilds_this_frame = 0

    def build_static_chunks(self, world: World) -> None:
        """Pre-render static layers (biomes/water/barriers) into chunks."""

        self._world = world
        self.chunks.clear()
        self._dirty_queue.clear()
        self._queued.clear()

        cols = math.ceil(world.width / self.chunk_size)
        rows = math.ceil(world.height / self.chunk_size)

        for cy in range(rows):
            for cx in range(cols):
                rect = self._rect_for_coords(cx, cy)
                if rect is None:
                    continue
                chunk = Chunk(rect=rect)
                chunk.surface = self._build_surface(rect)
                chunk.dirty_static = False
                self.chunks[(cx, cy)] = chunk

    def set_chunk_size(self, chunk_size: int) -> None:
        new_size = max(64, int(chunk_size))
        if new_size == self.chunk_size:
            return
        self.chunk_size = new_size
        self._entity_index = _EntityIndex(new_size)
        if self._world is not None:
            self.build_static_chunks(self._world)

    def ensure_chunks(self, viewport: pygame.Rect, margin: int = 1) -> None:
        """Ensure chunks around the viewport exist (supports lazy streaming)."""

        if self._world is None:
            return

        for coords in self._chunk_coords_for_rect(viewport, margin=margin):
            chunk = self.chunks.get(coords)
            if chunk is None:
                rect = self._rect_for_coords(*coords)
                if rect is None:
                    continue
                chunk = Chunk(rect=rect, dirty_static=True)
                self.chunks[coords] = chunk
            if chunk.surface is None:
                chunk.dirty_static = True
            if chunk.dirty_static:
                self._queue_rebuild(coords)
            chunk.last_used = self._frame_index

    def rebuild_queued(self) -> None:
        if self._world is None:
            return

        built = 0
        while self._dirty_queue and built < self.max_rebuilds_per_frame:
            coords = self._dirty_queue.popleft()
            self._queued.discard(coords)
            chunk = self.chunks.get(coords)
            if chunk is None:
                continue
            if not chunk.dirty_static and chunk.surface is not None:
                continue
            surface = self._build_surface(chunk.rect)
            chunk.surface = surface
            chunk.dirty_static = False
            built += 1
        self.rebuilds_this_frame += built

    def unload_far_chunks(self, viewport: pygame.Rect, max_distance: int = 3) -> None:
        """Unload chunks that are more than ``max_distance`` away (optional)."""

        if not self.streaming_enabled or not self.chunks:
            return

        keep: set[Tuple[int, int]] = set(
            self._chunk_coords_for_rect(viewport, margin=max_distance)
        )
        for key, chunk in list(self.chunks.items()):
            if key in keep:
                continue
            chunk.surface = None

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
                chunk.last_used = self._frame_index
        return visible

    def chunk_coords_for_point(self, x: float, y: float) -> Tuple[int, int]:
        """Map a world coordinate to chunk grid coordinates."""

        return (int(x) // self.chunk_size, int(y) // self.chunk_size)

    @property
    def rebuild_queue_size(self) -> int:
        return len(self._dirty_queue)

    @property
    def frame_index(self) -> int:
        return self._frame_index

    def update_entity_index(
        self,
        *,
        plants: Iterable[object],
        carcasses: Iterable[object],
        lifeforms: Iterable[object],
    ) -> None:
        entities = {
            "plants": plants,
            "carcasses": carcasses,
            "lifeforms": lifeforms,
        }
        self._entity_index.rebuild(
            entities, coords_for_rect=lambda r, margin=0: self._chunk_coords_for_rect(r, margin=margin)
        )

    def entities_in_rect(self, rect: pygame.Rect, margin: int = 0) -> Dict[str, List[object]]:
        return self._entity_index.entities_in_rect(
            rect,
            coords_for_rect=self._chunk_coords_for_rect,
            margin=margin,
        )

    def mark_region_dirty(self, rect: pygame.Rect) -> None:
        for coords in self._chunk_coords_for_rect(rect):
            self._queue_rebuild(coords)
            chunk = self.chunks.get(coords)
            if chunk is not None:
                chunk.dirty_static = True

    def mark_all_dirty(self) -> None:
        for coords in list(self.chunks.keys()):
            self._queue_rebuild(coords)
            self.chunks[coords].dirty_static = True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _chunk_coords_for_rect(
        self, rect: pygame.Rect, *, margin: int = 0
    ) -> Iterable[Tuple[int, int]]:
        if self._world is not None:
            max_cx = max(0, (self._world.width - 1) // self.chunk_size)
            max_cy = max(0, (self._world.height - 1) // self.chunk_size)
        else:
            max_cx = max_cy = math.inf

        start_x = max(0, rect.left // self.chunk_size - margin)
        start_y = max(0, rect.top // self.chunk_size - margin)
        end_x = max(0, (rect.right - 1) // self.chunk_size + margin)
        end_y = max(0, (rect.bottom - 1) // self.chunk_size + margin)

        end_x = min(int(end_x), int(max_cx))
        end_y = min(int(end_y), int(max_cy))

        for cy in range(start_y, end_y + 1):
            for cx in range(start_x, end_x + 1):
                yield (cx, cy)

    def _queue_rebuild(self, coords: Tuple[int, int]) -> None:
        if coords in self._queued:
            return
        self._queued.add(coords)
        self._dirty_queue.append(coords)

    def _rect_for_coords(self, cx: int, cy: int) -> pygame.Rect | None:
        if self._world is None:
            return None
        x = cx * self.chunk_size
        y = cy * self.chunk_size
        width = min(self.chunk_size, self._world.width - x)
        height = min(self.chunk_size, self._world.height - y)
        if width <= 0 or height <= 0:
            return None
        return pygame.Rect(x, y, width, height)

    def _build_surface(self, rect: pygame.Rect) -> pygame.Surface:
        assert self._world is not None
        surface = pygame.Surface(rect.size).convert()
        self._world.draw_static_region(surface, rect)
        return surface


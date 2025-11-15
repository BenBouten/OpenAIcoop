"""Sprite caching helpers for lifeform rendering."""

from __future__ import annotations

import math
from typing import Dict, Tuple

import pygame


class LifeformSpriteCache:
    """Cache rotated sprites per DNA profile and angle bin."""

    def __init__(self, angle_bin_size: int = 15) -> None:
        self._angle_bin_size = max(1, angle_bin_size)
        self._base: Dict[Tuple[int, int, int, Tuple[int, int, int]], pygame.Surface] = {}
        self._rotations: Dict[Tuple[int, int, int, Tuple[int, int, int], int], pygame.Surface] = {}

    def _angle_bin(self, angle: float) -> int:
        normalized = angle % 360.0
        bin_index = int(round(normalized / self._angle_bin_size))
        bins = int(math.ceil(360.0 / self._angle_bin_size))
        return bin_index % max(1, bins)

    def _base_key(self, lifeform) -> Tuple[int, int, int, Tuple[int, int, int]]:
        width = int(round(max(1.0, lifeform.width)))
        height = int(round(max(1.0, lifeform.height)))
        color = tuple(int(c) for c in getattr(lifeform, "body_color", lifeform.color))
        return (str(lifeform.dna_id), width, height, color)

    def _rotation_key(self, lifeform, angle_bin: int) -> Tuple[int, int, int, Tuple[int, int, int], int]:
        base_key = self._base_key(lifeform)
        return base_key + (angle_bin,)

    def get_body(self, lifeform) -> pygame.Surface:
        """Return the rotated body sprite for ``lifeform``."""

        angle_bin = self._angle_bin(getattr(lifeform, "angle", 0.0))
        rotation_key = self._rotation_key(lifeform, angle_bin)
        if rotation_key in self._rotations:
            return self._rotations[rotation_key]

        base_key = self._base_key(lifeform)
        surface = self._base.get(base_key)
        if surface is None:
            width = base_key[1]
            height = base_key[2]
            surface = pygame.Surface((width, height), pygame.SRCALPHA)
            surface.fill(base_key[3])
            self._base[base_key] = surface

        target_angle = angle_bin * self._angle_bin_size
        rotated = pygame.transform.rotate(surface, target_angle)
        self._rotations[rotation_key] = rotated
        return rotated


lifeform_sprite_cache = LifeformSpriteCache()

__all__ = ["lifeform_sprite_cache", "LifeformSpriteCache"]

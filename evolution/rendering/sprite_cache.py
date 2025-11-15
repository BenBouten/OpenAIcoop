"""Sprite caching helpers for lifeform rendering."""

from __future__ import annotations

import math
from typing import Dict, Iterable, Tuple

import pygame

Color = Tuple[int, int, int]
MorphSignature = Tuple[int, int, int, int, int, int, int]
BaseKey = Tuple[str, int, int, Color, MorphSignature]
RotationKey = Tuple[str, int, int, Color, MorphSignature, int]


def _clamp_color(value: int) -> int:
    return max(0, min(255, value))


def _shade_color(color: Color, multiplier: float) -> Color:
    return tuple(_clamp_color(int(channel * multiplier)) for channel in color)


def _evenly_spaced_positions(count: int, start: float, end: float) -> Iterable[float]:
    if count <= 0:
        return ()
    if count == 1:
        return ((start + end) / 2.0,)
    step = (end - start) / float(count - 1)
    return (start + step * index for index in range(count))


class LifeformSpriteCache:
    """Cache rotated sprites per DNA profile and angle bin."""

    def __init__(self, angle_bin_size: int = 15) -> None:
        self._angle_bin_size = max(1, angle_bin_size)
        self._base: Dict[BaseKey, pygame.Surface] = {}
        self._rotations: Dict[RotationKey, pygame.Surface] = {}

    def _angle_bin(self, angle: float) -> int:
        normalized = angle % 360.0
        bin_index = int(round(normalized / self._angle_bin_size))
        bins = int(math.ceil(360.0 / self._angle_bin_size))
        return bin_index % max(1, bins)

    def _morph_signature(self, lifeform) -> MorphSignature:
        morphology = getattr(lifeform, "morphology", None)
        if morphology is None:
            return (0, 0, 0, 0, 0, 0, 0)
        return (
            int(getattr(morphology, "legs", 0)),
            int(getattr(morphology, "fins", 0)),
            int(getattr(morphology, "antennae", 0)),
            int(getattr(morphology, "eyes", 0)),
            int(getattr(morphology, "ears", 0)),
            int(getattr(morphology, "whiskers", 0)),
            int(round(float(getattr(morphology, "pigment", 0.0)) * 1000)),
        )

    def _base_key(self, lifeform) -> BaseKey:
        width = int(round(max(1.0, lifeform.width)))
        height = int(round(max(1.0, lifeform.height)))
        color = tuple(int(c) for c in getattr(lifeform, "body_color", lifeform.color))  # type: ignore[arg-type]
        return (str(lifeform.dna_id), width, height, color, self._morph_signature(lifeform))

    def _rotation_key(self, lifeform, angle_bin: int) -> RotationKey:
        base_key = self._base_key(lifeform)
        return base_key + (angle_bin,)

    def _create_body_surface(self, lifeform, width: int, height: int, color: Color) -> pygame.Surface:
        morphology = getattr(lifeform, "morphology", None)

        legs = int(getattr(morphology, "legs", 0)) if morphology else 0
        fins = int(getattr(morphology, "fins", 0)) if morphology else 0
        antennae = int(getattr(morphology, "antennae", 0)) if morphology else 0
        eyes = int(getattr(morphology, "eyes", 0)) if morphology else 0
        ears = int(getattr(morphology, "ears", 0)) if morphology else 0
        whiskers = int(getattr(morphology, "whiskers", 0)) if morphology else 0

        leg_length = int(max(0.0, height * 0.35)) if legs else 0
        leg_radius = max(2, leg_length // 4) if legs else 0
        fin_length = int(max(0.0, max(width, height) * 0.3)) if fins else 0
        whisker_length = int(max(0.0, width * 0.35)) if whiskers else 0
        antenna_length = int(max(0.0, height * 0.4)) if antennae else 0
        ear_radius = int(max(0.0, min(width, height) * 0.12)) if ears else 0

        base_margin = 4
        margin_top = base_margin + max(antenna_length + 4, ear_radius + 2)
        margin_bottom = base_margin + leg_length + leg_radius + 2
        margin_side = base_margin + max(fin_length, whisker_length)

        sprite_width = width + margin_side * 2
        sprite_height = height + margin_top + margin_bottom

        surface = pygame.Surface((sprite_width, sprite_height), pygame.SRCALPHA)
        body_rect = pygame.Rect(margin_side, margin_top, width, height)

        pygame.draw.ellipse(surface, color, body_rect)

        highlight_rect = body_rect.inflate(-int(width * 0.35), -int(height * 0.35))
        if highlight_rect.width > 0 and highlight_rect.height > 0:
            highlight_color = (*_shade_color(color, 1.2), 80)
            highlight_surface = pygame.Surface(highlight_rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(
                highlight_surface,
                highlight_color,
                pygame.Rect(0, 0, highlight_rect.width, highlight_rect.height),
            )
            surface.blit(highlight_surface, highlight_rect.topleft)

        if fins:
            fin_color = _shade_color(color, 1.25)
            fin_height = max(6, int(height * 0.25))
            fin_positions = list(
                _evenly_spaced_positions(
                    fins,
                    body_rect.top + fin_height,
                    body_rect.bottom - fin_height,
                )
            )
            for index, y in enumerate(fin_positions):
                if index % 2 == 0:
                    points = [
                        (body_rect.left, int(y - fin_height / 2)),
                        (body_rect.left - fin_length, int(y)),
                        (body_rect.left, int(y + fin_height / 2)),
                    ]
                else:
                    points = [
                        (body_rect.right, int(y - fin_height / 2)),
                        (body_rect.right + fin_length, int(y)),
                        (body_rect.right, int(y + fin_height / 2)),
                    ]
                pygame.draw.polygon(surface, fin_color, points)

        if legs:
            leg_color = _shade_color(color, 0.7)
            foot_radius = leg_radius or 2
            for x in _evenly_spaced_positions(
                legs,
                body_rect.left + width * 0.2,
                body_rect.right - width * 0.2,
            ):
                start = (int(x), body_rect.bottom - 1)
                end = (int(x), body_rect.bottom + leg_length)
                pygame.draw.line(surface, leg_color, start, end, 2)
                pygame.draw.circle(surface, leg_color, end, foot_radius)

        if antennae:
            antenna_color = _shade_color(color, 1.35)
            for x in _evenly_spaced_positions(
                antennae,
                body_rect.left + width * 0.25,
                body_rect.right - width * 0.25,
            ):
                start = (int(x), body_rect.top)
                end = (int(x), body_rect.top - antenna_length)
                pygame.draw.line(surface, antenna_color, start, end, 2)
                pygame.draw.circle(surface, antenna_color, end, 3)

        if ears:
            ear_color = _shade_color(color, 0.9)
            ear_y = body_rect.top - max(1, ear_radius // 2)
            for x in _evenly_spaced_positions(
                ears,
                body_rect.left + ear_radius,
                body_rect.right - ear_radius,
            ):
                pygame.draw.circle(surface, ear_color, (int(x), ear_y), max(2, ear_radius))

        if eyes:
            eye_radius = max(2, int(min(width, height) * 0.1))
            eye_y = body_rect.top + int(height * 0.35)
            sclera_color = (240, 240, 240)
            pupil_color = (25, 25, 25)
            for x in _evenly_spaced_positions(
                eyes,
                body_rect.left + eye_radius,
                body_rect.right - eye_radius,
            ):
                center = (int(x), eye_y)
                pygame.draw.circle(surface, sclera_color, center, eye_radius)
                pygame.draw.circle(surface, pupil_color, center, max(1, eye_radius // 2))

        if whiskers:
            whisker_color = _shade_color(color, 0.65)
            pair_count = whiskers // 2
            has_center = whiskers % 2 == 1
            spacing = max(3, int(height * 0.12))
            if pair_count:
                start_y = body_rect.centery - spacing * (pair_count - 1) / 2
                for index in range(pair_count):
                    y = int(start_y + index * spacing)
                    left_start = (body_rect.left, y)
                    left_end = (body_rect.left - whisker_length, y - 1)
                    right_start = (body_rect.right, y)
                    right_end = (body_rect.right + whisker_length, y - 1)
                    pygame.draw.line(surface, whisker_color, left_start, left_end, 1)
                    pygame.draw.line(surface, whisker_color, right_start, right_end, 1)
            if has_center:
                y = int(body_rect.centery)
                center_start = (body_rect.centerx - whisker_length // 2, y)
                center_end = (body_rect.centerx + whisker_length // 2, y)
                pygame.draw.line(surface, whisker_color, center_start, center_end, 1)

        return surface

    def get_body(self, lifeform) -> pygame.Surface:
        """Return the rotated body sprite for ``lifeform``."""

        angle_bin = self._angle_bin(getattr(lifeform, "angle", 0.0))
        rotation_key = self._rotation_key(lifeform, angle_bin)
        if rotation_key in self._rotations:
            return self._rotations[rotation_key]

        base_key = self._base_key(lifeform)
        surface = self._base.get(base_key)
        if surface is None:
            width = int(round(max(1.0, lifeform.width)))
            height = int(round(max(1.0, lifeform.height)))
            color = base_key[3]
            surface = self._create_body_surface(lifeform, width, height, color)
            self._base[base_key] = surface

        target_angle = angle_bin * self._angle_bin_size
        rotated = pygame.transform.rotate(surface, target_angle)
        self._rotations[rotation_key] = rotated
        return rotated


lifeform_sprite_cache = LifeformSpriteCache()

__all__ = ["lifeform_sprite_cache", "LifeformSpriteCache"]

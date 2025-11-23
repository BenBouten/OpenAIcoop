"""Sprite caching helpers for lifeform rendering."""

from __future__ import annotations

import math
from typing import Dict, Iterable, Sequence, Tuple

import pygame
from pygame.math import Vector2

from ..body.body_graph import BodyGraph
from ..config import settings
from .modular_palette import BASE_MODULE_ALPHA, MODULE_RENDER_STYLES, tint_color

Color = Tuple[int, int, int]
MorphSignature = Tuple[int, int, int, int, int, int, int]
ModuleSignature = Tuple[str, ...]
BaseKey = Tuple[str, int, int, Color, MorphSignature, ModuleSignature]
RotationKey = Tuple[str, int, int, Color, MorphSignature, ModuleSignature, int]

CONNECTION_COLOR = (18, 42, 68)

MODULE_RENDER_PROFILES: Dict[str, Dict[str, float]] = {
    "core": {"length_scale": 0.55, "height_scale": 1.05, "max_aspect": 1.35},
    "head": {"length_scale": 0.75, "height_scale": 0.9, "max_aspect": 1.5},
    "sensor": {"length_scale": 0.8, "height_scale": 0.8, "max_aspect": 1.6},
    "propulsion": {"length_scale": 1.3, "height_scale": 0.55},
    "limb": {"length_scale": 1.35, "height_scale": 0.5},
    "default": {"length_scale": 1.0, "height_scale": 0.6},
}


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

    def __init__(self) -> None:
        self._lifeform_cache: Dict[str, pygame.Surface] = {}
        self._faction_cache: Dict[str, pygame.Surface] = {}
        self._rotations: Dict[RotationKey, pygame.Surface] = {}
        self._base: Dict[BaseKey, pygame.Surface] = {}
        self._angle_bin_size = float(getattr(settings, "SPRITE_ANGLE_BIN_DEG", 5.0))
        if self._angle_bin_size <= 0:
            self._angle_bin_size = 5.0

    def get_body(self, lifeform) -> pygame.Surface:
        """Return the rotated body sprite for ``lifeform``."""

        if settings.USE_BODYGRAPH_SIZE:
            # Legacy path: still cache sprites for non-modular creatures.
            cache_key = lifeform.dna_id
            if cache_key not in self._lifeform_cache:
                sprite = self._render_lifeform(lifeform)
                self._lifeform_cache[cache_key] = sprite
            return self._lifeform_cache[cache_key]
        return self._render_lifeform(lifeform)

    def _render_lifeform(self, lifeform) -> pygame.Surface:
        angle_bin = self._angle_bin(getattr(lifeform, "angle", 0.0))
        rotation_key = self._rotation_key(lifeform, angle_bin)
        if rotation_key in self._rotations:
            return self._rotations[rotation_key]

        base_key = self._base_key(lifeform)
        surface = self._base.get(base_key)
        if surface is None:
            width = int(round(max(1.0, lifeform.width)))
            height = int(round(max(1.0, lifeform.height)))
            if settings.USE_BODYGRAPH_SIZE:
                width = int(round(max(1.0, self._sprite_width(lifeform))))
                height = int(round(max(1.0, self._sprite_height(lifeform))))
            color = base_key[3]
            surface = self._create_body_surface(lifeform, width, height, color)
            surface = surface.convert_alpha()
            self._base[base_key] = surface

        target_angle = angle_bin * self._angle_bin_size
        rotated = pygame.transform.rotate(surface, target_angle).convert_alpha()
        self._rotations[rotation_key] = rotated
        return rotated

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

    def _module_signature(self, lifeform) -> ModuleSignature:
        names: Sequence[str] = getattr(lifeform, "body_module_names", ())
        if names:
            return tuple(names)
        graph: BodyGraph | None = getattr(lifeform, "body_graph", None)
        if graph is None:
            return tuple()
        collected: list[str] = []
        for module in graph.iter_modules():
            key = getattr(module, "key", None)
            if not key:
                key = getattr(module, "name", type(module).__name__)
            collected.append(str(key))
        return tuple(collected)

    def _base_key(self, lifeform) -> BaseKey:
        width = int(round(max(1.0, self._sprite_width(lifeform))))
        height = int(round(max(1.0, self._sprite_height(lifeform))))
        color = tuple(int(c) for c in getattr(lifeform, "body_color", lifeform.color))  # type: ignore[arg-type]
        return (
            str(lifeform.dna_id),
            width,
            height,
            color,
            self._morph_signature(lifeform),
            self._module_signature(lifeform),
        )

    def _rotation_key(self, lifeform, angle_bin: int) -> RotationKey:
        base_key = self._base_key(lifeform)
        return base_key + (angle_bin,)

    def _create_body_surface(self, lifeform, width: int, height: int, color: Color) -> pygame.Surface:
        graph: BodyGraph | None = getattr(lifeform, "body_graph", None)
        if graph is not None and getattr(graph, "nodes", None):
            modular_surface = self._create_modular_surface(lifeform, graph, width, height, color)
            if modular_surface is not None:
                return modular_surface
        return self._create_legacy_surface(lifeform, width, height, color)

    def _create_legacy_surface(self, lifeform, width: int, height: int, color: Color) -> pygame.Surface:
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

    def _create_modular_surface(
        self,
        lifeform,
        graph: BodyGraph,
        width: int,
        height: int,
        base_color: Color,
    ) -> pygame.Surface | None:
        layout = self._layout_body_graph(graph)
        if not layout:
            return None
        margin = 12
        sprite_width = max(20, width + margin * 2)
        sprite_height = max(20, height + margin * 2)
        positions = self._project_layout(layout, sprite_width, sprite_height, margin)
        surface = pygame.Surface((sprite_width, sprite_height), pygame.SRCALPHA)
        self._draw_connections(surface, graph, positions)
        module_scale = self._module_scale(max(width, height))
        for node_id, node in graph.nodes.items():
            if node_id not in positions:
                continue
            module_surface = self._build_module_surface(node.module, base_color, module_scale)
            rect = module_surface.get_rect()
            rect.center = (int(positions[node_id].x), int(positions[node_id].y))
            angle = graph.node_transform(node_id)[2]
            rotated = pygame.transform.rotate(module_surface, angle)
            rect = rotated.get_rect(center=rect.center)
            surface.blit(rotated, rect)
        return surface

    def _draw_connections(
        self,
        surface: pygame.Surface,
        graph: BodyGraph,
        positions: Dict[str, Vector2],
    ) -> None:
        if not positions:
            return
        connector = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for node_id, node in graph.nodes.items():
            parent_id = node.parent
            if not parent_id or parent_id not in positions or node_id not in positions:
                continue
            start = positions[parent_id]
            end = positions[node_id]
            width = 5 if getattr(node.module, "module_type", "") == "core" else 3
            pygame.draw.line(
                connector,
                CONNECTION_COLOR,
                (int(start.x), int(start.y)),
                (int(end.x), int(end.y)),
                width,
            )
            pygame.draw.circle(connector, CONNECTION_COLOR, (int(end.x), int(end.y)), max(2, width // 2))
        connector.set_alpha(190)
        surface.blit(connector, (0, 0))

    def _layout_body_graph(self, graph: BodyGraph) -> Dict[str, Vector2]:
        layout: Dict[str, Vector2] = {}
        for node_id in graph.nodes:
            x, y, _ = graph.node_transform(node_id)
            layout[node_id] = Vector2(x, y)
        if not layout:
            return layout
        min_x = min(pos.x for pos in layout.values())
        min_y = min(pos.y for pos in layout.values())
        for node_id, pos in layout.items():
            layout[node_id] = Vector2(pos.x - min_x, pos.y - min_y)
        return layout

    def _project_layout(
        self,
        layout: Dict[str, Vector2],
        sprite_width: int,
        sprite_height: int,
        margin: int,
    ) -> Dict[str, Vector2]:
        if not layout:
            return {}
        xs = [pos.x for pos in layout.values()]
        ys = [pos.y for pos in layout.values()]
        max_x = max(xs)
        max_y = max(ys)
        draw_width = max(1.0, sprite_width - margin * 2)
        draw_height = max(1.0, sprite_height - margin * 2)
        positions: Dict[str, Vector2] = {}
        for node_id, offset in layout.items():
            norm_x = offset.x / max(1e-3, max_x)
            norm_y = offset.y / max(1e-3, max_y)
            positions[node_id] = Vector2(
                margin + norm_x * draw_width,
                margin + norm_y * draw_height,
            )
        return positions

    def _module_scale(self, body_span: float) -> float:
        return max(settings.MODULE_SPRITE_MIN_PX, body_span * settings.MODULE_SPRITE_SCALE)

    def _build_module_surface(self, module, base_color: Color, scale: float) -> pygame.Surface:
        module_type = getattr(module, "module_type", "default") or "default"
        color, alpha = self._module_visuals(base_color, module_type)
        size = getattr(module, "size", (1.0, 1.0, 1.0))
        profile = MODULE_RENDER_PROFILES.get(module_type, MODULE_RENDER_PROFILES["default"])
        length_scale = profile.get("length_scale", 1.0)
        height_scale = profile.get("height_scale", 0.6)
        length = max(
            int(settings.MODULE_SPRITE_MIN_LENGTH),
            int(float(size[2]) * scale * length_scale),
        )
        height = max(
            int(settings.MODULE_SPRITE_MIN_HEIGHT),
            int(float(size[1]) * scale * height_scale),
        )
        max_aspect = profile.get("max_aspect")
        if max_aspect:
            max_length = max(int(settings.MODULE_SPRITE_MIN_LENGTH), int(height * max_aspect))
            length = min(length, max_length)
        surface = pygame.Surface((length, height), pygame.SRCALPHA)
        ellipse_rect = pygame.Rect(0, 0, length, height)
        pygame.draw.ellipse(surface, (*color, alpha), ellipse_rect)
        pygame.draw.ellipse(surface, (25, 40, 60, max(120, alpha - 40)), ellipse_rect, 2)
        if module_type == "propulsion":
            flame_rect = ellipse_rect.inflate(-int(length * 0.35), -int(height * 0.25))
            flame_rect.left = ellipse_rect.left + 2
            pygame.draw.ellipse(
                surface,
                (255, 200, 150, max(120, alpha - 30)),
                flame_rect,
            )
        elif module_type == "head":
            eye_rect = pygame.Rect(0, 0, max(4, length // 5), max(4, height // 3))
            eye_rect.center = (
                ellipse_rect.centerx + ellipse_rect.width // 5,
                ellipse_rect.centery - ellipse_rect.height // 4,
            )
            pygame.draw.ellipse(surface, (20, 30, 60, 220), eye_rect)
        elif module_type == "sensor":
            ping_rect = pygame.Rect(0, 0, max(3, length // 4), max(3, height // 2))
            ping_rect.center = (
                ellipse_rect.centerx + ellipse_rect.width // 3,
                ellipse_rect.centery,
            )
            pygame.draw.ellipse(surface, (240, 255, 255, 140), ping_rect, 2)
        elif module_type == "tentacle":
            spine = [
                (ellipse_rect.left + int(length * 0.1), ellipse_rect.centery - height // 6),
                (ellipse_rect.centerx, ellipse_rect.bottom - height // 5),
                (ellipse_rect.right - int(length * 0.15), ellipse_rect.bottom - 2),
            ]
            pygame.draw.lines(
                surface,
                (25, 60, 50, max(100, alpha - 60)),
                False,
                spine,
                3,
            )
            tip_radius = max(2, height // 6)
            pygame.draw.circle(
                surface,
                (255, 210, 160, max(140, alpha - 40)),
                (spine[-1][0], spine[-1][1]),
                tip_radius,
            )
        elif module_type == "bell_core":
            crown_rect = ellipse_rect.inflate(-int(length * 0.2), -int(height * 0.3))
            crown_rect.centery = ellipse_rect.centery - max(2, height // 10)
            pygame.draw.ellipse(surface, (255, 255, 255, max(100, alpha - 80)), crown_rect)
            ring_rect = pygame.Rect(0, 0, max(8, length // 2), max(6, height // 3))
            ring_rect.center = (
                ellipse_rect.centerx,
                ellipse_rect.bottom - ring_rect.height // 2,
            )
            pygame.draw.ellipse(surface, (35, 55, 90, max(140, alpha - 50)), ring_rect, 2)
        return surface

    def _module_visuals(self, base_color: Color, module_type: str) -> Tuple[Color, int]:
        style = MODULE_RENDER_STYLES.get(module_type, MODULE_RENDER_STYLES["default"])
        tint = style.get("tint", (1.0, 1.0, 1.0))
        tinted = tint_color(base_color, tint)  # type: ignore[arg-type]
        alpha_offset = int(style.get("alpha_offset", 0))
        alpha = max(60, min(255, BASE_MODULE_ALPHA + alpha_offset))
        return tinted, alpha

    def _sprite_width(self, lifeform) -> float:
        if settings.USE_BODYGRAPH_SIZE:
            geom = getattr(lifeform, "profile_geometry", {}) or getattr(lifeform, "body_geometry", {})
            width = float(geom.get("width", lifeform.width))
            return width * settings.BODY_PIXEL_SCALE
        return float(lifeform.width)

    def _sprite_height(self, lifeform) -> float:
        if settings.USE_BODYGRAPH_SIZE:
            geom = getattr(lifeform, "profile_geometry", {}) or getattr(lifeform, "body_geometry", {})
            height = float(geom.get("height", lifeform.height))
            return height * settings.BODY_PIXEL_SCALE
        return float(lifeform.height)


lifeform_sprite_cache = LifeformSpriteCache()

__all__ = ["lifeform_sprite_cache", "LifeformSpriteCache"]

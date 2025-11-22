"""Shared helpers for rendering BodyGraph modules with attachment-aware transforms."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

import pygame
from pygame.math import Vector2

from ..body.body_graph import BodyGraph
from ..body.modules import BodyModule
from .modular_palette import BASE_MODULE_ALPHA, MODULE_RENDER_STYLES, tint_color

Color = Tuple[int, int, int]
PARENT_CONTACT_COLOR = (255, 210, 120)
CHILD_CONTACT_COLOR = (120, 230, 255)
FORWARD_AXIS_COLOR = (120, 255, 180)
LATERAL_AXIS_COLOR = (255, 120, 210)

ENABLE_ALIGNMENT_LOG = False


def _rotate(vec: Vector2, angle_degrees: float) -> Vector2:
    radians = math.radians(angle_degrees)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    return Vector2(vec.x * cos_a - vec.y * sin_a, vec.x * sin_a + vec.y * cos_a)


def _module_radius(module: BodyModule) -> float:
    width, height, _ = module.size
    length = max(0.01, float(module.size[2]))
    return length / 2.0


def _unit(angle_degrees: float) -> Vector2:
    radians = math.radians(angle_degrees)
    return Vector2(math.cos(radians), math.sin(radians))


def _ellipse_distance(direction_local: Vector2, half_length: float, half_cross: float) -> float:
    if direction_local.length_squared() < 1e-9:
        return min(half_length, half_cross)
    d = direction_local.normalize()
    denom = math.sqrt((d.x / max(half_length, 1e-6)) ** 2 + (d.y / max(half_cross, 1e-6)) ** 2)
    if denom < 1e-6:
        return min(half_length, half_cross)
    return 1.0 / denom


@dataclass
class ModulePose:
    center: Vector2
    angle: float


@dataclass
class AnimatedModule:
    node_id: str
    module: BodyModule
    parent_id: str | None
    attachment_point: str | None
    rest_pose: ModulePose
    current_pose: ModulePose
    relative_angle: float = 0.0
    angle_offset: float = 0.0
    angular_velocity: float = 0.0
    joint_position: Vector2 = field(default_factory=Vector2)
    anchor_offset_local: Vector2 = field(default_factory=Vector2)
    attachment_angle: float = 0.0
    clearance: float = 0.0
    contact_markers: list[tuple[Vector2, bool]] = field(default_factory=list)
    half_length: float = 0.0
    half_cross: float = 0.0
    natural_orientation: float = 0.0
    outline_local: List[Vector2] = field(default_factory=list)
    outline_world: List[Vector2] = field(default_factory=list)

    @property
    def mass(self) -> float:
        return float(self.module.stats.mass)

    @property
    def drag_area(self) -> float:
        width, height, length = self.module.size
        return max(0.2, width * length * 0.5 + height * length * 0.5)


@dataclass
class ModularRendererState:
    graph: BodyGraph
    torso_color: Color
    poses: Dict[str, AnimatedModule] = field(default_factory=dict)
    dirty: bool = True

    def refresh(self) -> None:
        if not self.dirty:
            return
        self.dirty = False
        for node_id, node in self.graph.nodes.items():
            if node_id not in self.poses:
                x, y, angle = self.graph.node_transform(node_id)
                rest = ModulePose(center=Vector2(x, y), angle=angle)
                self.poses[node_id] = AnimatedModule(
                    node_id=node_id,
                    module=node.module,
                    parent_id=node.parent,
                    attachment_point=node.attachment_point,
                    rest_pose=rest,
                    current_pose=ModulePose(center=Vector2(x, y), angle=angle),
                    half_length=max(0.05, float(node.module.size[2]) / 2.0),
                    half_cross=max(0.05, float(max(node.module.size[0], node.module.size[1])) / 2.0),
                    natural_orientation=float(getattr(node.module, "natural_orientation", 0.0)),
                    outline_local=self._generate_outline(node.module),
                )

        stale = [node_id for node_id in self.poses if node_id not in self.graph.nodes]
        for node_id in stale:
            self.poses.pop(node_id, None)

        self._initialise_relative_angles()
        self._initialise_joint_metadata()

    def _initialise_relative_angles(self) -> None:
        for node_id, animated in self.poses.items():
            parent_id = animated.parent_id
            if parent_id is None or parent_id not in self.poses or not animated.attachment_point:
                animated.relative_angle = 0.0
                continue
            parent = self.poses[parent_id]
            point = parent.module.get_attachment_point(animated.attachment_point)
            parent_direction = parent.rest_pose.angle + point.angle
            animated.relative_angle = animated.rest_pose.angle - parent_direction

    def _initialise_joint_metadata(self) -> None:
        for node_id, animated in self.poses.items():
            parent_id = animated.parent_id
            if parent_id is None or parent_id not in self.poses or not animated.attachment_point:
                animated.anchor_offset_local = Vector2()
                animated.attachment_angle = 0.0
                animated.clearance = 0.0
                continue
            parent = self.poses[parent_id]
            point = parent.module.get_attachment_point(animated.attachment_point)
            parent_angle = parent.rest_pose.angle
            offset = Vector2(point.offset)
            if point.relative:
                offset.x *= parent.module.size[2]
                offset.y *= parent.module.size[1]
            anchor_world = parent.rest_pose.center + _rotate(offset, parent_angle)
            anchor_offset_world = anchor_world - parent.rest_pose.center
            animated.anchor_offset_local = _rotate(anchor_offset_world, -parent_angle)
            animated.attachment_angle = point.angle
            animated.clearance = float(getattr(point, "clearance", 0.0))

    def _generate_outline(self, module: BodyModule, segments: int = 32) -> List[Vector2]:
        if getattr(module, "module_type", "") == "limb":
            half_span = max(0.05, float(max(module.size[0], module.size[1])) / 2.0)
            length = max(0.1, float(module.size[2]))
            trailing = -length * 0.25
            leading = length * 0.65
            outline = [
                Vector2(trailing, -half_span * 0.2),
                Vector2(0.0, -half_span),
                Vector2(leading, 0.0),
                Vector2(0.0, half_span),
                Vector2(trailing, half_span * 0.2),
            ]
            return outline
        half_length = max(0.05, float(module.size[2]) / 2.0)
        half_cross = max(0.05, float(max(module.size[0], module.size[1])) / 2.0)
        outline: List[Vector2] = []
        for idx in range(segments):
            angle = (idx / segments) * 360.0
            direction = _unit(angle)
            radius = _ellipse_distance(direction, half_length, half_cross)
            outline.append(direction * radius)
        for point in module.attachment_points.values():
            offset = Vector2(point.offset)
            if point.relative:
                offset.x *= module.size[2]
                offset.y *= module.size[1]
            direction = _unit(point.angle)
            joint_radius = _ellipse_distance(direction, half_length, half_cross)
            joint_point = offset + direction * joint_radius
            if not outline:
                outline.append(joint_point)
                continue
            target_angle = math.degrees(math.atan2(joint_point.y, joint_point.x)) % 360.0
            closest_idx = min(
                range(len(outline)),
                key=lambda i: abs(((math.degrees(math.atan2(outline[i].y, outline[i].x)) % 360.0) - target_angle + 540.0) % 360.0 - 180.0),
            )
            outline[closest_idx] = joint_point
        return outline

    def rebuild_world_poses(self) -> None:
        if self.dirty:
            self.refresh()
        root = self.graph.root_id
        root_pose = self.poses[root]
        root_pose.current_pose.center = root_pose.rest_pose.center.copy()
        root_pose.current_pose.angle = root_pose.rest_pose.angle + root_pose.angle_offset
        root_pose.joint_position = root_pose.current_pose.center.copy()
        for animated in self.poses.values():
            animated.contact_markers.clear()
            animated.outline_world = [
                _rotate(vertex, animated.current_pose.angle) + animated.current_pose.center
                for vertex in animated.outline_local
            ]
        self._solve_children(root)

    def _solve_children(self, parent_id: str) -> None:
        parent = self.poses[parent_id]
        for child_id in self.graph.nodes[parent_id].children:
            child = self.poses[child_id]
            parent_angle = parent.current_pose.angle
            anchor_base = parent.current_pose.center + _rotate(child.anchor_offset_local, parent_angle)
            direction_angle = parent_angle + child.attachment_angle
            direction = _unit(direction_angle)
            parent_dir_local = _rotate(direction, -parent_angle)
            parent_target = _ellipse_distance(parent_dir_local, parent.half_length, parent.half_cross)
            base_offset = (anchor_base - parent.current_pose.center).dot(direction)
            anchor_world = anchor_base + direction * (parent_target - base_offset)
            self._log_alignment_error(parent, anchor_world, parent_target, "parent")
            child_angle = direction_angle + child.relative_angle + child.angle_offset
            child_dir_local = _rotate(-direction, -(child_angle + child.natural_orientation))
            child_distance = _ellipse_distance(child_dir_local, child.half_length, child.half_cross)
            child_center = anchor_world + direction * (child.clearance + child_distance)
            self._log_alignment_error(child, child_center - direction * child_distance, child_distance, "child")
            child.current_pose.center = child_center
            child.current_pose.angle = child_angle
            contact_point = anchor_world
            parent.contact_markers.append((contact_point, True))
            child.contact_markers.append((contact_point, False))
            child.joint_position = contact_point
            self._solve_children(child_id)

    def _log_alignment_error(
        self,
        module: AnimatedModule,
        target_point: Vector2,
        ideal_distance: float,
        label: str,
    ) -> None:
        actual = (target_point - module.current_pose.center).length()
        if ENABLE_ALIGNMENT_LOG and abs(actual - ideal_distance) > 1.5:
            print(
                f"[Renderer] Alignment drift on {module.node_id} ({label}): expected {ideal_distance:.2f}, got {actual:.2f}"
            )

    def iter_poses(self) -> Iterable[AnimatedModule]:
        for node_id in self.graph.nodes:
            yield self.poses[node_id]


class BodyGraphRenderer:
    """Draw body modules using their attachment-aware transforms."""

    def __init__(
        self,
        surface: pygame.Surface,
        torso_color: Color,
        position_scale: float = 36.0,
    ) -> None:
        self.surface = surface
        self.torso_color = torso_color
        self.position_scale = position_scale
        self.show_debug = True

    def set_debug_overlays(self, enabled: bool) -> None:
        self.show_debug = enabled

    def draw(self, state: ModularRendererState, offset: Vector2) -> None:
        skin_points = self._collect_outline_points(state, offset)
        if len(skin_points) >= 3:
            hull = self._convex_hull(skin_points)
            skin_color = tuple(int(c * 0.9) for c in self.torso_color)
            pygame.draw.polygon(self.surface, skin_color, hull, width=0)
            pygame.draw.polygon(self.surface, (15, 30, 45), hull, width=2)
        parent_lookup = state.poses
        for animated in state.iter_poses():
            if animated.parent_id:
                parent = parent_lookup.get(animated.parent_id)
                if parent:
                    self._draw_bridge(parent, animated, offset)
        for animated in state.iter_poses():
            self._draw_module(animated, offset)

    def _collect_outline_points(self, state: ModularRendererState, offset: Vector2) -> List[Tuple[int, int]]:
        points: List[Tuple[int, int]] = []
        for animated in state.iter_poses():
            if self._skin_includes_module(animated):
                for vertex in animated.outline_world:
                    screen_point = offset + vertex * self.position_scale
                    points.append((int(screen_point.x), int(screen_point.y)))
            joint_point = offset + animated.joint_position * self.position_scale
            points.append((int(joint_point.x), int(joint_point.y)))
        return points

    def _skin_includes_module(self, animated: AnimatedModule) -> bool:
        module_type = getattr(animated.module, "module_type", "")
        return module_type not in {"limb"}

    def _convex_hull(self, points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        pts = sorted(set(points))
        if len(pts) <= 2:
            return pts

        def cross(o: Tuple[int, int], a: Tuple[int, int], b: Tuple[int, int]) -> int:
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: List[Tuple[int, int]] = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper: List[Tuple[int, int]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        return lower[:-1] + upper[:-1]

    def _module_visuals(self, module_type: str) -> tuple[Color, int]:
        style = MODULE_RENDER_STYLES.get(module_type, MODULE_RENDER_STYLES["default"])
        tint = style.get("tint", (1.0, 1.0, 1.0))
        tinted = tint_color(self.torso_color, tint)
        alpha_offset = int(style.get("alpha_offset", 0))
        alpha = max(60, min(255, BASE_MODULE_ALPHA + alpha_offset))
        return tinted, alpha

    def _draw_module(self, animated: AnimatedModule, offset: Vector2) -> None:
        module = animated.module
        module_type = getattr(module, "module_type", "default")
        color, alpha = self._module_visuals(module_type)
        polygon_points = [
            (offset + vertex * self.position_scale) for vertex in animated.outline_world
        ]
        int_points = [(int(point.x), int(point.y)) for point in polygon_points]
        if len(int_points) >= 3:
            fill_color = (*color, alpha)
            pygame.draw.polygon(self.surface, fill_color, int_points)
            pygame.draw.polygon(self.surface, (20, 35, 50), int_points, 1)

        joint_center = offset + animated.joint_position * self.position_scale
        joint_color = (120, 190, 240) if animated.parent_id else (220, 230, 240)
        pygame.draw.circle(self.surface, joint_color, (int(joint_center.x), int(joint_center.y)), 4, 2)
        if self.show_debug:
            for point, is_parent in animated.contact_markers:
                self._draw_contact_marker(offset + point * self.position_scale, is_parent)
            self._draw_axes(animated, offset)

    def _draw_contact_marker(self, position: Vector2, is_parent: bool) -> None:
        color = PARENT_CONTACT_COLOR if is_parent else CHILD_CONTACT_COLOR
        x, y = int(position.x), int(position.y)
        pygame.draw.line(self.surface, color, (x - 4, y), (x + 4, y), 2)
        pygame.draw.line(self.surface, color, (x, y - 4), (x, y + 4), 2)

    def _draw_axes(self, animated: AnimatedModule, offset: Vector2) -> None:
        if not self.show_debug:
            return
        center = offset + animated.current_pose.center * self.position_scale
        forward = _unit(animated.current_pose.angle)
        lateral = _unit(animated.current_pose.angle + 90.0)
        forward_len = animated.half_length * self.position_scale
        lateral_len = animated.half_cross * self.position_scale
        pygame.draw.line(
            self.surface,
            FORWARD_AXIS_COLOR,
            (int(center.x), int(center.y)),
            (int(center.x + forward.x * forward_len), int(center.y + forward.y * forward_len)),
            2,
        )
        pygame.draw.line(
            self.surface,
            LATERAL_AXIS_COLOR,
            (int(center.x), int(center.y)),
            (int(center.x + lateral.x * lateral_len), int(center.y + lateral.y * lateral_len)),
            2,
        )

    def _draw_bridge(self, parent: AnimatedModule, child: AnimatedModule, offset: Vector2) -> None:
        direction = (child.joint_position - parent.joint_position)
        if direction.length_squared() < 1e-6:
            return
        direction = direction.normalize()
        tangent = Vector2(-direction.y, direction.x)
        parent_width = parent.half_cross * self.position_scale * 0.6
        child_width = child.half_cross * self.position_scale * 0.6
        parent_center = offset + parent.joint_position * self.position_scale
        child_center = offset + child.joint_position * self.position_scale
        bridge_points = [
            (parent_center - tangent * parent_width),
            (parent_center + tangent * parent_width),
            (child_center + tangent * child_width),
            (child_center - tangent * child_width),
        ]
        color_parent, _ = self._module_visuals(parent.module.module_type)
        color_child, _ = self._module_visuals(child.module.module_type)
        blend_color = tuple(int((p + c) / 2) for p, c in zip(color_parent, color_child))
        pygame.draw.polygon(self.surface, blend_color, [(int(pt.x), int(pt.y)) for pt in bridge_points])


__all__ = ["ModularRendererState", "BodyGraphRenderer", "AnimatedModule"]

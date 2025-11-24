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
    thrust_factor: float = 0.0  # New field to store animation intensity
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

    def _generate_outline(self, module: BodyModule, segments: int = 7) -> List[Vector2]:
        if getattr(module, "module_type", "") == "limb":
            half_span = max(0.05, float(max(module.size[0], module.size[1])) / 2.0)
            length = max(0.1, float(module.size[2]))
            trailing = -length * 0.25
            leading = length * 0.65
            # Make limbs more angular/diamond shaped
            outline = [
                Vector2(trailing, 0.0),
                Vector2(0.0, -half_span),
                Vector2(leading, 0.0),
                Vector2(0.0, half_span),
            ]
            return outline
        
        # Low poly circle (heptagon/octagon)
        half_length = max(0.05, float(module.size[2]) / 2.0)
        half_cross = max(0.05, float(max(module.size[0], module.size[1])) / 2.0)
        outline: List[Vector2] = []
        
        # Rotate the polygon slightly so it doesn't look too aligned
        offset_angle = 15.0 
        
        for idx in range(segments):
            angle = (idx / segments) * 360.0 + offset_angle
            direction = _unit(angle)
            radius = _ellipse_distance(direction, half_length, half_cross)
            outline.append(direction * radius)
            
        # Snap attachment points to nearest vertex to maintain low-poly look
        # Or just let them float? Let's keep the original logic but maybe relax it
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
            
            # Find closest vertex and replace it, or insert?
            # Replacing maintains the vertex count (low poly)
            target_angle = math.degrees(math.atan2(joint_point.y, joint_point.x)) % 360.0
            closest_idx = min(
                range(len(outline)),
                key=lambda i: abs(((math.degrees(math.atan2(outline[i].y, outline[i].x)) % 360.0) - target_angle + 540.0) % 360.0 - 180.0),
            )
            outline[closest_idx] = joint_point
        return outline

    def rebuild_world_poses(self, angular_velocity: float = 0.0, thrust_output: float = 0.0) -> None:
        if self.dirty:
            self.refresh()
        
        # Apply procedural animation to joints
        self._update_animation(angular_velocity, thrust_output)

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

    def _update_animation(self, angular_velocity: float, thrust_output: float) -> None:
        time_ms = pygame.time.get_ticks()
        
        # Base animation parameters
        # Idle movement: slow, low amplitude
        # Thrust movement: fast, high amplitude
        
        # Normalize thrust (assuming max thrust ~20-50 per module, total maybe 100?)
        # Let's just use a sigmoid or clamp.
        thrust_factor = min(1.0, abs(thrust_output) / 20.0)
        
        base_freq = 0.0015 + (0.010 * thrust_factor)
        base_amp = 1.5 + (18.0 * thrust_factor)
        
        visited = set()
        queue = [(self.graph.root_id, 0, 0.0)] # id, depth, parent_phase
        
        while queue:
            node_id, depth, parent_phase = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            
            animated = self.poses[node_id]
            module_type = getattr(animated.module, "module_type", "")
            
            # Animation Parameters
            wave_amp = 0.0
            spatial_freq = 0.4
            
            if module_type in ("tentacle", "propulsion"):
                # Snake/Tentacle movement

                is_chain = False
                if animated.parent_id:
                    parent_mod = self.poses[animated.parent_id].module
                    if getattr(parent_mod, "module_type", "") == module_type:
                        is_chain = True

                if is_chain or module_type in ("tentacle", "propulsion"):
                    # Scale amplitude by thrust; idle motion is subtle and elongated
                    wave_amp = base_amp
                    if module_type == "propulsion":
                        wave_amp *= 0.7 # Tails slightly stiffer

                    # Add turn leaning
                    lag = -angular_velocity * 5.0

                    # Sine wave driven by thrust; deeper segments trail behind
                    phase = time_ms * base_freq + thrust_output * 0.015 - depth * spatial_freq
                    wave = math.sin(phase) * wave_amp

                    # Apply to angle_offset
                    animated.angle_offset = wave + lag
                    animated.thrust_factor = thrust_factor
            elif module_type not in {"limb"}:
                # Flex the core/body slightly when thrusting so the hull undulates
                # alongside fins and tentacles.
                body_phase = time_ms * (base_freq * 0.6) - depth * 0.2
                body_amp = base_amp * 0.25 * thrust_factor + 0.4
                animated.angle_offset = math.sin(body_phase) * body_amp
            
            # Propagate to children
            if node_id in self.graph.nodes:
                for child_id in self.graph.nodes[node_id].children:
                    queue.append((child_id, depth + 1, 0.0))

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
            
            # Include angle_offset in the child's rotation
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
            # print(
            #     f"[Renderer] Alignment drift on {module.node_id} ({label}): expected {ideal_distance:.2f}, got {actual:.2f}"
            # )
            pass

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
            # Draw skin with low alpha or wireframe?
            # Let's keep it solid but maybe lighter
            pygame.draw.polygon(self.surface, skin_color, hull, width=0)
            # Distinct outline for the skin
            pygame.draw.polygon(self.surface, (200, 220, 230), hull, width=2)
            
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
            include_module = self._skin_includes_module(animated)
            if include_module:
                for vertex in animated.outline_world:
                    screen_point = offset + vertex * self.position_scale
                    points.append((int(screen_point.x), int(screen_point.y)))
                joint_point = offset + animated.joint_position * self.position_scale
                points.append((int(joint_point.x), int(joint_point.y)))
        return points

    def _skin_includes_module(self, animated: AnimatedModule) -> bool:
        module_type = getattr(animated.module, "module_type", "")
        # Exclude limbs, tentacles, and propulsion (fins/tails) from the main skin outline
        return module_type not in {"limb", "tentacle", "propulsion"}

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
        
        if module_type == "eye":
            self._draw_eye(animated, offset)
            return
        elif module_type == "mouth":
            self._draw_mouth(animated, offset)
            return
        elif module_type == "tentacle":
            self._draw_tentacle(animated, offset, color, alpha)
            return

        polygon_points = [
            (offset + vertex * self.position_scale) for vertex in animated.outline_world
        ]
        int_points = [(int(point.x), int(point.y)) for point in polygon_points]
        
        if len(int_points) >= 3:
            fill_color = (*color, alpha)
            pygame.draw.polygon(self.surface, fill_color, int_points)
            
            # Low Poly Aesthetic: Distinct outlines
            outline_color = (220, 240, 255) # Bright/Whitish outline
            pygame.draw.polygon(self.surface, outline_color, int_points, 2)
            
            # Triangulation / Internal lines
            # Draw lines from center to each vertex to create facets
            center = offset + animated.current_pose.center * self.position_scale
            center_pt = (int(center.x), int(center.y))
            
            # Use a slightly lighter/darker color for internal lines
            internal_color = (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40))
            
            for pt in int_points:
                pygame.draw.line(self.surface, internal_color, center_pt, pt, 1)

    def _draw_tentacle(self, animated: AnimatedModule, offset: Vector2, color: Color, alpha: int) -> None:
        """Render a multi-segment tentacle with thrust effects."""
        module = animated.module
        
        # Geometry setup
        start_pos = offset + animated.current_pose.center * self.position_scale
        base_angle = animated.current_pose.angle
        
        # Dimensions
        length = module.size[2] * self.position_scale
        base_width = max(module.size[0], module.size[1]) * self.position_scale * 0.5
        
        # Animation parameters
        time_ms = pygame.time.get_ticks()
        phase_offset = (id(animated) % 100) * 0.1
        
        # Movement characteristics
        # Scale internal animation by thrust factor
        thrust_factor = getattr(animated, "thrust_factor", 0.0)
        
        wave_speed = 0.002 + (0.008 * thrust_factor)
        wave_freq = 0.8  
        wave_amp = 2.0 + (5.0 * thrust_factor)   # Scale amplitude with thrust
        
        num_segments = max(6, int(length / 8))
        segment_len = length / num_segments
        
        spine_points: List[Vector2] = []
        current_pos = start_pos
        current_angle = base_angle
        
        # Calculate spine
        for i in range(num_segments + 1):
            t = i / num_segments  # 0.0 to 1.0
            
            # Envelope: 0 at base, increasing towards tip
            # This allows the segment to flex slightly internally
            envelope = math.sin(t * math.pi) * 0.5
            
            wave_val = math.sin(time_ms * wave_speed + i * wave_freq + phase_offset)
            angle_offset = wave_val * wave_amp * envelope * 0.2 
            
            current_angle += angle_offset
            
            spine_points.append(current_pos)
            
            # Advance
            direction = _unit(current_angle)
            current_pos += direction * segment_len
            
            # Thrust Effects (Bubbles/Flow)
            velocity_factor = math.cos(time_ms * wave_speed + i * wave_freq + phase_offset)
            
            # Draw effects only if thrust is significant
            if thrust_factor > 0.2 and t > 0.3 and abs(velocity_factor) > 0.65:
                move_dir = _unit(current_angle + 90) * (1.0 if velocity_factor > 0 else -1.0)
                effect_pos = current_pos - move_dir * (base_width * 0.8)
                
                effect_alpha = int(abs(velocity_factor) * 180 * t * thrust_factor)
                if effect_alpha > 30:
                    bubble_radius = max(1, int(3 * t))
                    bubble_color = (200, 240, 255)
                    pygame.draw.circle(self.surface, bubble_color, (int(effect_pos.x), int(effect_pos.y)), bubble_radius)
                    
                    if abs(velocity_factor) > 0.85:
                         trail_end = effect_pos - direction * (8 * t * thrust_factor)
                         pygame.draw.line(self.surface, (180, 230, 250), (int(effect_pos.x), int(effect_pos.y)), (int(trail_end.x), int(trail_end.y)), 1)

        # Build Polygon Strip
        left_verts: List[Vector2] = []
        right_verts: List[Vector2] = []
        
        for i, pt in enumerate(spine_points):
            t = i / num_segments
            # Tapering
            width = base_width * (1.0 - t * 0.4)
            
            # Calculate normal
            if i < len(spine_points) - 1:
                diff = spine_points[i+1] - pt
                if diff.length_squared() > 1e-6:
                    tangent = diff.normalize()
                else:
                    tangent = _unit(base_angle)
            elif i > 0:
                diff = pt - spine_points[i-1]
                if diff.length_squared() > 1e-6:
                    tangent = diff.normalize()
                else:
                    tangent = _unit(base_angle)
            else:
                tangent = _unit(base_angle)
                
            normal = Vector2(-tangent.y, tangent.x)
            
            left_verts.append(pt + normal * width)
            right_verts.append(pt - normal * width)
            
        # Combine into closed loop
        poly_points = left_verts + list(reversed(right_verts))
        int_poly = [(int(p.x), int(p.y)) for p in poly_points]
        
        # Draw Tentacle Body
        fill_color = (*color, alpha)
        pygame.draw.polygon(self.surface, fill_color, int_poly)
        
        # Outline
        pygame.draw.lines(self.surface, (200, 220, 230), False, [(int(p.x), int(p.y)) for p in left_verts], 1)
        pygame.draw.lines(self.surface, (200, 220, 230), False, [(int(p.x), int(p.y)) for p in right_verts], 1)
        
        # Internal muscle striations (rings)
        for i in range(1, num_segments, 2):
            p1 = left_verts[i]
            p2 = right_verts[i]
            pygame.draw.line(self.surface, (min(255, color[0]+30), min(255, color[1]+30), min(255, color[2]+30)), 
                             (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), 1)

    def _draw_eye(self, animated: AnimatedModule, offset: Vector2) -> None:
        module = animated.module
        center = offset + animated.current_pose.center * self.position_scale
        radius = module.size[0] * self.position_scale * 0.5 * getattr(module, "eye_size", 1.0)
        
        # Sclera (White)
        pygame.draw.circle(self.surface, (240, 240, 240), (int(center.x), int(center.y)), int(radius))
        pygame.draw.circle(self.surface, (200, 200, 200), (int(center.x), int(center.y)), int(radius), 1)
        
        # Iris
        iris_color = getattr(module, "iris_color", (100, 150, 200))
        iris_radius = radius * 0.6
        pygame.draw.circle(self.surface, iris_color, (int(center.x), int(center.y)), int(iris_radius))
        
        # Pupil
        pupil_color = getattr(module, "pupil_color", (0, 0, 0))
        pupil_shape = getattr(module, "pupil_shape", "circle")
        pupil_radius = iris_radius * 0.5
        
        if pupil_shape == "slit":
            rect = pygame.Rect(0, 0, pupil_radius * 0.6, pupil_radius * 2)
            rect.center = (int(center.x), int(center.y))
            pygame.draw.rect(self.surface, pupil_color, rect)
        elif pupil_shape == "rect":
            rect = pygame.Rect(0, 0, pupil_radius * 1.8, pupil_radius * 0.8)
            rect.center = (int(center.x), int(center.y))
            pygame.draw.rect(self.surface, pupil_color, rect)
        elif pupil_shape == "cross":
            rect1 = pygame.Rect(0, 0, pupil_radius * 0.5, pupil_radius * 1.8)
            rect1.center = (int(center.x), int(center.y))
            rect2 = pygame.Rect(0, 0, pupil_radius * 1.8, pupil_radius * 0.5)
            rect2.center = (int(center.x), int(center.y))
            pygame.draw.rect(self.surface, pupil_color, rect1)
            pygame.draw.rect(self.surface, pupil_color, rect2)
        else: # circle
            pygame.draw.circle(self.surface, pupil_color, (int(center.x), int(center.y)), int(pupil_radius))
            
        # Specular Highlight (Reflection)
        highlight_pos = (int(center.x + radius * 0.3), int(center.y - radius * 0.3))
        pygame.draw.circle(self.surface, (255, 255, 255), highlight_pos, int(radius * 0.2))

    def _draw_mouth(self, animated: AnimatedModule, offset: Vector2) -> None:
        module = animated.module
        center = offset + animated.current_pose.center * self.position_scale
        angle = animated.current_pose.angle
        
        # Use outline for base shape
        polygon_points = [
            (offset + vertex * self.position_scale) for vertex in animated.outline_world
        ]
        int_points = [(int(point.x), int(point.y)) for point in polygon_points]
        
        if len(int_points) < 3:
            return
            
        color = (180, 100, 100) # Reddish/Pinkish
        pygame.draw.polygon(self.surface, color, int_points)
        pygame.draw.polygon(self.surface, (100, 50, 50), int_points, 2)
        
        jaw_type = getattr(module, "jaw_type", "mandibles")
        
        forward = _unit(angle)
        right = _unit(angle + 90)
        size = module.size[0] * self.position_scale
        
        if jaw_type == "mandibles":
            # Draw two pincer shapes
            p1_start = center + right * size * 0.3
            p1_end = center + forward * size * 0.8 + right * size * 0.1
            p2_start = center - right * size * 0.3
            p2_end = center + forward * size * 0.8 - right * size * 0.1
            
            pygame.draw.line(self.surface, (50, 20, 20), (int(p1_start.x), int(p1_start.y)), (int(p1_end.x), int(p1_end.y)), 2)
            pygame.draw.line(self.surface, (50, 20, 20), (int(p2_start.x), int(p2_start.y)), (int(p2_end.x), int(p2_end.y)), 2)
        elif jaw_type == "beak":
            # Draw a triangle
            tip = center + forward * size * 0.9
            base_l = center - forward * size * 0.2 + right * size * 0.3
            base_r = center - forward * size * 0.2 - right * size * 0.3
            pygame.draw.polygon(self.surface, (200, 180, 100), [(int(tip.x), int(tip.y)), (int(base_l.x), int(base_l.y)), (int(base_r.x), int(base_r.y))])
            pygame.draw.polygon(self.surface, (100, 90, 50), [(int(tip.x), int(tip.y)), (int(base_l.x), int(base_l.y)), (int(base_r.x), int(base_r.y))], 1)
        elif jaw_type == "sucker":
            # Draw a circle with a hole
            pygame.draw.circle(self.surface, (150, 80, 80), (int(center.x), int(center.y)), int(size * 0.4))
            pygame.draw.circle(self.surface, (50, 20, 20), (int(center.x), int(center.y)), int(size * 0.2))

        # Draw joint
        joint_center = offset + animated.joint_position * self.position_scale
        joint_color = (120, 190, 240) if animated.parent_id else (220, 230, 240)
        pygame.draw.circle(self.surface, joint_color, (int(joint_center.x), int(joint_center.y)), 3)
        
        if self.show_debug:
            for point, is_parent in animated.contact_markers:
                self._draw_contact_marker(offset + point * self.position_scale, is_parent)
            self._draw_axes(animated, offset)

    def _draw_contact_marker(self, position: Vector2, is_parent: bool) -> None:
        color = PARENT_CONTACT_COLOR if is_parent else CHILD_CONTACT_COLOR
        x, y = int(position.x), int(position.y)
        pygame.draw.line(self.surface, color, (x - 3, y), (x + 3, y), 1)
        pygame.draw.line(self.surface, color, (x, y - 3), (x, y + 3), 1)

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
            1,
        )
        pygame.draw.line(
            self.surface,
            LATERAL_AXIS_COLOR,
            (int(center.x), int(center.y)),
            (int(center.x + lateral.x * lateral_len), int(center.y + lateral.y * lateral_len)),
            1,
        )

    def _draw_bridge(self, parent: AnimatedModule, child: AnimatedModule, offset: Vector2) -> None:
        direction = (child.joint_position - parent.joint_position)
        if direction.length_squared() < 1e-6:
            return
        direction = direction.normalize()
        tangent = Vector2(-direction.y, direction.x)
        parent_width = parent.half_cross * self.position_scale * 0.4 # Thinner bridges
        child_width = child.half_cross * self.position_scale * 0.4
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
        
        int_points = [(int(pt.x), int(pt.y)) for pt in bridge_points]
        pygame.draw.polygon(self.surface, blend_color, int_points)
        # Outline for bridge
        pygame.draw.polygon(self.surface, (200, 220, 230), int_points, 1)

__all__ = ["ModularRendererState", "BodyGraphRenderer", "AnimatedModule"]

#!/usr/bin/env python3
"""Interactive module viewer for testing lifeform rendering.

This tool allows developers to:
- Visualize body graphs with their modular structure
- Add/remove modules interactively
- Test different module configurations
- See real-time rendering updates

Usage:
    python tools/module_viewer.py
    python tools/module_viewer.py --screenshot output.png

Controls:
    1-7: Add different module types
    D: Remove last module
    R: Reset to default creature
    Q/ESC: Quit
    SPACE: Toggle animation
    +/-: Adjust animation speed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pygame
from pygame.math import Vector2

# Add parent directory to path to import evolution package
sys.path.insert(0, str(Path(__file__).parent.parent))

from evolution.body.modules import (
    build_default_fin,
    build_default_head,
    build_default_sensor,
    build_default_thruster,
)
from evolution.physics.physics_body import build_physics_body
from evolution.physics.test_creatures import build_fin_swimmer_prototype
from evolution.rendering.modular_palette import (
    BASE_MODULE_ALPHA,
    MODULE_RENDER_STYLES,
    tint_color,
)


class ModuleViewer:
    """Interactive viewer for testing module rendering."""

    def __init__(self, width: int = 1200, height: int = 800, headless: bool = False):
        # Set up pygame for headless mode if needed
        if headless:
            import os
            os.environ['SDL_VIDEODRIVER'] = 'dummy'

        pygame.init()
        self.width = width
        self.height = height
        self.headless = headless
        self.screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Module Viewer - Lifeform Body Graph")

        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 14)
        self.title_font = pygame.font.SysFont("monospace", 20, bold=True)

        # Viewer state
        self.creature = build_fin_swimmer_prototype()
        self.elapsed = 0.0
        self.running = True
        self.animate = True
        self.animation_speed = 1.0

        # Layout for rendering
        self.layout: dict[str, Vector2] = {}
        self.torso_color = (72, 130, 168)
        self._compute_layout()

        # Available modules for adding
        self.module_counter = 0

    def _compute_layout(self):
        """Compute 2D layout positions for modules in the body graph."""
        graph = self.creature.graph
        root_id = graph.root_id

        # Simple tree layout algorithm
        self.layout = {}
        self._layout_recursive(root_id, Vector2(0, 0), Vector2(0, 1), 0)

    def _layout_recursive(
        self, node_id: str, position: Vector2, direction: Vector2, depth: int
    ):
        """Recursively position nodes in a tree layout."""
        self.layout[node_id] = position

        node = self.creature.graph.get_node(node_id)
        children = list(node.children.keys())

        if not children:
            return

        # Arrange children in a fan pattern
        child_count = len(children)
        angle_step = 60.0 if child_count > 1 else 0.0
        start_angle = -angle_step * (child_count - 1) / 2.0

        for i, child_id in enumerate(children):
            import math
            angle = math.radians(start_angle + i * angle_step)
            child_direction = Vector2(
                direction.x * math.cos(angle) - direction.y * math.sin(angle),
                direction.x * math.sin(angle) + direction.y * math.cos(angle)
            )
            child_offset = 80 + depth * 20
            child_pos = position + child_direction * child_offset
            self._layout_recursive(child_id, child_pos, child_direction, depth + 1)

    def render(self):
        """Render the current creature and UI."""
        self.screen.fill((25, 35, 45))

        # Center the view
        center_x = self.width // 2
        center_y = self.height // 2 - 50

        # Render the body graph
        self._render_body_graph(center_x, center_y)

        # Render UI
        self._render_ui()

        pygame.display.flip()

    def _render_body_graph(self, center_x: int, center_y: int):
        """Render the modular body graph with connections."""
        import math

        graph = self.creature.graph

        # Compute animated positions
        positions: dict[str, Vector2] = {}
        for node_id, offset in self.layout.items():
            base_center = Vector2(center_x, center_y) + offset

            # Add animation if enabled
            if self.animate:
                sway_phase = self.elapsed * 1.2 + offset.x * 0.15
                lateral_sway = math.sin(sway_phase) * (5 + abs(offset.x) * 0.1)
                vertical_sway = math.sin(sway_phase * 0.7 + offset.y * 0.1) * (4 + abs(offset.y) * 0.05)
                base_center.x += lateral_sway
                base_center.y += vertical_sway

            positions[node_id] = base_center

        # Draw connections first (behind modules)
        for node_id, node in graph.nodes.items():
            parent_id = node.parent
            if not parent_id or parent_id not in positions or node_id not in positions:
                continue

            start = positions[parent_id]
            end = positions[node_id]

            # Draw curved connection
            direction = end - start
            control = (start + end) / 2
            normal = Vector2(-direction.y, direction.x)
            if normal.length_squared() > 1e-3:
                normal = normal.normalize()
                bend = math.sin(self.elapsed * 2.4 + offset.x * 0.8) if self.animate else 0
                normal *= bend * min(20.0, direction.length() * 0.3)
            control += normal

            width = 6 if node.module.module_type == "core" else 4
            pygame.draw.lines(
                self.screen,
                (60, 80, 100),
                False,
                [
                    (int(start.x), int(start.y)),
                    (int(control.x), int(control.y)),
                    (int(end.x), int(end.y))
                ],
                width
            )

        # Draw modules
        for node_id in self.layout:
            node = graph.get_node(node_id)
            module = node.module
            center = positions[node_id]

            # Calculate module size
            length = max(14, int(module.size[2] * 30))
            height = max(12, int(module.size[1] * 28))
            rect = pygame.Rect(0, 0, length, height)
            rect.center = (int(center.x), int(center.y))

            # Get visual style
            color, alpha = self._get_module_visuals(module.module_type)

            # Draw module body
            module_surface = pygame.Surface(rect.size, pygame.SRCALPHA)
            ellipse_rect = pygame.Rect(0, 0, rect.width, rect.height)
            pygame.draw.ellipse(module_surface, (*color, alpha), ellipse_rect)
            pygame.draw.ellipse(
                module_surface,
                (15, 30, 45, max(alpha, 160)),
                ellipse_rect,
                2
            )
            self.screen.blit(module_surface, rect)

            # Add module-specific decorations
            if module.module_type == "propulsion":
                # Thruster flame
                flame = rect.copy()
                flame.width = max(6, rect.width // 3)
                flame.left = rect.left - flame.width + 4
                flame_surface = pygame.Surface(flame.size, pygame.SRCALPHA)
                pygame.draw.ellipse(
                    flame_surface,
                    (255, 200, 150, max(120, alpha - 20)),
                    pygame.Rect(0, 0, flame.width, flame.height)
                )
                self.screen.blit(flame_surface, flame)

            elif module.module_type == "head":
                # Eye
                eye_center = (rect.centerx + rect.width // 4, rect.centery - rect.height // 4)
                pygame.draw.circle(self.screen, (15, 30, 60), eye_center, 4)

            # Draw module label
            label = self.font.render(module.key, True, (200, 220, 240))
            label_pos = (rect.centerx - label.get_width() // 2, rect.bottom + 5)
            self.screen.blit(label, label_pos)

    def _get_module_visuals(self, module_type: str) -> tuple[tuple[int, int, int], int]:
        """Get color and alpha for a module type."""
        style = MODULE_RENDER_STYLES.get(module_type, MODULE_RENDER_STYLES["default"])
        tint = style.get("tint", (1.0, 1.0, 1.0))
        tinted = tint_color(self.torso_color, tint)
        alpha_offset = int(style.get("alpha_offset", 0))
        alpha = max(60, min(255, BASE_MODULE_ALPHA + alpha_offset))
        return tinted, alpha

    def _render_ui(self):
        """Render UI overlay with controls and stats."""
        # Title
        title = self.title_font.render("Module Viewer - Body Graph", True, (220, 230, 240))
        self.screen.blit(title, (20, 20))

        # Controls
        y_pos = 60
        controls = [
            "Controls:",
            "  1: Add Fin (left)",
            "  2: Add Fin (right)",
            "  3: Add Thruster",
            "  4: Add Sensor",
            "  5: Add Head",
            "  D: Remove last module",
            "  R: Reset to default",
            "  SPACE: Toggle animation",
            "  +/-: Animation speed",
            "  Q/ESC: Quit",
        ]

        for text in controls:
            label = self.font.render(text, True, (180, 190, 200))
            self.screen.blit(label, (20, y_pos))
            y_pos += 20

        # Stats
        y_pos += 20
        graph = self.creature.graph
        agg = graph.aggregate_physics_stats()

        stats = [
            "Statistics:",
            f"  Modules: {len(graph)}",
            f"  Mass: {agg.mass:.1f} kg",
            f"  Volume: {agg.volume:.1f} m³",
            f"  Thrust: {agg.total_thrust:.1f} N",
            f"  Drag Area: {agg.drag_area:.2f} m²",
            f"  Energy Cost: {agg.energy_cost:.1f} W",
        ]

        for text in stats:
            label = self.font.render(text, True, (180, 190, 200))
            self.screen.blit(label, (20, y_pos))
            y_pos += 20

        # Animation state
        y_pos = self.height - 60
        anim_text = f"Animation: {'ON' if self.animate else 'OFF'} (Speed: {self.animation_speed:.1f}x)"
        anim_label = self.font.render(anim_text, True, (180, 190, 200))
        self.screen.blit(anim_label, (20, y_pos))

    def add_module(self, module_type: str):
        """Add a new module to the creature."""
        graph = self.creature.graph

        # Find a suitable attachment point
        for node_id, node in graph.nodes.items():
            module = node.module
            for point_name in module.attachment_points:
                # Check if this point is already used
                if point_name in node.children.values():
                    continue

                # Create new module based on type
                new_key = f"{module_type}_{self.module_counter}"
                self.module_counter += 1

                try:
                    if module_type == "fin_left" or module_type == "fin_right":
                        new_module = build_default_fin(new_key)
                    elif module_type == "thruster":
                        new_module = build_default_thruster(new_key)
                    elif module_type == "sensor":
                        new_module = build_default_sensor(new_key, ("light", "colour"))
                    elif module_type == "head":
                        new_module = build_default_head(new_key)
                    else:
                        print(f"Unknown module type: {module_type}")
                        return

                    # Try to add it
                    graph.add_module(new_key, new_module, node_id, point_name)

                    # Rebuild physics and layout
                    self.creature.physics = build_physics_body(graph)
                    self._compute_layout()
                    print(f"Added {new_key} to {node_id} at {point_name}")
                    return

                except (ValueError, KeyError):
                    # This attachment point didn't work, try next
                    continue

        print(f"Could not find suitable attachment point for {module_type}")

    def remove_last_module(self):
        """Remove the most recently added module (except root)."""
        graph = self.creature.graph

        # Find a non-root module to remove
        for node_id in reversed(list(graph.nodes.keys())):
            if node_id != graph.root_id:
                try:
                    graph.remove_module(node_id)
                    self.creature.physics = build_physics_body(graph)
                    self._compute_layout()
                    print(f"Removed module: {node_id}")
                    return
                except Exception as e:
                    print(f"Could not remove {node_id}: {e}")

        print("No modules to remove (cannot remove root)")

    def reset_creature(self):
        """Reset to default creature."""
        self.creature = build_fin_swimmer_prototype()
        self.module_counter = 0
        self._compute_layout()
        print("Reset to default creature")

    def handle_event(self, event: pygame.event.Event):
        """Handle pygame events."""
        if event.type == pygame.QUIT:
            self.running = False

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_q, pygame.K_ESCAPE):
                self.running = False

            elif event.key == pygame.K_1:
                self.add_module("fin_left")

            elif event.key == pygame.K_2:
                self.add_module("fin_right")

            elif event.key == pygame.K_3:
                self.add_module("thruster")

            elif event.key == pygame.K_4:
                self.add_module("sensor")

            elif event.key == pygame.K_5:
                self.add_module("head")

            elif event.key == pygame.K_d:
                self.remove_last_module()

            elif event.key == pygame.K_r:
                self.reset_creature()

            elif event.key == pygame.K_SPACE:
                self.animate = not self.animate
                print(f"Animation: {'ON' if self.animate else 'OFF'}")

            elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                self.animation_speed = min(5.0, self.animation_speed + 0.5)
                print(f"Animation speed: {self.animation_speed:.1f}x")

            elif event.key == pygame.K_MINUS:
                self.animation_speed = max(0.1, self.animation_speed - 0.5)
                print(f"Animation speed: {self.animation_speed:.1f}x")

    def save_screenshot(self, filename: str):
        """Save current view to a file."""
        pygame.image.save(self.screen, filename)
        print(f"Screenshot saved to {filename}")

    def run(self):
        """Main loop."""
        print("Module Viewer started")
        print("Use number keys to add modules, D to remove, R to reset")

        while self.running:
            dt = self.clock.tick(60) / 1000.0

            # Update animation
            if self.animate:
                self.elapsed += dt * self.animation_speed

            # Handle events
            for event in pygame.event.get():
                self.handle_event(event)

            # Render
            self.render()

        pygame.quit()
        print("Module Viewer closed")


def main():
    """Entry point for the module viewer."""
    parser = argparse.ArgumentParser(description="Interactive module viewer for lifeform body graphs")
    parser.add_argument(
        "--screenshot",
        type=str,
        help="Save a screenshot to the specified file and exit",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1200,
        help="Window width (default: 1200)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=800,
        help="Window height (default: 800)",
    )

    args = parser.parse_args()

    # Screenshot mode
    if args.screenshot:
        viewer = ModuleViewer(width=args.width, height=args.height, headless=True)
        viewer.render()
        viewer.save_screenshot(args.screenshot)
        pygame.quit()
        return

    # Interactive mode
    viewer = ModuleViewer(width=args.width, height=args.height)
    viewer.run()


if __name__ == "__main__":
    main()

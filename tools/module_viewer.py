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
    1-5: Add different module types
    D: Remove last module
    R: Reset to default creature
    Q/ESC: Quit
    SPACE: Toggle animation
    +/-: Adjust animation speed
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pygame
from pygame.math import Vector2

# Add parent directory to path to import evolution package
sys.path.insert(0, str(Path(__file__).parent.parent))

from evolution.body.body_graph import BodyGraph
from evolution.body.modules import (
    build_default_core,
    build_default_fin,
    build_default_head,
    build_default_sensor,
    build_default_thruster,
)
from evolution.physics.physics_body import build_physics_body
from evolution.physics.test_creatures import FinOscillationController, TestCreature, build_fin_swimmer_prototype
from evolution.rendering.modular_palette import (
    BASE_MODULE_ALPHA,
    MODULE_RENDER_STYLES,
    tint_color,
)
from evolution.rendering.modular_renderer import BodyGraphRenderer, ModularRendererState


class ModuleViewer:
    """Interactive viewer for testing module rendering."""

    def __init__(self, width: int = 1200, height: int = 800, headless: bool = False, pose: str | None = None):
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
        if pose == "sketch":
            self.creature = self._build_sketch_creature()
        else:
            self.creature = build_fin_swimmer_prototype()
        self.elapsed = 0.0
        self.running = True
        self.animate = True
        self.animation_speed = 1.0
        self.current_force = Vector2(0.0, 0.0)
        self.torque_bias = 0.0

        # Layout for rendering
        self.torso_color = (72, 130, 168)
        self.renderer_state = ModularRendererState(self.creature.graph, self.torso_color)
        self.renderer_state.refresh()
        self.renderer_state.rebuild_world_poses()
        self.renderer = BodyGraphRenderer(self.screen, self.torso_color)

        # Available modules for adding
        self.module_counter = 0

    def _build_sketch_creature(self) -> TestCreature:
        core = build_default_core("core")
        graph = BodyGraph(core.key, core)

        head = build_default_head("head")
        graph.add_module("head", head, "core", "head_socket")

        tentacle_root = build_default_fin("tentacle_root")
        graph.add_module("tentacle_root", tentacle_root, "core", "ventral_core")

        tentacle_tip = build_default_fin("tentacle_tip")
        graph.add_module("tentacle_tip", tentacle_tip, "tentacle_root", "proximal_joint")

        antenna = build_default_sensor("antenna", ("light", "sonar"))
        antenna.natural_orientation = 90.0
        antenna.size = (0.3, 0.3, 1.2)
        graph.add_module("antenna", antenna, "head", "cranial_sensor")

        fin_left = build_default_fin("fin_left")
        graph.add_module("fin_left", fin_left, "core", "lateral_mount_left")

        fin_right = build_default_fin("fin_right")
        graph.add_module("fin_right", fin_right, "core", "lateral_mount_right")

        graph.validate()
        physics = build_physics_body(graph)
        controller = FinOscillationController(amplitude=0.8, frequency=0.5)
        return TestCreature(name="sketch", graph=graph, physics=physics, controller=controller)

    def _apply_physics(self, dt: float) -> None:
        graph = self.creature.graph
        self.renderer_state.refresh()
        for node_id in graph.nodes:
            animated = self.renderer_state.poses[node_id]
            joint = None
            if animated.parent_id:
                parent = graph.get_node(animated.parent_id)
                joint = parent.module.get_attachment_point(animated.attachment_point or "")
            stiffness = 3.5
            damping = 1.5
            if joint is not None and joint.joint.torque_limit:
                stiffness += joint.joint.torque_limit * 0.01
            drag = animated.drag_area * 0.2
            torque = (self.current_force.x + self.current_force.y * 0.3) * 0.05
            torque += self.torque_bias
            angular_accel = (torque - damping * animated.angular_velocity - stiffness * animated.angle_offset) / max(1.0, animated.mass)
            animated.angular_velocity += angular_accel * dt
            animated.angular_velocity = max(-2.5, min(2.5, animated.angular_velocity - drag * dt))
            animated.angle_offset += animated.angular_velocity * dt
            animated.angle_offset = max(-35.0, min(35.0, animated.angle_offset))
        self.renderer_state.rebuild_world_poses()

    def render(self):
        """Render the current creature and UI."""
        self.screen.fill((25, 35, 45))
        center = Vector2(self.width // 2, self.height // 2)
        self.renderer_state.graph = self.creature.graph
        if self.animate:
            dt_seconds = self.clock.get_time() / 1000.0 * self.animation_speed
            self._apply_physics(dt_seconds)
        else:
            self.renderer_state.rebuild_world_poses()
        self.renderer.draw(self.renderer_state, center)
        self._render_ui()
        pygame.display.flip()

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
            f"  Current Force: ({self.current_force.x:.1f}, {self.current_force.y:.1f})",
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
                    self.creature.physics = build_physics_body(graph)
                    self.renderer_state.graph = graph
                    self.renderer_state.refresh()
                    self.renderer_state.rebuild_world_poses()
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
                    self.renderer_state.graph = graph
                    self.renderer_state.refresh()
                    self.renderer_state.rebuild_world_poses()
                    print(f"Removed module: {node_id}")
                    return
                except Exception as e:
                    print(f"Could not remove {node_id}: {e}")

        print("No modules to remove (cannot remove root)")

    def reset_creature(self):
        """Reset to default creature."""
        self.creature = build_fin_swimmer_prototype()
        self.creature.physics = build_physics_body(self.creature.graph)
        self.module_counter = 0
        self.renderer_state = ModularRendererState(self.creature.graph, self.torso_color)
        self.renderer_state.refresh()
        self.renderer_state.rebuild_world_poses()
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

            elif event.key == pygame.K_LEFT:
                self.current_force.x = max(-50.0, self.current_force.x - 5.0)
            elif event.key == pygame.K_RIGHT:
                self.current_force.x = min(50.0, self.current_force.x + 5.0)
            elif event.key == pygame.K_UP:
                self.current_force.y = max(-50.0, self.current_force.y - 5.0)
            elif event.key == pygame.K_DOWN:
                self.current_force.y = min(50.0, self.current_force.y + 5.0)
            elif event.key == pygame.K_p:
                self.current_force = Vector2()
            elif event.key == pygame.K_j:
                self.renderer.set_debug_overlays(not self.renderer.show_debug)

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
    parser.add_argument(
        "--pose",
        choices=("default", "sketch"),
        default="default",
        help="Choose initial creature layout",
    )

    args = parser.parse_args()

    # Screenshot mode
    if args.screenshot:
        viewer = ModuleViewer(width=args.width, height=args.height, headless=True, pose=args.pose)
        viewer.render()
        viewer.save_screenshot(args.screenshot)
        pygame.quit()
        return

    # Interactive mode
    viewer = ModuleViewer(width=args.width, height=args.height, pose=args.pose)
    viewer.run()


if __name__ == "__main__":
    main()

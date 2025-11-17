"""Simplified Newtonian fluid simulation focused on a layered alien ocean."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from pygame.math import Vector2


@dataclass(frozen=True)
class OceanLayer:
    """Definition of a depth layer inside the ocean."""

    name: str
    depth_start: float
    depth_end: float
    density: float
    drag: float
    light_absorption: float
    temperature: float
    current: Vector2


@dataclass(frozen=True)
class FluidProperties:
    """Fluid state sampled for a given depth."""

    layer: OceanLayer
    density: float
    drag: float
    light: float
    pressure: float
    temperature: float
    current: Vector2


class OceanPhysics:
    """Layered 2D Newtonian fluid approximating an alien ocean."""

    def __init__(self, width: float, depth: float) -> None:
        self.width = float(width)
        self.depth = max(1.0, float(depth))
        self.gravity = 9.81  # screen units / s^2
        self.surface_pressure = 1.0
        self.layers: List[OceanLayer] = self._build_default_layers()
        self._time: float = 0.0

    def _build_default_layers(self) -> List[OceanLayer]:
        depth = self.depth
        return [
            OceanLayer(
                name="Sunlit",
                depth_start=0.0,
                depth_end=depth * 0.15,
                density=0.97,
                drag=0.18,
                light_absorption=0.0014,
                temperature=26.0,
                current=Vector2(28.0, 0.0),
            ),
            OceanLayer(
                name="Twilight",
                depth_start=depth * 0.15,
                depth_end=depth * 0.35,
                density=1.02,
                drag=0.24,
                light_absorption=0.003,
                temperature=12.0,
                current=Vector2(12.0, 2.0),
            ),
            OceanLayer(
                name="Midnight",
                depth_start=depth * 0.35,
                depth_end=depth * 0.7,
                density=1.08,
                drag=0.32,
                light_absorption=0.008,
                temperature=4.0,
                current=Vector2(6.0, 6.0),
            ),
            OceanLayer(
                name="Abyss",
                depth_start=depth * 0.7,
                depth_end=depth,
                density=1.15,
                drag=0.42,
                light_absorption=0.02,
                temperature=1.0,
                current=Vector2(2.0, 4.0),
            ),
        ]

    def update(self, now_ms: int) -> None:
        self._time = now_ms / 1000.0

    def layer_at(self, depth: float) -> OceanLayer:
        clamped_depth = max(0.0, min(self.depth, depth))
        for layer in self.layers:
            if layer.depth_start <= clamped_depth < layer.depth_end:
                return layer
        return self.layers[-1]

    def properties_at(self, depth: float) -> FluidProperties:
        layer = self.layer_at(depth)
        local_depth = max(layer.depth_start, min(layer.depth_end, depth))
        layer_fraction = (local_depth - layer.depth_start) / max(
            1.0, layer.depth_end - layer.depth_start
        )
        density = layer.density * (1.0 + layer_fraction * 0.08)
        pressure = self.surface_pressure + density * self.gravity * (depth / self.depth)
        light = math.exp(-depth * layer.light_absorption)
        sway = math.sin(self._time * 0.12 + layer_fraction) * 14.0
        current = layer.current.rotate(sway)
        current *= 0.4 + 0.6 * (1.0 - layer_fraction)
        return FluidProperties(
            layer=layer,
            density=density,
            drag=layer.drag,
            light=max(0.0, min(1.0, light)),
            pressure=pressure,
            temperature=layer.temperature,
            current=current,
        )

    def enrich_effects(self, effects: dict, depth: float) -> None:
        fluid = self.properties_at(depth)
        effects["light"] = fluid.light
        effects["pressure"] = fluid.pressure
        effects["fluid_density"] = fluid.density
        effects["current_speed"] = fluid.current.length()
        effects["temperature"] = fluid.temperature

    def integrate_body(
        self,
        lifeform,
        thrust: Vector2,
        dt: float,
        *,
        max_speed: float,
    ) -> Tuple[Vector2, FluidProperties]:
        fluid = self.properties_at(lifeform.rect.centery)
        physics_body = getattr(lifeform, "physics_body", None)
        base_mass = float(getattr(physics_body, "mass", getattr(lifeform, "mass", 1.0)))
        mass = max(0.4, base_mass)
        body_density = max(
            0.2,
            float(getattr(physics_body, "density", getattr(lifeform, "body_density", 1.0))),
        )
        volume = max(
            1.0,
            float(getattr(physics_body, "volume", getattr(lifeform, "volume", 1.0))),
        )
        buoyancy_volume = max(
            1.0,
            float(
                getattr(
                    physics_body,
                    "buoyancy_volume",
                    getattr(lifeform, "buoyancy_volume", volume),
                )
            ),
        )
        propulsion = thrust
        volume_scale = min(2.5, max(0.3, buoyancy_volume / 220.0))
        buoyancy_ratio = fluid.density / body_density
        buoyancy_acc = (buoyancy_ratio - 1.0) * self.gravity * volume_scale
        locomotion_drag = getattr(lifeform, "_locomotion_drag_multiplier", 1.0)
        base_drag = float(
            getattr(
                physics_body,
                "drag_coefficient",
                getattr(lifeform, "drag_coefficient", 0.2),
            )
        )
        drag_coefficient = fluid.drag + base_drag * locomotion_drag
        drag = -lifeform.velocity * (drag_coefficient / max(1.0, mass))
        grip_strength = max(0.3, float(getattr(lifeform, "grip_strength", 1.0)))
        if physics_body is not None:
            grip_strength = max(grip_strength, physics_body.grip_strength / 6.0)
        current_adjust = (fluid.current - lifeform.velocity) * (
            0.12 / max(0.5, grip_strength)
        )
        net_gravity = self.gravity - buoyancy_acc
        vertical = Vector2(0.0, net_gravity)
        acceleration = propulsion + drag + current_adjust + vertical
        lifeform.velocity += acceleration * dt
        speed = lifeform.velocity.length()
        if speed > max_speed:
            lifeform.velocity.scale_to_length(max_speed)
        displacement = lifeform.velocity * dt
        next_position = Vector2(lifeform.x, lifeform.y) + displacement
        lifeform.last_fluid_properties = fluid
        return next_position, fluid

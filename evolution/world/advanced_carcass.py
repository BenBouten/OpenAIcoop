"""Advanced carcass system with decomposition, modular rendering, and physics."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, TYPE_CHECKING

import pygame
from pygame.math import Vector2

from ..config import settings
from ..rendering.modular_renderer import BodyGraphRenderer, ModularRendererState
from ..systems.telemetry import log_event

if TYPE_CHECKING:
    from ..entities.lifeform import Lifeform
    from .world import World

Color = Tuple[int, int, int]


class DecompositionStage(Enum):
    """Stages of decomposition affecting physics and visuals."""
    FRESH = "fresh"              # Normal density, sinks slowly
    BLOATED = "bloated"          # Gas buildup, floats upward
    ACTIVE_DECAY = "active"      # Gas escapes, max particles, starts sinking
    ADVANCED_DECAY = "advanced"  # Waterlogged, sinks fast
    DISINTEGRATED = "gone"       # Removed from world


@dataclass
class OceanSnowParticle:
    """Small organic particle drifting from decomposing carcass."""
    position: Vector2
    velocity: Vector2
    size: float
    nutrition: float
    opacity: int
    color: Tuple[int, int, int]
    max_age: float
    age: float = 0.0

    def update(self, dt: float, current: Vector2, gravity: float = 9.81) -> bool:
        """Update particle physics. Returns False if particle should be removed."""
        self.age += dt
        if self.age >= self.max_age:
            return False
            
        # Physics
        drag = 0.5
        buoyancy = -0.2 * gravity  # Slight sinking
        
        # Apply forces
        self.velocity.y += (gravity + buoyancy) * dt
        self.velocity += (current - self.velocity) * drag * dt
        
        # Move
        self.position += self.velocity * dt
        
        # Fade out
        self.opacity = max(0, int(self.opacity * (1.0 - dt * 0.5)))
        
        return self.opacity > 5

    def draw(self, surface: pygame.Surface, offset: Tuple[int, int]) -> None:
        """Draw the particle."""
        if self.opacity <= 0:
            return
            
        pos = (int(self.position.x - offset[0]), int(self.position.y - offset[1]))
        
        # Create surface for transparency
        s = pygame.Surface((int(self.size * 2) + 1, int(self.size * 2) + 1), pygame.SRCALPHA)
        color_with_alpha = (*self.color, self.opacity)
        pygame.draw.circle(s, color_with_alpha, (int(self.size), int(self.size)), int(self.size))
        
        surface.blit(s, (pos[0] - int(self.size), pos[1] - int(self.size)))


class DecomposingCarcass:
    """Advanced carcass with decomposition stages, dynamic buoyancy, and modular rendering."""

    def __init__(
        self,
        *,
        position: Tuple[float, float],
        size: Tuple[int, int],
        mass: float,
        nutrition: float,
        color: Color,
        body_graph=None,  # Original creature body structure
        body_geometry: dict = None,  # Original geometry data
    ) -> None:
        self.x, self.y = position
        width, height = size
        self.width = max(6, int(width))
        self.height = max(4, int(height))
        self.rect = pygame.Rect(int(self.x), int(self.y), self.width, self.height)
        
        # Store original body for rendering
        self.body_graph = body_graph
        self.body_geometry = body_geometry or {}
        self.angle = random.uniform(-15.0, 15.0)
        self.angular_velocity = random.uniform(-3.0, 3.0)  # degrees per second
        
        # Physical properties
        self.initial_mass = max(0.5, mass)
        self.mass = self.initial_mass
        self.velocity = Vector2(random.uniform(-3.0, 3.0), 0.0)
        
        # Nutrition and decay
        self.initial_nutrition = float(max(5.0, nutrition))
        self.resource = self.initial_nutrition
        self.base_decay_rate = max(0.05, self.resource * 0.0005)
        
        # Visual
        self.original_color = color
        self.color = color
        self.outline_color = tuple(max(0, min(255, channel - 40)) for channel in color)
        
        # Decomposition tracking
        self.decomposition_progress = 0.0  # 0.0 to 1.0
        self.stage = DecompositionStage.FRESH
        self.time_since_death = 0.0
        
        # Buoyancy modifiers
        self.gas_buildup = 0.0  # 0 to 1, increases buoyancy
        self.waterlogging = 0.0  # 0 to 1, decreases buoyancy
        # Start slightly heavier than water so it sinks slowly when fresh
        self.base_density = 1.05 
        self.body_density = self.base_density
        
        # Ocean snow particles
        self.snow_particles: List[OceanSnowParticle] = []
        self.particle_spawn_timer = 0.0
        self.particle_spawn_interval = 0.5  # seconds

        # Module consumption tracking
        self.consumed_modules = set()  # Set of module keys (node_ids) that have been eaten

    def _update_decomposition_stage(self) -> None:
        """Update stage based on progress."""
        old_stage = self.stage
        
        if self.decomposition_progress < 0.2:
            self.stage = DecompositionStage.FRESH
            self.gas_buildup = 0.0
            self.waterlogging = 0.0
        elif self.decomposition_progress < 0.4:
            self.stage = DecompositionStage.BLOATED
            # Gas buildup phase - floats
            self.gas_buildup = min(1.0, (self.decomposition_progress - 0.2) / 0.2 * 2.0)
            self.waterlogging = 0.0
        elif self.decomposition_progress < 0.7:
            self.stage = DecompositionStage.ACTIVE_DECAY
            # Gas escapes, starts waterlogging
            self.gas_buildup = max(0.0, 1.0 - (self.decomposition_progress - 0.4) / 0.3)
            self.waterlogging = (self.decomposition_progress - 0.4) / 0.3
        elif self.decomposition_progress < 1.0:
            self.stage = DecompositionStage.ADVANCED_DECAY
            # Heavily waterlogged, sinks fast
            self.gas_buildup = 0.0
            self.waterlogging = min(1.0, (self.decomposition_progress - 0.7) / 0.3 * 1.5)
        else:
            self.stage = DecompositionStage.DISINTEGRATED
            
        if self.stage != old_stage:
            log_event("CARCASS", "DECOMPOSITION_STAGE", "SYSTEM", {
                "pos": (int(self.x), int(self.y)),
                "from": old_stage.value,
                "to": self.stage.value,
                "mass": round(self.mass, 2)
            })

    def _calculate_dynamic_density(self) -> float:
        """Calculate density based on decomposition state."""
        # Base density modified by gas and waterlogging
        gas_factor = 1.0 - self.gas_buildup * 0.7  # Gas makes it lighter (more buoyant)
        water_factor = 1.0 + self.waterlogging * 0.8  # Water makes it heavier
        
        return self.base_density * gas_factor * water_factor

    def _emit_ocean_snow(self, world: "World") -> None:
        """Emit decomposition particles (ocean snow)."""
        # More particles during active decay
        emission_rate = 0.0
        if self.stage == DecompositionStage.ACTIVE_DECAY:
            emission_rate = 3.0  # particles per spawn
        elif self.stage == DecompositionStage.ADVANCED_DECAY:
            emission_rate = 1.0
        elif self.stage == DecompositionStage.BLOATED:
            emission_rate = 0.5
        
        num_particles = int(emission_rate)
        if random.random() < (emission_rate - num_particles):
            num_particles += 1
        
        for _ in range(num_particles):
            # Spawn particle near carcass
            offset_x = random.uniform(-self.width / 2, self.width / 2)
            offset_y = random.uniform(-self.height / 2, self.height / 2)
            
            position = Vector2(
                self.rect.centerx + offset_x,
                self.rect.centery + offset_y
            )
            
            # Initial velocity (slight upward if bloated/gas release)
            if self.stage == DecompositionStage.BLOATED:
                vy = random.uniform(-5.0, -1.0)  # Float up
            else:
                vy = random.uniform(-0.5, 0.5)
            
            velocity = Vector2(
                random.uniform(-2.0, 2.0),
                vy
            )
            
            # Particle properties
            size = random.uniform(0.5, 2.0)
            nutrition_per_particle = self.base_decay_rate * 0.1
            
            # Gray color for decomposition
            gray_val = random.randint(60, 120)
            particle_color = (gray_val, gray_val, gray_val)
            
            particle = OceanSnowParticle(
                position=position,
                velocity=velocity,
                size=size,
                nutrition=nutrition_per_particle,
                opacity=random.randint(100, 200),
                color=particle_color,
                max_age=random.uniform(20.0, 40.0)
            )
            
            self.snow_particles.append(particle)

    def _update_color(self) -> None:
        """Update color to gray based on decomposition."""
        # Gradually desaturate and darken
        gray_factor = self.decomposition_progress
        
        r, g, b = self.original_color
        
        # Convert to grayscale
        gray = int(r * 0.299 + g * 0.587 + b * 0.114)
        
        # Blend original with gray
        new_r = int(r * (1 - gray_factor) + gray * gray_factor)
        new_g = int(g * (1 - gray_factor) + gray * gray_factor)
        new_b = int(b * (1 - gray_factor) + gray * gray_factor)
        
        # Darken over time
        darkness = 1.0 - (self.decomposition_progress * 0.6)
        new_r = int(new_r * darkness)
        new_g = int(new_g * darkness)
        new_b = int(new_b * darkness)
        
        self.color = (
            max(0, min(255, new_r)),
            max(0, min(255, new_g)),
            max(0, min(255, new_b))
        )
        self.outline_color = tuple(max(0, min(255, channel - 30)) for channel in self.color)

    def update(self, world: "World", dt: float) -> None:
        """Update carcass physics, decomposition, and particles."""
        from .ocean_physics import OceanPhysics
        
        self.time_since_death += dt
        
        # Update decomposition progress
        # Target ~60 seconds for full decomposition
        decay_speed = 1.0 / 60.0 
        self.decomposition_progress += decay_speed * dt
        self.decomposition_progress = min(1.0, self.decomposition_progress)
        
        # Update decomposition stage
        self._update_decomposition_stage()
        
        # Update visual appearance
        self._update_color()
        
        # Update rotation
        self.angle += self.angular_velocity * dt
        
        # Calculate current density
        self.body_density = self._calculate_dynamic_density()
        
        # Physics update
        gravity = 9.81
        fluid_density = 1.0
        current = Vector2()
        
        if hasattr(world, "ocean") and isinstance(world.ocean, OceanPhysics):
            fluid = world.ocean.properties_at(self.rect.centery)
            gravity = world.ocean.gravity
            fluid_density = fluid.density
            current = fluid.current
        
        # Buoyancy force
        # Buoyancy force (upward force opposing gravity)
        # F_net = g * (1 - rho_fluid / rho_body)
        # If body is lighter (rho_body < rho_fluid), factor > 1, result is negative (upward)
        buoyancy_factor = fluid_density / max(0.1, self.body_density)
        vertical_acc = gravity * (1.0 - buoyancy_factor)
        
        # Apply drag to simulate water resistance
        self.velocity.y *= 0.95
        
        # Add some random wobble during decomposition
        if self.stage in (DecompositionStage.BLOATED, DecompositionStage.ACTIVE_DECAY):
            wobble = math.sin(self.time_since_death * 2.0) * 0.5
            self.velocity.x += wobble * dt
        
        self.velocity.y += vertical_acc * dt
        self.velocity += (current - self.velocity) * 0.05 * dt
        
        # Position update
        self.x += self.velocity.x * dt
        self.y += self.velocity.y * dt
        
        # Boundaries
        max_x = world.width - self.width
        max_y = world.height - self.height
        if self.x < 0:
            self.x = 0
            self.velocity.x *= -0.3
        elif self.x > max_x:
            self.x = max_x
            self.velocity.x *= -0.3
        if self.y > max_y:
            self.y = max_y
            self.velocity.y *= -0.2
        
        self.rect.topleft = (int(self.x), int(self.y))
        
        # Decay nutrition
        self.resource = max(0.0, self.resource - self.base_decay_rate * dt)
        
        # Emit ocean snow particles
        self.particle_spawn_timer += dt
        if self.particle_spawn_timer >= self.particle_spawn_interval:
            self.particle_spawn_timer = 0.0
            self._emit_ocean_snow(world)
        
        # Update particles
        self.snow_particles = [
            p for p in self.snow_particles
            if p.update(dt, current, gravity)
        ]
        
        # Limit particle count
        if len(self.snow_particles) > 200:
            self.snow_particles = self.snow_particles[-200:]

    def draw(self, surface: pygame.Surface, offset: Tuple[int, int] = (0, 0)) -> None:
        """Draw carcass with decomposition effects."""
        if self.stage == DecompositionStage.DISINTEGRATED:
            return
        
        # Draw ocean snow particles first (behind carcass)
        for particle in self.snow_particles:
            particle.draw(surface, offset)
        
        # Calculate screen position
        x = int(self.x) - offset[0]
        y = int(self.y) - offset[1]
        
        # Opacity decreases as it decomposes
        base_opacity = int(255 * (1.0 - self.decomposition_progress * 0.3))
        
        # Try to use modular renderer for realistic body
        rendered_modular = False
        if self.body_graph is not None:
            try:
                # Create state
                state = ModularRendererState(self.body_graph, self.color)
                state.rebuild_world_poses()
                
                # Remove consumed modules from state so they don't render
                for module_key in self.consumed_modules:
                    if module_key in state.poses:
                        del state.poses[module_key]
                
                # Create a temporary surface for the body
                # Use a generous size to accommodate limbs and rotation
                surf_size = int(max(self.width, self.height) * 2.5)
                body_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
                
                # Render to center of temp surface
                renderer = BodyGraphRenderer(body_surf, self.color, position_scale=settings.BODY_PIXEL_SCALE)
                renderer.draw(state, Vector2(surf_size // 2, surf_size // 2))
                
                # Apply opacity
                if base_opacity < 255:
                    body_surf.set_alpha(base_opacity)
                
                # Rotate the body (dead creatures tumble)
                if abs(self.angle) > 0.1:
                    body_surf = pygame.transform.rotate(body_surf, -self.angle)
                
                # Center the rotated surface
                body_rect = body_surf.get_rect()
                blit_x = x + self.width // 2 - body_rect.width // 2
                blit_y = y + self.height // 2 - body_rect.height // 2
                
                surface.blit(body_surf, (blit_x, blit_y))
                
                # Add decay spots overlay
                if self.stage in (DecompositionStage.ACTIVE_DECAY, DecompositionStage.ADVANCED_DECAY):
                    spot_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
                    for _ in range(random.randint(3, 7)):
                        spot_x = random.randint(0, self.width)
                        spot_y = random.randint(0, self.height)
                        spot_size = random.randint(2, 5)
                        spot_opacity = random.randint(30, 80)
                        spot_color = (30, 30, 30, spot_opacity)
                        pygame.draw.circle(spot_surface, spot_color, (spot_x, spot_y), spot_size)
                    
                    surface.blit(spot_surface, (x, y))
                
                rendered_modular = True
                
            except Exception:
                # Fall back to ellipse if modular rendering fails
                pass
        
        if not rendered_modular:
            # Fallback: Simple ellipse rendering
            ellipse = pygame.Rect(0, 0, self.width, self.height)
            body_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
            
            pygame.draw.ellipse(body_surface, (*self.color, base_opacity), ellipse)
            pygame.draw.ellipse(body_surface, self.outline_color, ellipse, 2)
            
            # Add texture/spots for decay
            if self.stage in (DecompositionStage.ACTIVE_DECAY, DecompositionStage.ADVANCED_DECAY):
                for _ in range(random.randint(2, 5)):
                    spot_x = random.randint(0, self.width)
                    spot_y = random.randint(0, self.height)
                    spot_size = random.randint(1, 3)
                    spot_color = (
                        max(0, self.color[0] - 30),
                        max(0, self.color[1] - 30),
                        max(0, self.color[2] - 30),
                        base_opacity // 2
                    )
                    pygame.draw.circle(body_surface, spot_color, (spot_x, spot_y), spot_size)
            
            surface.blit(body_surface, (x, y))

    def is_depleted(self) -> bool:
        """Check if carcass is depleted."""
        return self.resource <= 0.25 or self.stage == DecompositionStage.DISINTEGRATED

    def distance_to(self, point: Tuple[float, float]) -> float:
        """Distance to a point."""
        dx = self.rect.centerx - point[0]
        dy = self.rect.centery - point[1]
        return math.hypot(dx, dy)

    def consume(self, amount: float) -> float:
        """Consume nutrition from carcass."""
        if self.resource <= 0:
            return 0.0
        bite = min(amount, self.resource)
        self.resource -= bite
        
        # Consuming speeds up decomposition slightly
        self.decomposition_progress = min(1.0, self.decomposition_progress + 0.01)
        
        return bite

    def consume_module(self, node_id: str) -> float:
        """Consume a specific module from the carcass.
        
        Args:
            node_id: The key/node_id of the module to consume.
            
        Returns:
            float: Nutrition value obtained (0.0 if already eaten or not found).
        """
        if self.body_graph is None:
            return 0.0
            
        if node_id in self.consumed_modules:
            return 0.0
            
        try:
            node = self.body_graph.get_node(node_id)
            module = node.module
        except KeyError:
            return 0.0
            
        # Get nutrition value
        nutrition = module.stats.nutrition_value
        
        # Mark as consumed
        self.consumed_modules.add(node_id)
        
        # Accelerate decomposition
        self.decomposition_progress = min(1.0, self.decomposition_progress + 0.02)
        
        # Reduce total resource pool to keep it somewhat in sync
        # (though resource pool is less relevant with module consumption)
        self.resource = max(0.0, self.resource - nutrition)
        
        return nutrition

    def blocks_rect(self, _rect: pygame.Rect) -> bool:
        return False

    def contains_point(self, x: float, y: float) -> bool:
        return self.rect.collidepoint(int(x), int(y))

    def movement_modifier_for(self, _lifeform: "Lifeform") -> float:
        return 1.0

    def apply_effect(
        self,
        lifeform: "Lifeform",
        nutrition: float,
        *,
        digest_multiplier: float = 1.0,
    ) -> None:
        """Apply nutrition effect to lifeform eating the carcass."""
        scaled_nutrition = nutrition * digest_multiplier
        hunger_reduction = (
            scaled_nutrition * settings.PLANT_HUNGER_SATIATION_PER_NUTRITION * 1.4
        )
        lifeform.hunger = max(settings.HUNGER_MINIMUM, lifeform.hunger - hunger_reduction)
        lifeform.energy_now = min(
            lifeform.energy, lifeform.energy_now + scaled_nutrition * 0.8
        )
        lifeform.health_now = min(
            lifeform.health, lifeform.health_now + scaled_nutrition * 0.2
        )

    def summary(self) -> dict:
        return {
            "resource": round(self.resource, 2),
            "position": (self.x, self.y),
            "stage": self.stage.value,
            "decomposition": round(self.decomposition_progress, 2),
            "particles": len(self.snow_particles),
        }

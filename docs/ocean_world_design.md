# Ocean world integration guide

This document outlines how the layered ocean world exposes physical and ecological data to emergent agents.

## Depth layers and biomes
- The world is assembled from stacked `DepthLayer` bands produced by `build_ocean_blueprint`.
- Each layer wraps a `BiomeRegion` that supplies baseline movement, hunger, regrowth, energy, and health modifiers. Active weather adjusts these values at runtime.
- `World.get_layer_at(y)` returns the layer intersecting a depth, while `World.get_biome_at(x, y)` resolves the underlying biome (respecting masks).
- Biome effects are cached via a lightweight layer lookup so sensors can query frequently without heavy collision checks.

## Physics as the single movement source
- `OceanPhysics` is instantiated once per world and all movement should flow through `World.apply_fluid_dynamics`, which delegates to `OceanPhysics.integrate_body`.
- Agents influence motion by emitting thrust/forces; buoyancy, drag, currents, and density are integrated by physics—no direct teleportation paths should be added.

## Environment sampling API
- `World.sample_environment(x, y)` gathers sensory-friendly data:
  - Normalised depth, local light, density, drag, pressure, temperature, and current vector from `OceanPhysics.properties_at`.
  - Biome modifiers (`movement`, `hunger`, `regrowth`, `health`) derived from `BiomeRegion.get_effects`.
  - A mutation multiplier from `World.get_mutation_multiplier`, which blends nearby `RadVentField` influence.
- The API is deliberately descriptive: brains can interpret signals without scripted "go to food" behaviours.

## Mutation hotspots
- `RadVentField` instances define radioactive vents with a centre, radius, and mutation bonus.
- `World.get_mutation_multiplier(x, y)` returns `1.0` plus weighted vent influence (clamped), enabling DNA mutation systems to query local variation pressure.

## Vegetation and resource cycle
- Vegetation placement now honours `World.vegetation_masks` generated per depth band.
- Moss clusters are seeded in shallower "Surface" and "Sunlit" masks; seaweed strands prefer "Sunlit" and "Twilight" masks for deeper growth.
- Both plant types reuse biome `regrowth_modifier` via their existing growth logic, keeping primary production coupled to local conditions.
- Dead creatures spawn `DecomposingCarcass` instances that shed ocean snow particles over time, returning nutrients to the water column and plants.

## Usage by creatures/brains
- Sample the environment with `World.sample_environment` to build sensors for depth, light, flow, and biome stressors.
- Query `World.get_mutation_multiplier` when mutating DNA to localise adaptation pressure near vents.
- Avoid hardcoded behaviours; the world exposes state, while neural controllers learn how to respond.

Philosophy: the world and physics define constraints, while behaviour emerges from agents and evolution rather than scripts or roles.

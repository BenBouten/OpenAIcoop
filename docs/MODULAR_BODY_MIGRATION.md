# Modular Body Migration Plan

## Goals
- Remove all legacy sprite-derived stats (width/height/profile_geometry) in favor of BodyGraph geometry.
- Ensure sensory data and combat/physics stats come from modular modules.
- Provide step-by-step checklist for future contributors.

## Checklist
1. Audit references to `profile_geometry`, `body_geometry`, and `USE_BODYGRAPH_SIZE` (done; see sections below).
2. Unify spawn/reproduction templates to always store BodyGraph genomes and derived `geometry`.
3. Update `Lifeform` to derive width/height/perception/hearing strictly from BodyGraph outputs.
4. Remove flag fallbacks in rendering (`draw_lifeform`, `sprite_cache`).
5. Ensure AI/targeting uses `sensor_suite`/`_apply_sensor_baselines` rather than legacy morph stats.
6. Align population stats/UI with new fields and delete sprite-specific config toggles.
7. Add regression tests for BodyGraph sizing, sensors, and rendering caches.
8. Document rollout, feature flags, and telemetry validation.

## Current Touchpoints
- `evolution/entities/lifeform.py`: still stores `profile_geometry`; `perception_rays` and `hearing_range` seeded by morph stats.
- `evolution/rendering/draw_lifeform.py` / `sprite_cache.py`: rely on `profile_geometry` when flag is enabled.
- `evolution/config/settings.py`: `USE_BODYGRAPH_SIZE` CLI/env toggles.
- `evolution/entities/reproduction.py`: `_mix_parent_traits`, `_apply_mutations`, `_clamp_profile` mutate legacy width/height.
- `evolution/simulation/bootstrap.py`: seeds `width/height` before BodyGraph build; spawn spacing uses legacy radius when geometry absent.
- `evolution/morphology/phenotype.py`: collision stats computed from fixed `(32,32)` base.

## Implementation Phases
1. **Geometry Source of Truth**
   - Remove `profile_geometry` storage on lifeforms.
   - Always compute `base_width/base_height` from `body_graph.compute_bounds()`.
   - Update rendering helpers to trust `lifeform.body_geometry` exclusively.
2. **Sensory & Stat Derivation**
   - Introduce `_apply_sensor_baselines()` (now implemented) to convert sensor modules → perception/hearing stats.
   - Feed locomotion/AI systems with sensor suite ranges.
3. **Spawner/Template Cleanup**
   - Ensure DNA generation/reproduction always run `build_body_graph(..., include_geometry=True)`.
   - Remove legacy `width/height` mutations; instead mutate genomes or module params.
4. **UI/Telemetry Update**
   - Adjust inspector/stats windows to display BodyGraph metrics.
   - Log warnings if legacy geometry fields appear.
5. **Config Flag Retirement**
   - Deprecate `USE_BODYGRAPH_SIZE` after new code ships; keep CLI flag as no-op with warning for one release.
6. **Testing & Validation**
   - Add tests for sensor aggregation, BodyGraph geometry scaling, sprite cache dimensions.
   - Run visual regression via screenshots or geometry logs.

## Status Snapshot (Nov 21, 2025)
- Sensor baselines derived from BodyGraph **Done** (`_apply_sensor_baselines`).
- Documentation plan established (this file).
- Remaining work: landing code changes in steps 1-5, write regression tests, update docs/README about new workflow.


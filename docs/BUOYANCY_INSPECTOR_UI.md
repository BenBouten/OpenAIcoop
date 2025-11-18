# Buoyancy Inspector UI Feature - Visual Guide

## Overview
This document describes the new "Net drijfvermogen" (Net Buoyancy) feature added to the Lifeform Inspector UI.

## UI Location
The new stat appears in the **left column** of the "Kernstatistieken" (Core Statistics) section, after the "Leeftijd" (Age) field.

## Display Format

### Stat Row
```
Net drijfvermogen: +2.3%     ← Floating (positive buoyancy)
Net drijfvermogen: -1.5%     ← Sinking (negative buoyancy)
Net drijfvermogen: +0.1%     ← Near-neutral (near-floating)
Net drijfvermogen: n/a       ← Diagnostics not available
```

The percentage represents `relative_buoyancy`, which is the ratio of net buoyant force to weight:
- **Positive values** (e.g., +2.3%) = body is lighter than water, tends to float upward
- **Negative values** (e.g., -1.5%) = body is heavier than water, tends to sink
- **Near zero** (e.g., +0.1%) = body is near-neutrally buoyant, hovers at current depth

### Tooltip (on hover)
When hovering over the "Net drijfvermogen" stat, a detailed tooltip appears showing:

```
Net buoyancy (N): 1.85
Relative: +2.30%
Near-floating: No
Fluid density: 0.970
Buoyancy volume: 80.00
Body volume: 80.00
Body density: 0.948
Mass: 75.84
Buoyant force (N): 761.26
Weight (N): 743.99
```

**Tooltip Fields Explained:**
- **Net buoyancy (N)**: The net upward/downward force (buoyant force - weight)
- **Relative**: Same as the main stat, shown as percentage
- **Near-floating**: "Yes" if within tolerance (±5% relative OR ±0.5N absolute), "No" otherwise
- **Fluid density**: Density of the water/fluid at the lifeform's current depth
- **Buoyancy volume**: Volume of water displaced (determines buoyant force)
- **Body volume**: Total volume of the body
- **Body density**: Average density of the body (mass/volume)
- **Mass**: Total mass of the lifeform
- **Buoyant force (N)**: Upward force from Archimedes' principle = fluid_density × buoyancy_volume × g
- **Weight (N)**: Downward force from gravity = mass × g

## Example Scenarios

### 1. Neutral Lifeform (hovering)
```
Stats:
  Net drijfvermogen: +0.1%

Tooltip:
  Net buoyancy (N): 0.76
  Relative: +0.10%
  Near-floating: Yes          ← Within ±5% tolerance
  Fluid density: 0.970
  Body density: 0.969         ← Very close to fluid density
  Mass: 77.52
  Buoyant force (N): 761.26
  Weight (N): 760.50          ← Almost equal to buoyant force
```

### 2. Heavy Lifeform (sinking)
```
Stats:
  Net drijfvermogen: -48.7%

Tooltip:
  Net buoyancy (N): -372.45
  Relative: -48.72%
  Near-floating: No           ← Outside tolerance
  Fluid density: 0.970
  Body density: 1.940         ← 2x fluid density
  Mass: 155.20
  Buoyant force (N): 761.26
  Weight (N): 1133.71         ← Much greater than buoyant force
```

### 3. Light Lifeform (floating)
```
Stats:
  Net drijfvermogen: +97.4%

Tooltip:
  Net buoyancy (N): 372.45
  Relative: +97.44%
  Near-floating: No           ← Outside tolerance
  Fluid density: 0.970
  Body density: 0.485         ← 0.5x fluid density
  Mass: 38.80
  Buoyant force (N): 761.26
  Weight (N): 388.81          ← Much less than buoyant force
```

## Debug Logging
When a lifeform spawns or its inertial properties refresh, a debug log entry is created:

```
DEBUG evolution.simulation: Lifeform fish_12 @y=150.00 net_buoyancy=1.234 N (rel: 0.002). breakdown: {'fluid_density': 0.97, 'buoyancy_volume': 80.0, 'body_volume': 80.0, 'body_density': 0.969, 'mass': 77.52, 'buoyant_force_N': 761.26, 'weight_N': 760.02, 'buoyancy_offsets': (0.0, 0.0), 'drag_coefficient': 0.25, 'grip_strength': 12.0}
```

## Implementation Details

### Lifeform Attributes
Each lifeform now has these attributes (set by `_compute_buoyancy_debug()`):
- `net_buoyancy` (float): Net buoyant force in Newtons
- `relative_buoyancy` (float): Ratio of net buoyancy to weight
- `is_near_floating` (bool): True if within tolerance threshold
- `buoyancy_debug` (dict): Complete breakdown of all physics values

### Tolerance Criteria for "Near-Floating"
A lifeform is marked as near-floating if **either** condition is true:
1. **Relative tolerance**: `abs(relative_buoyancy) ≤ 0.05` (within ±5% of weight)
2. **Absolute tolerance**: `abs(net_buoyancy) ≤ max(0.02 * weight, 0.5)` (within ±0.5N or ±2% of weight, whichever is larger)

This dual-threshold approach ensures both small and large lifeforms can be detected as near-floating.

### Graceful Degradation
If a lifeform doesn't have buoyancy diagnostics (e.g., older save files):
- The stat displays "n/a"
- No tooltip is shown
- No errors or crashes occur
- Uses `getattr(lifeform, 'relative_buoyancy', 0.0)` and `hasattr()` checks

## Benefits

### For Developers
- **Debug physics issues**: Quickly identify buoyancy problems in lifeforms
- **Validate balance**: Ensure creatures behave as intended in water
- **Performance insights**: Monitor how body composition affects movement

### For Players
- **Understand behavior**: See why some creatures sink or float
- **Strategic decisions**: Choose creatures with desired buoyancy profiles
- **Educational**: Learn about Archimedes' principle and fluid dynamics

## Testing
New tests in `tests/test_lifeform_buoyancy.py` validate:
- ✅ Neutral buoyancy calculation and detection
- ✅ Heavy bodies correctly marked as not near-floating
- ✅ Light bodies correctly marked as not near-floating
- ✅ All tolerance thresholds work correctly

## Related Files
- `evolution/entities/lifeform.py` - Diagnostic computation
- `evolution/rendering/lifeform_inspector.py` - UI display
- `evolution/world/ocean_physics.py` - Physics calculations
- `tests/test_lifeform_buoyancy.py` - Test coverage

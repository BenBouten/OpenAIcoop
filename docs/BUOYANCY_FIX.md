# Buoyancy Fix - Implementation Summary

## Problem Statement (Dutch)
De levensvormen in de ocean physics simulatie vertonen continu een positief drijfvermogen van +13,6. Dit resulteert erin dat ze niet actief lijken te zwemmen, en ze vertonen geen pogingen om hun drijfvermogen te neutraliseren. Daarnaast wordt er geen zoekpatroon of vluchtgedrag geobserveerd.

## Problem Statement (English)
The lifeforms in the ocean physics simulation exhibit continuous positive buoyancy of +13.6. This results in them not appearing to actively swim, and they show no attempts to neutralize their buoyancy. Additionally, no search pattern or escape behavior is observed.

## Root Cause Analysis

### Issue 1: Excessive Buoyancy Bias Values
The `buoyancy_bias` values in `evolution/body/modules.py` were set to unrealistically high values:

**Before:**
- TrunkCore: +6.0
- CephalonHead: +2.0
- HydroFin: +5.0
- TailThruster: -4.0
- SensorPod: +1.0

**Typical Lifeform Total (Before):**
- Minimal (core + head + 2 fins + thruster): +14.0
- Maximal (core + head + 4 fins + thruster + 2 sensors): +24.0

This massive positive bias created a continuous upward force that overwhelmed any active swimming attempts.

### Issue 2: Lack of Active Buoyancy Compensation
While the physics system had mechanisms for fins to provide lift based on `y_direction`, there was no AI logic to actively detect and compensate for net buoyancy. Lifeforms would passively drift instead of actively swimming to maintain depth.

## Solution Implementation

### Fix 1: Reduced Buoyancy Bias Values

**After:**
- TrunkCore: +0.5 (reduced by 12x)
- CephalonHead: +0.2 (reduced by 10x)
- HydroFin: +0.3 (reduced by 16.7x)
- TailThruster: -0.3 (reduced by 13.3x)
- SensorPod: +0.1 (reduced by 10x)

**Typical Lifeform Total (After):**
- Minimal: +1.0
- Maximal: +1.8

This creates a manageable buoyancy bias that can be actively counteracted through swimming.

### Fix 2: Active Buoyancy Compensation in AI

Added `_buoyancy_compensation_vector()` function in `evolution/entities/ai.py`:

```python
def _buoyancy_compensation_vector(lifeform: "Lifeform") -> Vector2:
    """Compute a vertical steering force to actively counteract net buoyancy.
    
    This makes lifeforms actively swim to maintain depth instead of passively drifting.
    """
    relative_buoyancy = getattr(lifeform, "relative_buoyancy", 0.0)
    is_near_floating = getattr(lifeform, "is_near_floating", False)
    
    # If near neutral buoyancy, no compensation needed
    if is_near_floating or abs(relative_buoyancy) < 0.02:
        return Vector2()
    
    # Check if lifeform has fins to counteract buoyancy
    fin_count = getattr(lifeform, "fin_count", 0)
    lift_per_fin = getattr(lifeform, "lift_per_fin", 0.0)
    
    if fin_count == 0 or lift_per_fin == 0.0:
        # No fins: use weak vertical thrust
        compensation_strength = min(0.3, abs(relative_buoyancy) * 0.4)
        return Vector2(0.0, math.copysign(compensation_strength, relative_buoyancy))
    
    # With fins: stronger active compensation
    # Positive relative_buoyancy → swim down (positive Y)
    # Negative relative_buoyancy → swim up (negative Y)
    compensation_strength = min(0.8, abs(relative_buoyancy) * 1.2)
    return Vector2(0.0, math.copysign(compensation_strength, relative_buoyancy))
```

**Integration:**
The function is called in `update_brain()` between `_avoid_recent_positions()` and `_depth_bias_vector()`, ensuring buoyancy compensation is applied before depth preference steering.

## Behavioral Impact

### Before Fix:
1. Lifeforms passively float upward due to +13.6 to +24.0 net buoyancy
2. No active swimming to counteract drift
3. Search and escape behaviors ineffective due to constant upward drift
4. Fins not utilized for depth control

### After Fix:
1. Lifeforms maintain depth through active swimming
2. Small buoyancy bias (+1.0 to +1.8) is actively compensated
3. Search and escape behaviors work correctly with realistic movement
4. Fins actively used to counteract buoyancy and maintain depth
5. Near-neutral lifeforms don't waste energy on unnecessary compensation

## Test Coverage

### 1. Module Value Tests (`test_buoyancy_fix.py`)
- Validates all module buoyancy_bias values in reasonable range (-1.0 to 1.0)
- Verifies typical lifeform configurations have manageable total bias (< 3.0)
- **Status: ✅ All tests pass**

### 2. AI Behavior Tests (`test_buoyancy_compensation.py`)
- Positive buoyancy compensation (floating → swim down)
- Negative buoyancy compensation (sinking → swim up)
- Neutral buoyancy (no compensation needed)
- No fins scenario (weaker compensation)
- Small buoyancy ignored (< 2% threshold)
- High buoyancy capped at 0.8 strength
- **Status: ✅ All tests pass**

## Physics Integration

The fix integrates seamlessly with existing ocean physics:

1. **Buoyancy Calculation** (`lifeform.py:753-820`):
   - Computes `net_buoyancy` and `relative_buoyancy` based on physics_body
   - Determines `is_near_floating` using tolerance thresholds

2. **Fluid Dynamics** (`ocean_physics.py:135-219`):
   - Applies buoyancy acceleration: `(fluid_density * buoyancy_volume * g) / mass`
   - Applies buoyancy bias: `buoyancy_acc += buoyant_bias * g * 0.25`
   - Integrates fin lift forces: `lift_force = lift_per_fin * fin_count * lift_signal`

3. **AI Steering** (`ai.py:48-154`):
   - Combines buoyancy compensation with other behaviors (threat, pursuit, group, depth bias)
   - Converts to `y_direction` which drives fin lift in ocean physics

## Expected Simulation Behavior

After this fix, lifeforms should exhibit:

✅ **Active Swimming**: Constant fin movement to maintain depth  
✅ **Realistic Movement**: Natural swimming patterns with depth control  
✅ **Search Behavior**: Proper wandering and searching for food/partners  
✅ **Escape Behavior**: Effective fleeing from threats without upward drift  
✅ **Depth Preference**: Following locomotion profile depth bias (shallow/deep)  
✅ **Energy Efficiency**: Minimal compensation for near-neutral buoyancy  

## Files Changed

1. `evolution/body/modules.py` - Reduced buoyancy_bias values
2. `evolution/entities/ai.py` - Added buoyancy compensation function
3. `tests/test_buoyancy_fix.py` - Module value validation tests
4. `tests/test_buoyancy_compensation.py` - AI behavior tests
5. `docs/BUOYANCY_FIX.md` - This documentation

## Conclusion

The continuous positive buoyancy issue has been resolved through a two-pronged approach:

1. **Reducing excessive buoyancy bias values** to realistic levels (1.0-1.8 total instead of 14-24)
2. **Adding active AI compensation** to make lifeforms swim to maintain depth

This creates realistic ocean behavior where lifeforms actively swim using their fins to counteract buoyancy and maintain their preferred depth, enabling proper search patterns, escape behaviors, and natural swimming dynamics.

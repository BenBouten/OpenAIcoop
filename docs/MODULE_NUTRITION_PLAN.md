# Module-Based Nutrition System - Implementation Plan

## Overview
Implement a system where each body module has its own nutrition value and can be individually consumed/damaged.

## Status: **PHASE 3 COMPLETE** ✅

## Features
1. **Module Nutrition Values** ✅ - Each module type has edible value
2. **Selective Consumption** - Creatures can eat specific modules
3. **Combat Limb Loss** - Severe damage can remove modules
4. **Realistic Carcass Rendering** - Show actual body shape when dead

## Implementation Steps

### Phase 1: Module Nutrition ✅ COMPLETE
- [x] Add `nutrition_value` field to `ModuleStats`
- [x] Create helper function to calculate nutrition from mass + type
- [x] Test: Verify nutrition calculation works
- [x] Test: All existing tests still pass (21 tests passing)

**Results:**
- `nutrition_value` field added to ModuleStats
- `calculate_module_nutrition(mass, module_type)` function created
- 11 new tests in `test_module_nutrition.py` - all passing ✅
- All existing tests still pass (10 tests) ✅
- Ready for Phase 2!

### Phase 2: Carcass Body Preservation ✅ COMPLETE
- [x] Create `advanced_carcass.py` with `DecomposingCarcass` class
- [x] Update `DecomposingCarcass.__init__` to accept `body_graph` and `body_geometry`
- [x] Update `Lifeform.handle_death()` to pass body data to carcass
- [x] Implement module-based rendering for carcasses (using `render_modular_body`)
- [x] Test: Dead creatures show their actual shape (verified via `test_body_preservation`)

**Results:**
- Created `evolution/world/advanced_carcass.py`
- Implemented full decomposition logic + modular rendering
- Updated `Lifeform` to use new system
- Verified with tests
- Ready for Phase 3!

### Phase 3: Module Consumption for Carcasses ✅ COMPLETE
- [x] Track which modules remain in carcass (`consumed_modules` set)
- [x] Implement `consume_module(module_key)` method
- [x] Calculate nutrition based on specific module eaten
- [x] Update rendering to hide consumed modules
- [x] Test: Eating specific modules from carcass

### Phase 4: Combat Limb Damage/Loss
- [ ] Track module damage in `Lifeform.limb_damage`
- [ ] Implement severe damage threshold (>80% = module lost)
- [ ] Remove modules from `body_graph` when destroyed
- [ ] Recalculate stats when module is lost
- [ ] Visual indication of damaged/missing modules
- [ ] Test: Combat can destroy limbs

### Phase 5: Eating Living Creatures
- [ ] Implement `bite_module()` for targeted attacks
- [ ] Allow consumption while creature is alive (gruesome!)
- [ ] Balance: Make this difficult/risky
- [ ] Test: Predator can bite off prey limb

## Technical Details

### Nutrition Calculation
```python
def calculate_module_nutrition(mass: float, module_type: str) -> float:
    base_nutrition = mass * 10.0  # 10 nutrition per kg
    
    multipliers = {
        "core": 1.5,      # Organs - energy rich
       "muscle": 1.3,    # Protein rich  
        "mouth": 0.8,     # Teeth - less edible
        "armor": 0.6,     # Scales - tough
        # ... etc
    }
    
    return base_nutrition * multipliers.get(module_type, 1.0)
```

### Module Tracking in Carcass
```python
class DecomposingCarcass:
    def __init__(self, ..., body_graph, body_geometry):
        self.body_graph = body_graph  # Original body
        self.consumed_modules = set()  # Keys of eaten modules
        self.module_nutrition = {}  # Pre-calculated per module
        
    def consume_module(self, module_key: str) -> float:
        if module_key in self.consumed_modules:
            return 0.0
        
        module = self.body_graph.get_module(module_key)
        nutrition = module.stats.nutrition_value
        
        self.consumed_modules.add(module_key)
        self.decomposition_progress += 0.05  # Eating speeds decay
        
        return nutrition
```

### Rendering with Missing Modules
```python
def draw(self, surface, offset):
    # Only render modules NOT in consumed_modules
    visible_modules = [
        m for m in self.body_graph.iter_modules()
        if m.key not in self.consumed_modules
    ]
    
    render_modular_body(
        visible_modules,
        color_override=self.gray_color,
        ...
    )
```

## Benefits

### Gameplay
- **Strategic Feeding**: Choose nutritious organs over tough armor
- **Scavenging Realism**: Pick clean a carcass bone by bone
- **Combat Depth**: Target specific limbs to disable enemies
- **Visual Feedback**: See exactly what's been eaten

### Biological Realism
- Different tissues have different nutritional value
- Organs vs muscle vs bone
- Predators can be selective feeders
- Carcass decomposition shows actual damage

## Challenges

1. **Performance**: Tracking individual modules per carcass
2. **Balance**: Prevent exploits (eating only cores)
3. **Visual**: Rendering partial bodies cleanly
4. **Physics**: Recalculating stats when modules are lost

## Testing Strategy

Each phase needs dedicated tests:
- `test_module_nutrition.py` - Nutrition calculations
- `test_carcass_consumption.py` - Eating specific modules
- `test_limb_damage.py` - Combat module destruction
- `test_partial_rendering.py` - Visual display

## Next Action

Start with **Phase 1**: Add nutrition_value to ModuleStats and implement calculation function.

This is a smaller, manageable step that doesn't break existing code.

# Evolution Simulation Design Document

## 1. Target Philosophy

The goal is to create a simulation where complex behaviors and ecological dynamics **emerge** from simple, physical rules rather than being scripted.

### Core Pillars

*   **Emergent Behavior**: Creatures should not have hardcoded "roles" (predator/prey) or state machines (Flee/Chase/Mate). Instead, they should have sensory inputs and motor outputs. If a creature eats meat, it becomes a predator because it learns to chase things that move. If it eats plants, it becomes a grazer.
*   **Physics-First Movement**: All movement should be the result of forces (thrust, drag, lift) applied by body parts. No "teleportation" or direct velocity setting.
*   **Energy-Based Reproduction**: Reproduction should be a purely economic decision for the organism: "Do I have enough excess energy to create offspring?" coupled with "Is there a compatible mate nearby?".
*   **Trait-Driven Visuals**: The visual appearance should strictly reflect the underlying genetics and physical state. A creature with high bioluminescence genes should *glow*. A creature with armor should *look* armored.
*   **Generic Biomass**: "Food" is anything with nutritional value. Predation is just "aggressive feeding on a live target". Scavenging is "feeding on a dead target".

## 2. Current Implementation Analysis

### Behavior & AI
*   **Current State**:
    *   **Hybrid Approach**: A neural network (`ai.py`) controls low-level actuation (thrust, turning), but high-level decisions are often hardcoded.
    *   **Hardcoded Logic**: `Lifeform.py` contains explicit logic for `should_seek_food`, `should_seek_partner`, and `_trigger_escape_manoeuvre`.
    *   **Global Knowledge**: `update_targets()` iterates through *all* entities in the world to find the closest ones. This is computationally expensive (O(N^2)) and biologically unrealistic (infinite knowledge).
    *   **Neural Inputs**: Food density (fwd/left/right), depth, energy, neighbor density.
    *   **Neural Outputs**: Thrust (tail/fins), bite intent, luminescence.

### Resources & Reproduction
*   **Current State**:
    *   **Energy Dynamics**: Implemented. Creatures lose energy to move/exist and gain it by eating.
    *   **Reproduction**: Partly Implemented (`reproduction.py`). Sexual reproduction mixes genomes and applies mutations. However, reproducing is not a purely economic decision. It is also not a decision that is made by the brain. Reproduction should also be triggered without the need for a partner.
    *   **Gating**: Reproduction is gated by hardcoded checks (`can_reproduce`): Age > Maturity and Energy > Threshold.

### Movement
*   **Current State**:
    *   **Physics-Based**: `Lifeform` calculates drag, mass, and thrust. `ai.py` outputs thrust commands.
    *   **Overrides**: There are "escape" and "wander" modes that seem to override or bypass pure neural control in some cases (e.g., `_trigger_escape_manoeuvre` sets a specific vector).

### Visuals
*   **Current State**:
    *   **Modular Rendering**: `modular_lifeform_renderer.py` and `modular_renderer.py` draw creatures based on their `BodyGraph`.
    *   **Procedural Animation**: Tentacles and spines animate based on thrust and movement, which is excellent.
    *   **Missing Features**: **Bioluminescence is not rendered.** The brain outputs `lum_intensity`, but the renderer does not use this value to alter the creature's appearance (e.g., glowing, brightness).

## 3. Key Pain Points & Gap Analysis

| Feature | Target Philosophy | Current Implementation | Gap |
| :--- | :--- | :--- | :--- |
| **Target Selection** | Sensory-based (vision cones, local queries). | Global iteration of all entities. | **High**. Creatures have "god mode" knowledge of nearest targets. |
| **Decision Making** | Fully neural/emergent. | Hardcoded state overrides (Hungry -> Seek Food). | **High**. The brain suggests actions, but the code forces modes. |
| **Predation** | Emergent (bite what moves). | `prefers_meat` / `prefers_plants` flags. | **Medium**. `BiomassTarget` abstraction exists but diet flags still drive logic. |
| **Visuals** | 1:1 State reflection. | Bioluminescence ignored. | **Medium**. Visual feedback loop for communication is broken. |
| **Performance** | Scalable (Spatial Partitioning). | O(N^2) neighbor checks. | **High**. Simulation slows down with population growth. |

## 4. Recommendations

1.  **Remove Global Knowledge**: Replace `update_targets` with a spatial grid query that only returns entities within `vision_range`.
2.  **Unshackle the Brain**: Remove `should_seek_food` / `should_seek_partner` overrides. Feed "hunger" and "reproductive_urge" (hormones) as inputs to the brain and let it decide what to do.
3.  **Implement Bioluminescence**: Pass `lum_intensity` to the renderer and use it to adjust the brightness/glow of the creature (or specific modules).
4.  **Unified "Bite" Interface**: Ensure `feeding.py` treats all biomass identically, with only physical properties (hardness, size) distinguishing them.

# Module Viewer Tool

A standalone interactive tool for testing and visualizing lifeform body graphs with modular structures.

## Purpose

This tool allows developers to:
- **Visualize body graphs**: See how modules are connected in a hierarchical structure
- **Test module configurations**: Add and remove modules interactively
- **Debug rendering**: Verify that module rendering works correctly before integrating into the simulation
- **Experiment with designs**: Quickly prototype different creature body layouts

## Usage

### Interactive Mode

Run the viewer in interactive mode to manipulate the body graph in real-time:

```bash
python tools/module_viewer.py
```

### Screenshot Mode

Generate a screenshot of the current body graph without opening a window:

```bash
python tools/module_viewer.py --screenshot output.png
```

Headless mode uses SDL's dummy driver, so you can run screenshots in CI or when no display is attached. Combine with `--pose sketch` to export the reference creature:

```bash
python tools/module_viewer.py --pose sketch --screenshot docs/images/sketch.png
```

### Custom Window Size

Specify custom window dimensions:

```bash
python tools/module_viewer.py --width 1600 --height 900
```

## Controls

When running in interactive mode, use these keyboard controls:

### Module Management
- **1**: Add a fin (left)
- **2**: Add a fin (right)
- **3**: Add a thruster module
- **4**: Add a sensor module
- **5**: Add a head module
- **D**: Remove the last added module
- **R**: Reset to default creature

### Animation
- **SPACE**: Toggle animation on/off
- **+/-**: Increase/decrease animation speed

### Window
- **Q** or **ESC**: Quit the viewer

## What You'll See

The viewer displays:

1. **Body Graph Visualization**: 
   - Modules rendered as colored ellipses
   - Module types distinguished by color (based on `MODULE_RENDER_STYLES`)
   - Connections between modules shown as curved lines
   - Module labels beneath each component
   - Attachment-aware polygons with tapered fin/tentacle outlines
   - Convex hull "skin" drawn around the core body (limbs excluded)
   - Bridges between attachment points so limbs visibly connect to the torso
   - Optional debug overlay showing joints/axes (toggle with `J`)

2. **Statistics Panel**:
   - Number of modules
   - Total mass (kg)
   - Total volume (m³)
   - Total thrust capability (N)
   - Drag area (m²)
   - Energy cost (W)

3. **Controls Reference**: On-screen list of available keyboard shortcuts

4. **Animation State**: Shows whether animation is enabled and current speed

## Module Types

The viewer supports adding these module types:

- **Core** (TrunkCore): Main torso providing power distribution
- **Head** (CephalonHead): Sensory organ with vision and cognition bonuses
- **Fin** (HydroFin): Flexible fin for aquatic locomotion
- **Thruster** (TailThruster): Powerful axial propulsion
- **Sensor** (SensorPod): Detection apparatus for environmental awareness

## Technical Details

#### Rendering
The viewer reuses the same rendering code from the main simulation:
- Module colors from `evolution.rendering.modular_palette`
- Attachment-driven polygons and convex hull skin from `evolution.rendering.modular_renderer`
- Physics aggregation from `evolution.body.body_graph`
- Test creature builders from `evolution.physics.test_creatures`
- Debug overlay toggle (`J`) to hide or show joint markers

#### Layout & Animation
- Modules inherit positions directly from the `BodyGraph` transforms so attachment points line up.
- Limb outlines are custom tapered polygons; cores/head/torso use ellipse-derived outlines.
- A lightweight spring solver (`_apply_physics`) simulates torque on joints, matching the planned sim behavior.

### Physics Integration
When modules are added or removed:
1. The body graph is updated
2. Physics body is rebuilt using `build_physics_body()`
3. Layout is recomputed
4. Statistics are recalculated

## Examples

### Default Creature
The viewer starts with a default "fin swimmer" prototype that includes:
- 1x Core module
- 1x Head module
- 2x Fin modules (left and right)
- 1x Thruster module

### Adding Sensors
Press **4** multiple times to add sensor modules to available attachment points.

### Testing Symmetry
Add fins with **1** and **2** to see how bilateral symmetry affects the layout and statistics.

## Troubleshooting

### No Display Available
In headless environments, use screenshot mode:
```bash
python tools/module_viewer.py --screenshot test.png
```

### Module Won't Add
If a module can't be added, it means:
- No compatible attachment points are available
- All attachment points are occupied
- Module constraints prevent attachment

Check the console output for details about why a module couldn't be added.

## Integration with Development Workflow

### Before Creating New Modules
1. Use the viewer to test existing module rendering
2. Verify colors and visual styles are correct
3. Check that statistics are calculated properly

### After Modifying Rendering Code
1. Generate screenshots with `--screenshot` before and after changes
2. Compare images to verify rendering changes
3. Test different module combinations

### When Designing New Creatures
1. Use the viewer to prototype body layouts
2. Experiment with module arrangements
3. Check physics statistics for balance
4. Export screenshots for documentation

## Related Files

- `evolution/body/body_graph.py`: Body graph data structure
- `evolution/body/modules.py`: Module definitions
- `evolution/rendering/modular_palette.py`: Visual styling
- `evolution/physics/test_creatures.py`: Test creature builders
- `evolution/physics/physics_body.py`: Physics aggregation

## Future Enhancements

Potential improvements to the viewer:
- Save/load body graph configurations to JSON
- Export body graph as DNA profiles
- Show attachment point constraints
- Highlight invalid module placements
- Add drag-and-drop module placement
- Display joint types and limits
- Show force vectors during animation

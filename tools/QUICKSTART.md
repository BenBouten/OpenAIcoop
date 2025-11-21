# Quick Start Guide: Module Viewer

This guide will help you quickly start using the Module Viewer tool to test and visualize lifeform body graphs.

## Installation

The module viewer uses the same dependencies as the main simulation. If you've already set up the project, you're ready to go!

```bash
# If not already installed
pip install -r requirements.txt
```

## Your First View

### Generate a Screenshot

The quickest way to see the module viewer in action:

```bash
python tools/module_viewer.py --screenshot my_creature.png
```

This creates an image showing the default creature with all its modules laid out.

### Interactive Mode

To experiment with different module configurations:

```bash
python tools/module_viewer.py
```

A window will open showing the body graph visualization.

## Try These Actions

1. **Add a sensor module**: Press `4`
   - Watch as the sensor attaches to an available point
   - See the statistics update in real-time

2. **Add multiple fins**: Press `1` and `2` several times
   - Observe how modules fill available attachment points
   - Notice when no more can be added

3. **Remove modules**: Press `D`
   - Modules are removed in reverse order
   - The layout automatically adjusts

4. **Toggle animation**: Press `SPACE`
   - See the organic movement of the body graph
   - The animation mimics swimming motion

5. **Reset**: Press `R`
   - Return to the default creature configuration
   - Useful for starting fresh

## Understanding the Visualization

### Module Colors

Different module types have distinct colors:
- **Core** (main body): Blue-gray
- **Head**: Lighter blue with an eye
- **Fins**: Blue-green
- **Thrusters**: Orange with flame effect
- **Sensors**: Light colored

### Connections

The curved lines between modules represent physical connections. The thickness indicates:
- **Thick lines**: Core connections
- **Thin lines**: Peripheral connections

### Statistics Panel

On the left side, you'll see:
- **Modules**: Total count of body parts
- **Mass**: Total weight in kg
- **Volume**: Total volume in m³
- **Thrust**: Total propulsion capability in Newtons
- **Drag Area**: Surface area affecting water resistance
- **Energy Cost**: Power consumption in Watts

## Common Use Cases

### 1. Testing a New Module Design

Before adding a new module type to the simulation:

```bash
# View default creature
python tools/module_viewer.py --screenshot before.png

# Edit evolution/body/modules.py to add your module
# Then test it in the viewer

python tools/module_viewer.py --screenshot after.png
```

### 2. Designing a Creature Blueprint

Experiment with different body layouts:

1. Start the viewer: `python tools/module_viewer.py`
2. Add modules in different orders (keys 1-5)
3. Observe the statistics to balance your design
4. Note the configuration you like
5. Take a screenshot for reference

### 3. Debugging Rendering Issues

If modules aren't rendering correctly in the main simulation:

1. Use the viewer to isolate the problem
2. Check that module colors match `MODULE_RENDER_STYLES`
3. Verify attachment points are working
4. Test with screenshot mode for reproducibility

### 4. Documentation and Communication

Generate images for:
- Design documentation
- Bug reports
- Feature proposals
- Teaching materials

```bash
python tools/module_viewer.py --screenshot docs/creature_example.png
```

## Tips and Tricks

### Custom Window Size

For presentations or high-resolution output:

```bash
python tools/module_viewer.py --width 1920 --height 1080 --screenshot hires.png
```

### Rapid Prototyping

Use keyboard shortcuts efficiently:
- Hold `1` or `2` to add multiple fins quickly
- Use `D` repeatedly to strip down to basics
- `R` for instant reset

### Studying Module Attachment

The viewer helps you understand:
- Which modules can attach where
- Attachment point constraints
- How the tree structure grows

Try adding modules in different orders to see how the graph structure changes.

## What's Next?

After getting comfortable with the module viewer:

1. **Explore the code**: Check `tools/module_viewer.py` to see how it works
2. **Customize it**: Modify colors, layout algorithm, or add new features
3. **Create variations**: Save different creature configs as presets
4. **Integrate with workflow**: Use it regularly when developing new features

## Troubleshooting

### "No compatible attachment points"

This means all available attachment points are either:
- Already occupied
- Don't accept the module type you're trying to add
- Have constraints that prevent attachment

Try:
- Removing some modules with `D`
- Resetting with `R`
- Adding a different module type

### Window doesn't appear

If you're on a headless server or without display:
- Use screenshot mode instead: `--screenshot output.png`
- The tool will run in headless mode automatically

### Modules overlap

This is normal with complex graphs. The layout algorithm tries to space them out, but with many modules, some overlap is expected. The animation helps distinguish individual modules.

## Getting Help

- See `tools/README.md` for complete documentation
- Check `evolution/body/modules.py` for module definitions
- Look at `evolution/body/body_graph.py` for graph structure
- Read the main `README.md` for overall project info

## Share Your Creations!

If you design interesting creature configurations, consider:
- Taking screenshots to share
- Documenting the module composition
- Contributing presets to the project
- Reporting any issues you find

Happy experimenting! 🐠

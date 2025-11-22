# Creature Creator Overview

The Creature Creator adds a pauseable overlay to the Alien Ocean simulation that lets players assemble modular creatures, analyse survivability hints, and persist designs as JSON templates.

## Accessing the Lab
- Start the sim normally (`python main.py`).
- Press `C` during gameplay to toggle the Creature Lab overlay. The simulation pauses while the overlay is visible.

## Layout
- **Palette bar (left):** quick buttons for core/head/fin/propulsion/sensor modules. Select a module type here, then click a node in the viewport and press **Add** to attach it. (Drag-and-drop editing arrives in later iterations.)
- **Creature viewport (center):** schematic graph of the current draft. Click a node to highlight it; the next Add action will use that anchor. The root core is larger; lines indicate parent/child links.
- **Survivability panel (right):** lightweight stats: thrust/drag ratio, energy-efficiency proxy, sensor/offence/defence heuristics, plus per-layer buoyancy drift.
- **Toolbar (top-right):** Analyse, Save, Load, and Add buttons. Add attaches the selected palette module to the selected node using the first compatible slot.

## Templates & Storage
- Templates live in `creature_templates/` (configurable via `settings.CREATURE_TEMPLATE_DIR`).
- Save writes `<name>.json`; Load picks the first template for now (UI selection is slated for v2).
- Files are simple JSON dictionaries describing module graphs, making them easy to version-control or mod.

## Survivability Metrics
- Uses `BodyGraph.aggregate_physics_stats()` to derive thrust, drag area, mass, etc.
- Buoyancy heuristics sample each ocean layer (Surface → Abyss) and label drift tendencies.
- Metrics are indicative, not deterministic; they guide tuning before spawning creations into the full sim.

## Roadmap Notes
- Upcoming work: module property editing, drag/drop placement, spawn-from-template buttons, multi-template picker UI, and deeper integration with DNA profiles.

# 🌊 OpenAI Coop Evolution Simulator

An ambitious evolution simulation game set in an alien ocean environment, featuring Newtonian physics, modular creature bodies, genetic algorithms, and retro-inspired graphics reminiscent of *Ecco the Dolphin*.

![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-alpha-orange.svg)

## 🎮 Overview

This project simulates an evolving ecosystem in a vertically-oriented alien ocean world. Creatures with modular bodies compete for resources, reproduce, and evolve over generations. The simulation combines:

- **Newtonian Physics**: Realistic ocean physics with buoyancy, drag, pressure, and currents
- **Modular Bodies**: LEGO-like body composition system with interchangeable modules
- **Genetic Evolution**: DNA-driven traits, mutations, and natural selection
- **Layered World**: Multiple ocean biomes from sunlit surface to pitch-black abyss
- **Retro Aesthetics**: 16-bit inspired pixel art with synthwave color palettes

## ✨ Features

### Core Systems
- 🧬 **DNA & Genetics** - Genetic representation of physical and behavioral traits
- 🐠 **Lifeforms** - Creatures that inherit, mutate, and evolve over generations
- 🌍 **Ocean World** - Layered biomes (Sunlit, Twilight, Midnight, Abyss) with unique properties
- ⚛️ **Physics Engine** - 2D Newtonian simulation with forces, drag, buoyancy, and currents
- ⚡ **Energy System** - Energy consumption tied to movement, growth, and reproduction
- 🧩 **Modular Bodies** - Build creatures from core modules, fins, thrusters, and sensors

### Locomotion Archetypes
1. **Fin-based Swimmers** - Efficient oscillating fins for sustained speed
2. **Jet Propulsion** - Burst speed through water jets
3. **Drift Feeders** - Passive filter feeders riding currents
4. **Benthic Crawlers** - Bottom-dwelling creatures with grip mechanics
5. **Tentacle Locomotion** - Slow but versatile tentacle movement
6. **Electromagnetic Sensors** - Deep-sea hunters with electric sensing

### Advanced Features
- 🧠 **AI Behavior** - Memory, decision-making, group dynamics, and survival instincts
- 🍖 **Food Chain** - Herbivores, carnivores, omnivores, and carrion feeders
- 👥 **Social Dynamics** - Flocking, mating, parental care, and territorial behavior
- 🎨 **Visual Effects** - Caustics, bioluminescence, particle effects
- 📊 **Statistics** - Real-time population metrics and evolution tracking

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (required)
- **pygame 2.5+** for rendering
- **matplotlib 3.7+** (optional, for graphs)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/BenBouten/OpenAIcoop.git
   cd OpenAIcoop
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the simulation**
   ```bash
   python main.py
   ```

### Development Setup

For development with testing and code quality tools:

```bash
pip install -r requirements-dev.txt
pre-commit install  # Optional: set up pre-commit hooks
```

## 🎯 Controls

### Camera
- **Arrow Keys** or **WASD** - Pan camera
- **Mouse Wheel** - Zoom in/out
- **Space** - Follow selected creature

### Simulation
- **P** - Pause/Resume simulation
- **[** / **]** - Decrease/Increase simulation speed
- **R** - Reset simulation
- **ESC** - Exit

### Interaction
- **Left Click** - Select creature (opens inspector panel)
- **Right Click** - Place vegetation (editor mode)
- **Tab** - Toggle UI panels
- **F1** - Toggle debug info
- **F2** - Toggle performance stats

## 🏗️ Architecture

### Project Structure

```
OpenAIcoop/
├── main.py                 # Entry point
├── evolution/              # Main package
│   ├── body/              # Modular body system
│   │   ├── body_graph.py  # Graph data structure
│   │   ├── modules.py     # Module definitions
│   │   └── attachment.py  # Joint & attachment logic
│   ├── config/            # Configuration
│   │   ├── settings.py    # Runtime settings
│   │   └── constants.py   # Fixed constants
│   ├── dna/               # Genetics system
│   │   ├── genes.py       # Gene definitions
│   │   ├── factory.py     # DNA → Body conversion
│   │   ├── blueprints.py  # Starting genomes
│   │   ├── mutation.py    # Mutation logic
│   │   └── selection.py   # Natural selection
│   ├── entities/          # Game entities
│   │   ├── lifeform.py    # Main creature class
│   │   ├── ai.py          # AI behavior
│   │   ├── movement.py    # Movement physics
│   │   ├── locomotion.py  # Locomotion profiles
│   │   ├── combat.py      # Combat system
│   │   └── reproduction.py # Breeding logic
│   ├── physics/           # Physics engine
│   │   ├── physics_body.py # Physics properties
│   │   ├── vector_math.py  # Vector utilities
│   │   └── controllers.py  # Physics controllers
│   ├── rendering/         # Visualization
│   │   ├── camera.py      # Camera system
│   │   ├── draw_lifeform.py # Creature rendering
│   │   ├── effects.py     # Visual effects
│   │   └── stats_window.py # HUD
│   ├── simulation/        # Game loop
│   │   ├── loop.py        # Main loop
│   │   ├── bootstrap.py   # World initialization
│   │   ├── state.py       # Simulation state
│   │   └── environment.py # Environmental updates
│   ├── systems/           # ECS-style systems
│   │   ├── events.py      # Event management
│   │   ├── stats.py       # Statistics tracking
│   │   └── player.py      # Player controller
│   └── world/             # World generation
│       ├── world.py       # World class
│       ├── ocean_world.py # Ocean-specific world
│       ├── ocean_physics.py # Fluid physics
│       ├── biomes.py      # Biome definitions
│       ├── vegetation.py  # Plant life
│       └── carcass.py     # Carrion system
├── tests/                 # Test suite
├── docs/                  # Documentation
│   └── ALIEN_OCEAN_DESIGN.md
└── logs/                  # Runtime logs (generated)
```

### Key Design Patterns

- **Entity-Component**: Lifeforms composed of modular components
- **Factory Pattern**: DNA → Body Graph conversion
- **State Machine**: AI behavior states
- **Observer Pattern**: Event system for notifications
- **Strategy Pattern**: Different locomotion strategies

## 🧬 Modular Body System

The simulation uses a graph-based body composition system where creatures are built from modules:

### Module Types

1. **Core Modules** - Central body structure
   - `TrunkCore`: Main body with 5 attachment points
   
2. **Head Modules** - Sensory and feeding
   - `CephalonHead`: Advanced sensory suite
   
3. **Propulsion Modules** - Movement
   - `HydroFin`: Oscillating fins for swimming
   - `TailThruster`: Jet propulsion bursts
   
4. **Sensory Modules** - Environmental awareness
   - `SensorPod`: Visual/electromagnetic sensors

### Example Body Graph

```
       TrunkCore (root)
      /    |    |    \
    Fin  Fin  Head  Thruster
             /         \
          Sensor      Sensor
```

Each module contributes:
- **Mass & Volume** - Affects buoyancy and inertia
- **Drag Profile** - Determines water resistance
- **Energy Cost** - Maintenance requirements
- **Thrust/Grip** - Movement capabilities
- **Sensory Range** - Perception abilities

## 🌊 Ocean Physics

The simulation models realistic underwater physics:

### Fluid Dynamics
- **Buoyancy**: `F_b = ρ_fluid * V * g` (Archimedes' principle)
- **Drag**: `F_d = 0.5 * ρ * v² * C_d * A` (quadratic drag)
- **Pressure**: Increases 1 bar per 10m depth
- **Currents**: Layer-specific flow fields

### Ocean Layers

| Layer | Depth | Light | Pressure | Density | Temperature |
|-------|-------|-------|----------|---------|-------------|
| **Surface** | 0-200m | 100% | 1-20 bar | Low | Warm |
| **Sunlit** | 200-800m | 60-40% | 20-80 bar | Medium | Moderate |
| **Twilight** | 800-2000m | 20-5% | 80-200 bar | High | Cool |
| **Midnight** | 2000-4000m | <5% | 200-400 bar | Higher | Cold |
| **Abyss** | 4000-6000m | 0% | 400-600 bar | Highest | Near-freezing |

Each layer affects:
- Energy consumption rates
- Sensor effectiveness
- Available food sources
- Mutation rates (near radioactive vents)

## 📊 Evolution Mechanics

### DNA Structure

Creatures carry a genome with:
- **Module Genes**: Body composition blueprint
- **Trait Genes**: Behavioral parameters
- **Development Plan**: Growth stages
- **Constraints**: Mass limits, nerve capacity

### Mutation Types

1. **Structural Mutations**
   - Add/remove body modules
   - Change attachment points
   - Modify module parameters

2. **Parametric Mutations**
   - Size adjustments
   - Color variations
   - Energy efficiency tweaks

3. **Behavioral Mutations**
   - AI decision weights
   - Aggression levels
   - Social tendencies

### Natural Selection

Fitness determined by:
- **Survival** - Reaching maturity age
- **Energy Efficiency** - Metabolic cost vs. food intake
- **Reproduction Success** - Number of viable offspring
- **Hydrodynamics** - Movement efficiency in fluid

## 🛠️ Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=evolution --cov-report=html

# Run specific test file
pytest tests/test_dna_factory.py

# Run only fast tests
pytest -m "not slow"
```

### Code Quality

```bash
# Format code
black evolution/ tests/

# Lint code
ruff check evolution/ tests/

# Type checking
mypy evolution/

# Run all checks
pre-commit run --all-files
```

### Adding New Modules

1. Define module in `evolution/body/modules.py`:
```python
class MyNewModule(BodyModule):
    def __init__(self):
        super().__init__(
            key="my_module",
            mass=10.0,
            volume=12.0,
            energy_cost=2.0,
            # ... other properties
        )
```

2. Register in factory (`evolution/dna/factory.py`):
```python
DEFAULT_MODULE_FACTORIES["my_module"] = MyNewModule
```

3. Add tests in `tests/test_modules.py`

### Adding New Biomes

1. Define in `evolution/world/biomes.py`:
```python
@dataclass
class MyBiome(BiomeRegion):
    name: str = "My Biome"
    depth_range: tuple = (1000, 2000)
    # ... properties
```

2. Integrate into world generation

## 📖 Documentation

- **[Design Document](docs/ALIEN_OCEAN_DESIGN.md)** - Comprehensive vision and roadmap
- **[Code Analysis](CODE_ANALYSIS_REPORT.md)** - Current state and improvement plan
- **API Docs** - Coming soon

## 🤝 Contributing

Contributions are welcome! Areas needing help:

- 🧪 **Testing** - Expand test coverage (currently ~9%)
- 📚 **Documentation** - API docs, tutorials, examples
- 🐛 **Bug Fixes** - See [issues](https://github.com/BenBouten/OpenAIcoop/issues)
- ✨ **Features** - New modules, biomes, AI behaviors
- 🎨 **Art** - Retro pixel art sprites and effects

### Contribution Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run code quality checks (`pre-commit run --all-files`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to your branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by **Ecco the Dolphin** (Sega Genesis/CD)
- Physics concepts from **Navier-Stokes equations**
- Evolution mechanics inspired by **genetic algorithms**
- Visual style influenced by **80's synthwave** aesthetic
- Ocean biome research from marine biology literature

## 📞 Contact

- **Author**: Ben Bouten
- **GitHub**: [@BenBouten](https://github.com/BenBouten)
- **Issues**: [GitHub Issues](https://github.com/BenBouten/OpenAIcoop/issues)

## 🗺️ Roadmap

### Current Status: **Alpha v0.1**

- [x] Core physics engine
- [x] Modular body system
- [x] Basic genetics & evolution
- [x] Ocean world generation
- [x] AI behavior framework
- [ ] Comprehensive testing (in progress)
- [ ] Performance optimization
- [ ] Save/load system
- [ ] Replay system
- [ ] Complete retro visual effects

### Upcoming Milestones

**v0.2 - Infrastructure** (Current)
- [ ] 80% test coverage
- [ ] CI/CD pipeline
- [ ] Performance profiling
- [ ] Configuration system

**v0.3 - Polish**
- [ ] Complete retro aesthetic
- [ ] Sound effects & music
- [ ] Tutorial system
- [ ] Improved UI/UX

**v1.0 - Release**
- [ ] Stable gameplay
- [ ] Complete documentation
- [ ] Performance optimizations
- [ ] Community features

---

**Star ⭐ this repo if you find it interesting!**

Made with 💙 for evolution simulation enthusiasts

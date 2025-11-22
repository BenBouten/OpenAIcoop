# Quick Start Guide for Developers

A rapid-fire guide to get you developing on OpenAI Coop Evolution Simulator in under 5 minutes.

## ⚡ Super Quick Start

```bash
# Clone and enter
git clone https://github.com/BenBouten/OpenAIcoop.git
cd OpenAIcoop

# Setup environment
python3.12 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install and run
pip install -r requirements.txt
python main.py
```

## 🧪 Development Mode

```bash
# Install dev tools
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black evolution/ tests/

# Lint code
ruff check evolution/ tests/

# Type check
mypy evolution/
```

## 🎮 Common Commands

### Running the Simulation
```bash
python main.py                           # Normal mode
EVOLUTION_DEBUG_LOG_LEVEL=DEBUG python main.py  # Debug mode
```

### Testing
```bash
pytest                                   # All tests
pytest tests/test_dna_factory.py         # Specific file
pytest -v                                # Verbose
pytest --cov=evolution                   # With coverage
pytest -m "not slow"                     # Skip slow tests
```

### Code Quality
```bash
# Format everything
black evolution/ tests/

# Lint and auto-fix
ruff check --fix evolution/ tests/

# Sort imports
isort evolution/ tests/

# Type check
mypy evolution/

# Run all checks
pre-commit run --all-files
```

## 🏗️ Project Structure Quick Reference

```
evolution/
├── body/          # Modular creatures (BodyGraph, modules, joints)
├── dna/           # Genetics (genes, mutations, blueprints)
├── entities/      # Lifeforms, AI, movement, combat
├── physics/       # Newtonian physics, ocean dynamics
├── rendering/     # Pygame rendering, camera, UI
├── simulation/    # Game loop, state management
├── world/         # Ocean generation, biomes
└── systems/       # Events, stats, notifications
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point |
| `evolution/simulation/loop.py` | Main game loop (1,514 LOC) |
| `evolution/entities/lifeform.py` | Creature logic (1,334 LOC) |
| `evolution/entities/ai.py` | AI behavior (1,465 LOC) |
| `evolution/body/body_graph.py` | Modular body system |
| `evolution/dna/factory.py` | DNA → Body conversion |
| `evolution/config/settings.py` | Configuration constants |

## 🔧 Configuration

Runtime settings load in layers: defaults ← YAML config (`configs/*.yaml`) ← environment ← CLI.

- Update `configs/default.yaml` or point to a custom file with `--config path/to/file`.
- Env variables (`EVOLUTION_WORLD_WIDTH=6000`) override config values.
- CLI flags like `--world-width 6400 --fps 45` override everything.
- Invalid combinations (e.g., `n_lifeforms` > `max_lifeforms`, out-of-range FPS) raise early with helpful errors.
 
## 🎮 Controls

| Key | Action |
|-----|--------|
| **Arrow Keys/WASD** | Pan camera |
| **Mouse Wheel** | Zoom |
| **P** | Pause/Resume |
| **[** / **]** | Speed down/up |
| **Left Click** | Select creature |
| **R** | Reset simulation |
| **F1** | Toggle debug info |
| **ESC** | Exit |

## 🐛 Debugging

### Enable Debug Logging
```bash
export EVOLUTION_DEBUG_LOG_LEVEL=DEBUG
python main.py
# Check logs/simulation_debug.log
```

### Common Issues

**pygame not found**:
```bash
pip install pygame
```

**Tests fail**:
```bash
# Install test dependencies
pip install -r requirements-dev.txt
```

**Import errors**:
```bash
# Run from project root
cd /path/to/OpenAIcoop
python main.py
```

## 🧬 Adding New Features

### New Body Module
1. Define in `evolution/body/modules.py`
2. Register in `evolution/dna/factory.py`
3. Add tests in `tests/test_modules.py`

### New AI Behavior
1. Add decision logic in `evolution/entities/ai.py`
2. Update state machine
3. Test with different scenarios

### New Biome
1. Define in `evolution/world/biomes.py`
2. Add to world generator
3. Configure layer properties

## 📊 Monitoring

### View Statistics
- Press **Tab** to toggle UI panels
- **Stats Window** shows population metrics
- **Inspector Panel** shows creature details

### Check Performance
```bash
# Run with profiling
python -m cProfile main.py > profile.txt

# View FPS in debug mode
EVOLUTION_DEBUG_LOG_LEVEL=DEBUG python main.py
```

## 🔗 Useful Links

- **Design Doc**: [docs/ALIEN_OCEAN_DESIGN.md](docs/ALIEN_OCEAN_DESIGN.md)
- **Analysis Report**: [CODE_ANALYSIS_REPORT.md](CODE_ANALYSIS_REPORT.md)
- **Full README**: [README.md](README.md)
- **Contributing**: [CONTRIBUTING.md](CONTRIBUTING.md)

## 💡 Quick Tips

1. **Use virtual environment** - Keeps dependencies isolated
2. **Run tests often** - Catch bugs early
3. **Format before commit** - Run `black` and `ruff`
4. **Check type hints** - Run `mypy` for type safety
5. **Read design doc** - Understand the vision
6. **Start small** - Fix a bug or add tests first

## 🚀 Ready to Contribute?

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-feature`
3. Make changes
4. Run tests: `pytest`
5. Format: `black evolution/ tests/`
6. Commit: `git commit -m "feat: add my feature"`
7. Push: `git push origin feature/my-feature`
8. Open a Pull Request

---

**Questions?** Open an [issue](https://github.com/BenBouten/OpenAIcoop/issues) or [discussion](https://github.com/BenBouten/OpenAIcoop/discussions)!

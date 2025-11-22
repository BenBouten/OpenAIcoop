# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive project documentation (README.md, CONTRIBUTING.md)
- Dependency management (requirements.txt, requirements-dev.txt, pyproject.toml)
- Code quality tooling configuration (Ruff, Black, mypy, isort)
- GitHub Actions CI/CD pipeline
- Code analysis and improvement report
- MIT License
- .gitignore for Python projects
- Module viewer upgrades: attachment-aware hull rendering, tapered fin outlines, headless screenshot mode, `--pose sketch`, debug overlay toggle, and limb attachment fixes
- Simulation now reuses the modular renderer so viewer geometry matches in-game lifeforms

### Changed
- Improved project structure documentation

## [0.1.0] - 2024-11-18

### Added
- Initial modular body system with BodyGraph
- DNA and genetics system
- Ocean physics simulation with multiple biomes
- AI behavior system with memory and decision-making
- Newtonian physics engine
- Pygame-based rendering
- Multiple locomotion archetypes (fin swimmers, jet propulsion, etc.)
- Combat and reproduction systems
- Vegetation and food chain
- Carrion and nutrient cycling
- Event and notification systems
- Statistics tracking

### Core Modules
- `evolution.body`: Modular body composition system
- `evolution.dna`: Genetic algorithms and mutations
- `evolution.entities`: Lifeforms, AI, movement, combat
- `evolution.physics`: Newtonian physics and controllers
- `evolution.rendering`: Visualization and UI
- `evolution.simulation`: Game loop and world management
- `evolution.world`: Ocean generation and biomes

[Unreleased]: https://github.com/BenBouten/OpenAIcoop/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BenBouten/OpenAIcoop/releases/tag/v0.1.0

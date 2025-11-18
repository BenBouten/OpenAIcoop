# Contributing to OpenAI Coop Evolution Simulator

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 🤝 Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Respect differing viewpoints and experiences

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/OpenAIcoop.git
cd OpenAIcoop
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks (optional but recommended)
pre-commit install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

## 📋 Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=evolution --cov-report=html

# Run specific test file
pytest tests/test_dna_factory.py

# Run only unit tests
pytest -m unit

# Run only fast tests (exclude slow tests)
pytest -m "not slow"
```

### Code Quality Checks

```bash
# Format code with black
black evolution/ tests/

# Sort imports with isort
isort evolution/ tests/

# Lint with ruff
ruff check evolution/ tests/

# Type check with mypy
mypy evolution/

# Run all checks at once
pre-commit run --all-files
```

### Running the Simulation

```bash
# Run from project root
python main.py

# With debug logging
EVOLUTION_DEBUG_LOG_LEVEL=DEBUG python main.py
```

## 📝 Contribution Guidelines

### Code Style

- **Follow PEP 8** with line length of 100 characters
- **Use type hints** for function signatures
- **Add docstrings** for public functions and classes
- **Format with Black** before committing
- **Keep functions focused** - extract large functions into smaller ones

Example:
```python
from __future__ import annotations

def calculate_buoyancy(
    volume: float,
    fluid_density: float,
    gravity: float = 9.81
) -> float:
    """Calculate buoyancy force using Archimedes' principle.
    
    Args:
        volume: Volume of the submerged object in m³
        fluid_density: Density of the fluid in kg/m³
        gravity: Gravitational acceleration in m/s² (default: 9.81)
    
    Returns:
        Buoyancy force in Newtons
    
    Raises:
        ValueError: If volume or density is negative
    """
    if volume < 0 or fluid_density < 0:
        raise ValueError("Volume and density must be non-negative")
    
    return volume * fluid_density * gravity
```

### Testing

- **Write tests** for all new functionality
- **Aim for 80%+ coverage** for new code
- **Use pytest fixtures** for common test data
- **Test edge cases** and error conditions
- **Use descriptive test names**

Example:
```python
def test_buoyancy_calculation_with_valid_inputs() -> None:
    """Buoyancy should equal volume * density * gravity."""
    force = calculate_buoyancy(volume=10.0, fluid_density=1000.0)
    assert abs(force - 98100.0) < 0.01

def test_buoyancy_raises_on_negative_volume() -> None:
    """Should raise ValueError for negative volume."""
    with pytest.raises(ValueError, match="non-negative"):
        calculate_buoyancy(volume=-5.0, fluid_density=1000.0)
```

### Commit Messages

Use conventional commits format:

```
type(scope): brief description

Longer explanation if needed.

Fixes #123
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(physics): add pressure gradient calculation

fix(ai): prevent division by zero in steering behavior

docs(readme): update installation instructions

test(dna): add tests for mutation edge cases
```

## 🎯 What to Contribute

### High Priority

- **Tests** - Expand coverage (currently ~9%)
- **Bug Fixes** - Check [issues](https://github.com/BenBouten/OpenAIcoop/issues)
- **Documentation** - API docs, tutorials, examples
- **Performance** - Profile and optimize bottlenecks

### Feature Areas

- **New Body Modules** - Add creatures parts (fins, sensors, etc.)
- **New Biomes** - Create ocean environments
- **AI Behaviors** - Implement new decision-making strategies
- **Visual Effects** - Add retro-style effects
- **Sound Effects** - Implement audio (synthwave style)

### Good First Issues

Look for issues tagged with `good first issue` or `help wanted`.

## 🔍 Code Review Process

1. **Submit PR** with clear description
2. **Link related issues** using "Fixes #123"
3. **Wait for CI checks** to pass (tests, linting)
4. **Address feedback** from reviewers
5. **Squash commits** if requested
6. **Merge** once approved

### PR Checklist

- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Code formatted with Black
- [ ] No linting errors from Ruff
- [ ] Type hints added/updated
- [ ] Docstrings added/updated
- [ ] CHANGELOG updated (if applicable)
- [ ] Documentation updated (if applicable)

## 🏗️ Project Structure

Key directories:

```
evolution/
├── body/          # Modular body system
├── dna/           # Genetics and evolution
├── entities/      # Lifeforms and AI
├── physics/       # Physics engine
├── rendering/     # Visualization
├── simulation/    # Game loop
├── world/         # World generation
└── systems/       # Supporting systems
```

## 📚 Resources

- **Design Doc**: [ALIEN_OCEAN_DESIGN.md](docs/ALIEN_OCEAN_DESIGN.md)
- **Analysis Report**: [CODE_ANALYSIS_REPORT.md](CODE_ANALYSIS_REPORT.md)
- **Issues**: [GitHub Issues](https://github.com/BenBouten/OpenAIcoop/issues)

## 🐛 Reporting Bugs

Use the bug report template and include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages/stack traces
- Screenshots (if UI-related)

## 💡 Suggesting Features

Use the feature request template and include:

- Clear use case
- Why it's needed
- How it fits the project vision
- Implementation ideas (if any)

## ❓ Questions

- Open a [Discussion](https://github.com/BenBouten/OpenAIcoop/discussions)
- Tag with `question` label

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing! 🎉

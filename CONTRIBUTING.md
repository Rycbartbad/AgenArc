# Contributing to AgenArc

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Rycbartbad/agenarc.git
cd agenarc

# Install with dev dependencies
pip install -e ".[dev]"

# Or using uv
uv sync
```

## Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=agenarc --cov-report=term-missing

# Run specific test file
pytest tests/unit/test_builtin_operators.py -v
```

## Code Quality

```bash
# Lint checking
ruff check agenarc/

# Type checking
mypy agenarc/

# Format checking
ruff format --check agenarc/
```

## Pull Request Process

1. Ensure all tests pass: `pytest tests/`
2. Ensure lint passes: `ruff check agenarc/`
3. Update documentation if adding new features
4. Add tests for new functionality
5. Keep changes focused — one feature/fix per PR

## Commit Style

Follow conventional commits:
- `feat:` — New feature
- `fix:` — Bug fix
- `refactor:` — Code change without feature/fix
- `docs:` — Documentation
- `test:` — Test changes
- `chore:` — Build/config changes

## Architecture Overview

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

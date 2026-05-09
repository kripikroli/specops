# Development Guide

SpecOps uses [**uv**](https://docs.astral.sh/uv/) as its package manager.

## Prerequisites

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Getting Started

```bash
git clone https://github.com/kripikroli/specops-ai.git
cd specops-ai
uv sync          # Creates .venv, installs all deps + dev group
```

## Common Commands

| Task | Command |
|------|---------|
| Install all deps | `uv sync` |
| Add a runtime dependency | `uv add <package>` |
| Add a dev dependency | `uv add --dev <package>` |
| Remove a dependency | `uv remove <package>` |
| Run tests | `uv run pytest` |
| Run tests with coverage | `uv run pytest --cov=src/specops_ai` |
| Lint | `uv run ruff check src/ tests/` |
| Format | `uv run ruff format src/ tests/` |
| Type check | `uv run mypy src/` |
| Run any command in venv | `uv run <cmd>` |
| Run a CLI tool without installing | `uvx <tool>` |
| Build package | `uv build` |
| Publish to PyPI | `uv publish` |
| Update lockfile | `uv lock` |
| Upgrade a dependency | `uv lock --upgrade-package <pkg>` |

## Lockfile

`uv.lock` is committed to the repository. This ensures all contributors and CI get identical dependency versions.

After adding or removing dependencies, `uv.lock` updates automatically. Commit the updated lockfile with your change.

## Python Version

uv manages the Python version. The project requires Python 3.10+. To pin a specific version locally:

```bash
uv python pin 3.12
```

The `.python-version` file is gitignored — each developer can use their preferred minor version.

## CI

GitHub Actions runs on every push to `main` and on PRs:

| Job | What it does | Command |
|-----|-------------|---------|
| **lint** | Ruff check + format | `uv run ruff check src/ tests/ examples/` |
| **typecheck** | mypy strict | `uv run mypy src/` |
| **test** | pytest on 3.10/3.11/3.12 | `uv run pytest --cov=src/specops_ai` |

See `.github/workflows/ci.yml` for the full config.

### Release

Releases are triggered by pushing a version tag:

```bash
git tag v0.1.0
git push --tags
```

This runs tests, builds the wheel, and publishes to PyPI via `.github/workflows/release.yml`.

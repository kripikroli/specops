# Contributing to SpecOps AI

Thank you for your interest in contributing to SpecOps AI! We're building the reliability layer for LLM agents, and every contribution — whether it's a bug fix, a new feature, documentation improvement, or a thoughtful issue — helps make agents more trustworthy in production.

## Table of Contents

- [Philosophy](#philosophy)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Spec-Driven Development](#spec-driven-development)
- [Development Setup](#development-setup)
- [Code Standards](#code-standards)
- [Running Tests](#running-tests)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Code of Conduct](#code-of-conduct)

---

## Philosophy

SpecOps AI follows three guiding principles that shape every contribution:

1. **Spec-first** — Every non-trivial feature starts as a written specification before code is written. This forces clear thinking, creates shared understanding, and makes code review faster.

2. **Framework-agnostic** — The core library has zero framework dependencies. Adapters are optional and auto-detected. We never introduce vendor lock-in.

3. **Production-grade** — This toolkit is designed for real workloads. Low overhead, comprehensive tests, full type safety, and OTel-native observability are non-negotiable.

If your contribution serves these principles, it belongs here.

---

## Getting Started

### Good First Contributions

- 🐛 **Bug fixes** — Check [open issues](https://github.com/kripikroli/specops-ai/issues) labeled `good-first-issue`
- 📖 **Documentation** — Improve docstrings, fix typos, add examples
- 🧪 **Tests** — Increase coverage for edge cases
- 💡 **Ideas** — Open an issue to discuss before building

### Where to Find Work

| Label | Description |
|-------|-------------|
| `good-first-issue` | Great for newcomers — well-scoped, clear requirements |
| `help-wanted` | We'd love community help on these |
| `spec-needed` | Needs a specification before implementation |
| `bug` | Confirmed bugs ready for fixing |

---

## How to Contribute

### Reporting Issues

Open an issue with:
- A clear, descriptive title
- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Python version and OS
- Minimal code example if possible

### Proposing Features

1. Open an issue describing the problem you want to solve
2. Discuss the approach with maintainers
3. Once aligned, write a spec (see below)
4. Implement after spec approval

---

## Spec-Driven Development

Every non-trivial feature follows our spec-driven workflow:

```
Idea → Spec → Review → Implement → Test → Ship
```

### Why Spec-First?

- Forces clear thinking before coding
- Creates shared understanding across contributors
- Produces documentation as a side effect
- Makes code review faster (reviewers already know the intent)
- Enables parallel work (multiple people can implement from one spec)

### Writing a Spec

Create a spec in `docs/specs/` with three parts:

#### 1. Requirements

Define what the system must do using clear, testable language:

```markdown
## Feature: [Name]

### Problem
What problem does this solve?

### Requirements
- The system shall [do X]
- When [condition], the system shall [respond with Y]
- The system shall not [constraint]

### Success Criteria
- How do we know this is done?
```

#### 2. Design

Describe how it will work:

```markdown
## Design: [Feature Name]

### Approach
High-level description of the solution.

### API
Public interface (functions, classes, decorators).

### Trade-offs
What alternatives were considered and why this approach was chosen.
```

#### 3. Tasks

Break implementation into ordered steps:

```markdown
## Tasks: [Feature Name]

### Implementation Steps
1. [ ] Step one — description
2. [ ] Step two — description

### Verification
- How to confirm each step works
```

### Spec Review Process

1. Create a branch: `spec/<feature-name>`
2. Add your spec files to `docs/specs/`
3. Open a PR labeled `spec`
4. Address feedback
5. Once approved, proceed to implementation

---

## Development Setup

We use [**uv**](https://docs.astral.sh/uv/) as our package manager for fast, reproducible builds.

```bash
# Clone the repository
git clone https://github.com/kripikroli/specops-ai.git
cd specops-ai

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (creates .venv automatically)
uv sync

# Verify everything works
uv run pytest
```

### Running Examples

```bash
# Core examples (no API key needed)
uv run examples/plain_agent.py
uv run examples/simulation_demo.py
uv run examples/chaos_demo.py

# Provider examples (requires API key)
cp .env.example .env  # Add your keys
uv run examples/providers/openai/basic_agent.py

# Mock mode (no API key needed)
SPECOPS_EXAMPLE_MODE=mock uv run examples/providers/openai/langgraph_agent.py
```

---

## Code Standards

### Python

- **Python 3.10+** — Use modern syntax (`X | Y` unions, `match` where appropriate)
- **Type annotations** — All parameters and return types annotated
- **Docstrings** — All public functions (Google style)
- **Minimal API surface** — Only export what users need

### Tooling

| Tool | Purpose | Command |
|------|---------|---------|
| **Ruff** | Linting + formatting | `uv run ruff check src/ tests/` |
| **Ruff** | Auto-format | `uv run ruff format src/ tests/` |
| **mypy** | Type checking (strict) | `uv run mypy src/` |
| **pytest** | Test runner | `uv run pytest` |

### File Organization

New code follows this structure:

```
src/specops_ai/
├── <module>.py        # New module (trace, replay, eval, heal, health, simulate, etc.)
├── adapters/          # Framework adapters (optional, auto-detected)
└── __init__.py        # Public API re-exports

tests/
└── test_<module>.py   # Tests mirror source structure
```

### Commit Messages

Use [conventional commits](https://www.conventionalcommits.org/):

```
feat: add circuit breaker to self-healing module
fix: handle async context propagation in trace decorator
docs: update simulation sandbox examples
test: add edge case coverage for replay engine
chore: upgrade ruff to 0.15.x
refactor: simplify RCA graph traversal
```

---

## Running Tests

```bash
# Run full test suite
uv run pytest

# Run with coverage
uv run pytest --cov

# Run a specific test file
uv run pytest tests/test_trace.py

# Run tests matching a pattern
uv run pytest -k "test_replay"

# Full validation (what CI runs)
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest
```

### Test Requirements

- All existing tests must continue to pass (zero regressions)
- New code must have corresponding tests
- Cover happy path + edge cases (empty inputs, None values, timeouts)
- Tests should be fast and isolated (no network calls, no file I/O)

---

## Submitting a Pull Request

### Before You Submit

- [ ] Code follows existing patterns and conventions
- [ ] All public functions have type annotations and docstrings
- [ ] Tests cover happy path and edge cases
- [ ] `uv run pytest` passes
- [ ] `uv run ruff check src/ tests/` passes
- [ ] `uv run mypy src/` passes
- [ ] No unnecessary dependencies added
- [ ] PR references the related issue or spec

### PR Process

1. Create a feature branch from `main`
2. Make your changes (small, focused commits)
3. Push and open a PR
4. Fill in the PR template
5. Address review feedback
6. Maintainer merges when all checks pass

### CI Pipeline

All PRs automatically run:

1. **Lint** — `ruff check` + `ruff format --check`
2. **Type check** — `mypy src/`
3. **Test** — `pytest` on Python 3.10, 3.11, 3.12 with coverage

All checks must pass before merge.

---

## Code of Conduct

We are committed to providing a welcoming and inclusive experience for everyone. All participants are expected to:

- **Be respectful** — Treat everyone with dignity. No harassment, discrimination, or personal attacks.
- **Be constructive** — Offer helpful feedback. Critique ideas, not people.
- **Be collaborative** — We're building something together. Assume good intent.
- **Be patient** — Not everyone has the same experience level. Help others learn.

### Unacceptable Behavior

- Harassment, intimidation, or discrimination of any kind
- Trolling, insulting comments, or personal attacks
- Publishing others' private information without consent
- Any conduct that would be inappropriate in a professional setting

### Enforcement

Violations may result in warnings, temporary bans, or permanent removal from the project. Report issues to the maintainers via [email](mailto:luminding.aaron420@gmail.com) or by opening a private issue.

---

## Questions?

- 💬 Open a [Discussion](https://github.com/kripikroli/specops-ai/discussions) for general questions
- 🐛 Open an [Issue](https://github.com/kripikroli/specops-ai/issues) for bugs or feature requests
- 📖 Check the [README](README.md) for usage examples
- 🗺️ See the [Roadmap](ROADMAP.md) for planned features

---

Thank you for helping make LLM agents more reliable. Every contribution matters. 🛠️

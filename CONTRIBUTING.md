# Contributing to SpecOps

Thank you for your interest in SpecOps! We use **spec-driven development** — every feature begins as a written specification before any code is written.

## Development Workflow

```
1. Idea / Issue
2. Write Spec (requirements → design → tasks)
3. Review Spec (PR against docs/specs/)
4. Implement (code follows the approved spec)
5. Review Code (PR against src/)
6. Ship
```

### Why Spec-First?

- Forces clear thinking before coding
- Creates shared understanding across contributors
- Produces documentation as a side effect
- Makes code review faster (reviewers already know the intent)
- Enables AI agents to assist with implementation

## How to Contribute

### 1. Pick or Propose Work

- Check [open issues](https://github.com/kripikroli/specops-ai/issues) for `good-first-issue` or `help-wanted`
- Or open a new issue describing what you'd like to build

### 2. Write a Spec

Create a branch and add your spec to `docs/specs/`:

```
docs/specs/
├── requirements.md    # What the system must do
├── design.md          # How it will work (architecture)
└── tasks.md           # Ordered implementation steps
```

**Spec templates:**

<details>
<summary>Requirements Template</summary>

```markdown
## Feature: [Name]

### Problem
What problem does this solve?

### Requirements
- FR-1: The system shall...
- FR-2: The system shall...

### Non-Requirements
- What is explicitly out of scope

### Success Criteria
- How do we know this is done?
```
</details>

<details>
<summary>Design Template</summary>

```markdown
## Design: [Feature Name]

### Approach
High-level description of the solution.

### API
Public interface (functions, classes, decorators).

### Internal Architecture
How components interact.

### Trade-offs
What alternatives were considered and why this approach was chosen.
```
</details>

<details>
<summary>Tasks Template</summary>

```markdown
## Tasks: [Feature Name]

### Prerequisites
- What must exist before starting

### Implementation Steps
1. [ ] Step one — description
2. [ ] Step two — description

### Verification
- How to confirm each step works
```
</details>

### 3. Submit Spec PR

Open a PR with your spec files. Label it `spec`. The team reviews the spec before implementation begins.

### 4. Implement

Once the spec is approved:

1. Create a feature branch from `main`
2. Follow the tasks in your spec
3. Write tests alongside implementation
4. Open a PR referencing the spec

## Development Setup

We use [**uv**](https://docs.astral.sh/uv/) as our package manager. See [DEVELOPMENT.md](DEVELOPMENT.md) for full details.

```bash
# Clone
git clone https://github.com/kripikroli/specops-ai.git
cd specops-ai

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (creates .venv automatically)
uv sync

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Type check
uv run mypy src/
```

## Code Standards

- **Python 3.10+** minimum
- **Ruff** for linting and formatting
- **mypy** strict mode for type checking
- **pytest** for all tests
- Docstrings on all public APIs (Google style)
- 80%+ test coverage for new code

## CI Pipeline

All PRs run through GitHub Actions:

1. **Lint** — `ruff check` + `ruff format --check`
2. **Type check** — `mypy src/`
3. **Test** — `pytest` on Python 3.10, 3.11, 3.12 with coverage

PRs must pass all checks before merge. See `.github/workflows/ci.yml`.

## Commit Messages

Use conventional commits:

```
feat: add @trace_agent decorator
fix: handle async context propagation
docs: update Phase 1 spec with token tracking
test: add integration tests for OTel export
```

## Code of Conduct

Be respectful, constructive, and collaborative. We're building tools to make agents reliable — let's be reliable to each other too.

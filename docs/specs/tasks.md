# SpecOps — Task Breakdown

> Version: 0.2 | Status: Active | Last Updated: 2026-05-07

## Phase 0: Project Bootstrap

**Goal:** Professional project structure ready for contributors.

| # | Task | Status | Verification |
|---|------|--------|--------------|
| 0.1 | Initialize repo with MIT license | ✅ Done | LICENSE file exists |
| 0.2 | Create `pyproject.toml` (hatch, ruff, pytest, mypy, uv) | ✅ Done | `uv sync` succeeds |
| 0.3 | Create folder structure (`src/specops/`, `tests/`, `examples/`, `docs/specs/`) | ✅ Done | Directories exist |
| 0.4 | Write README.md | ✅ Done | Renders correctly on GitHub |
| 0.5 | Write ROADMAP.md | ✅ Done | Phases clearly defined |
| 0.6 | Write CONTRIBUTING.md + DEVELOPMENT.md | ✅ Done | Spec workflow + uv commands documented |
| 0.7 | Write specs (requirements, design, tasks) | ✅ Done | `docs/specs/` populated |
| 0.8 | Set up GitHub Actions CI (lint + test) | ⬜ Todo | PR checks pass |
| 0.9 | Create issue templates | ⬜ Todo | Templates appear in GitHub UI |

---

## Phase 1: Core OTel Tracing

**Goal:** Ship `@trace_agent`, `@trace_tool`, `@trace_llm` decorators. Publish v0.1.0.

**Prerequisites:** Phase 0 complete.

### Tasks

| # | Task | Status | Verification |
|---|------|--------|--------------|
| 1.1 | Define semantic conventions (`_constants.py`) | ✅ Done | All `specops.*` attribute keys defined |
| 1.2 | Implement context propagation (`_context.py`) | ✅ Done | ContextVar-based, works across async boundaries |
| 1.3 | Implement `@trace_agent` decorator | ✅ Done | Creates parent span with agent attributes |
| 1.4 | Implement `@trace_tool` decorator | ✅ Done | Creates child span with tool attributes |
| 1.5 | Implement `@trace_llm` decorator | ✅ Done | Creates child span with LLM attributes (model, tokens) |
| 1.6 | Implement adapter system (`adapters.py`) | ✅ Done | BaseAdapter ABC + PlainAdapter + registry |
| 1.7 | Add auto-configuration (`config.py`) | ✅ Done | Reads `OTEL_*` env vars, lazy init, console fallback |
| 1.8 | Public API exports (`__init__.py`) | ✅ Done | All decorators + config importable from `specops` |
| 1.9 | Write unit tests (15 tests) | ✅ Done | `uv run pytest` passes, all 15 green |
| 1.10 | Create example: trace a custom agent | ⬜ Todo | `examples/custom_agent.py` runs |
| 1.11 | Write API documentation (docstrings + docs/) | ⬜ Todo | All public APIs documented |
| 1.12 | Publish to PyPI as v0.1.0 | ⬜ Todo | `pip install specops` works |

---

## Phase 1.5: Framework Adapters + Examples

**Goal:** Concrete adapters for popular frameworks, high-quality examples, updated docs.

**Prerequisites:** Phase 1 core tracing complete.

### Tasks

| # | Task | Status | Verification |
|---|------|--------|--------------|
| 1.5.1 | Convert `adapters.py` to `adapters/` package | ✅ Done | Package imports work |
| 1.5.2 | Implement `LangGraphAdapter` | ✅ Done | Handles StateGraph state, AIMessage, ToolMessage |
| 1.5.3 | Implement `CrewAIAdapter` | ✅ Done | Handles Task objects, kickoff inputs, token_usage |
| 1.5.4 | Implement `AutoGenAdapter` (stub) | ✅ Done | Basic chat pattern support |
| 1.5.5 | Auto-register adapters via `_auto_register()` | ✅ Done | Graceful ImportError handling |
| 1.5.6 | Add optional deps to `pyproject.toml` | ✅ Done | `pip install specops[langgraph]` works |
| 1.5.7 | Create examples (plain, langgraph, crewai, async) | ✅ Done | All 4 examples run |
| 1.5.8 | Update README.md with quickstart examples | ✅ Done | Shows all 3 frameworks |
| 1.5.9 | Update design.md and tasks.md | ✅ Done | Specs reflect current state |

---

## Definition of Done

A task is complete when:

1. Code is written and passes linting (`uv run ruff check`)
2. Type checking passes (`uv run mypy src/`)
3. Tests pass (`uv run pytest`)
4. Documentation is updated
5. PR is reviewed and merged

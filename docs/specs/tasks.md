# SpecOps — Task Breakdown

> Version: 0.1 | Status: Active | Last Updated: 2026-05-07

## Phase 0: Project Bootstrap

**Goal:** Professional project structure ready for contributors.

| # | Task | Status | Verification |
|---|------|--------|--------------|
| 0.1 | Initialize repo with MIT license | ✅ Done | LICENSE file exists |
| 0.2 | Create `pyproject.toml` (hatch, ruff, pytest, mypy) | ✅ Done | `pip install -e ".[dev]"` succeeds |
| 0.3 | Create folder structure (`src/specops/`, `tests/`, `examples/`, `docs/specs/`) | ✅ Done | Directories exist |
| 0.4 | Write README.md | ✅ Done | Renders correctly on GitHub |
| 0.5 | Write ROADMAP.md | ✅ Done | Phases clearly defined |
| 0.6 | Write CONTRIBUTING.md | ✅ Done | Spec workflow documented |
| 0.7 | Write specs (requirements, design, tasks) | ✅ Done | `docs/specs/` populated |
| 0.8 | Set up GitHub Actions CI (lint + test) | ⬜ Todo | PR checks pass |
| 0.9 | Create issue templates | ⬜ Todo | Templates appear in GitHub UI |

---

## Phase 1: Core OTel Tracing

**Goal:** Ship `@trace_agent`, `@trace_tool`, `@trace_llm` decorators. Publish v0.1.0.

**Prerequisites:** Phase 0 complete, CI green.

### Tasks

| # | Task | Status | Verification |
|---|------|--------|--------------|
| 1.1 | Create `src/specops/trace.py` module skeleton | ⬜ Todo | Module importable |
| 1.2 | Implement `@trace_agent` decorator | ⬜ Todo | Creates parent span with agent attributes |
| 1.3 | Implement `@trace_tool` decorator | ⬜ Todo | Creates child span with tool attributes |
| 1.4 | Implement `@trace_llm` decorator | ⬜ Todo | Creates child span with LLM attributes (model, tokens) |
| 1.5 | Implement context propagation for async | ⬜ Todo | Spans nest correctly across `await` boundaries |
| 1.6 | Add auto-configuration (read `OTEL_*` env vars) | ⬜ Todo | Exporter connects without manual setup |
| 1.7 | Write unit tests for all decorators | ⬜ Todo | `pytest` passes, 80%+ coverage |
| 1.8 | Write integration test with in-memory exporter | ⬜ Todo | Spans captured and validated |
| 1.9 | Create example: trace a custom agent | ⬜ Todo | `examples/custom_agent.py` runs |
| 1.10 | Create example: trace a LangChain agent | ⬜ Todo | `examples/langchain_agent.py` runs |
| 1.11 | Write API documentation (docstrings + docs/) | ⬜ Todo | All public APIs documented |
| 1.12 | Publish to PyPI as v0.1.0 | ⬜ Todo | `pip install specops` works |

### Implementation Notes

**Task 1.2 — `@trace_agent` detail:**

```python
# Expected behavior:
@trace_agent(name="my-agent")
async def run(task: str):
    ...

# Creates span:
#   name: "agent:my-agent"
#   attributes: specops.agent.name, specops.agent.task
#   wraps entire function execution
```

**Task 1.4 — `@trace_llm` detail:**

```python
# Must capture:
# - Model name (from decorator arg or response)
# - Input/output token counts (from response metadata)
# - Latency (span duration)
# - Status (success/error)
```

**Task 1.5 — Async context propagation:**

```python
# Must work with:
# - asyncio.gather()
# - asyncio.create_task()
# - Nested async calls
# Uses contextvars to maintain span context
```

---

## Definition of Done

A task is complete when:

1. Code is written and passes linting (`ruff check`)
2. Type checking passes (`mypy --strict`)
3. Tests pass (`pytest`)
4. Documentation is updated
5. PR is reviewed and merged

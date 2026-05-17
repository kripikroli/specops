# 🗺️ SpecOps Roadmap

> Living document. Updated as phases complete.

## Overview

| Phase | Focus | Timeline | Status |
|-------|-------|----------|--------|
| **0** | Project bootstrap & specs | Week 1 | ✅ Done |
| **1** | Core OTel tracing | Weeks 2–3 | ✅ Done |
| **1.5** | Framework adapters + examples | Week 3 | ✅ Done |
| **2** | Replay engine + behavioral eval | Week 4 | ✅ Done |
| **3** | Self-healing + RCA graphs | Week 5 | ✅ Done |
| **4** | Simulation sandbox + coordination | Week 6 | ✅ Done |
| **5** | CLI tooling + dashboards | Weeks 7–9 | 🚧 In Progress |
| **6** | Chaos engineering + regression testing | Weeks 10–11 | ✅ Done |
| **6.5** | Health Score + Shareable Replay | Week 12 | ✅ Done |

---

## Phase 0 — Bootstrap ✅

- [x] Repository setup (MIT license, .gitignore)
- [x] `pyproject.toml` with hatch/ruff/pytest, **uv** as package manager
- [x] README, ROADMAP, CONTRIBUTING
- [x] `docs/specs/` with requirements and design specs
- [x] CI pipeline (lint + test)

## Phase 1 — Core OTel Tracing ✅

- [x] `@trace_agent` decorator — wraps agent functions with OTel spans
- [x] `@trace_tool` decorator — traces tool/function calls
- [x] `@trace_llm` decorator — traces LLM API calls (tokens, latency, model)
- [x] Semantic attributes (`specops.*` namespace)
- [x] Context propagation across async boundaries
- [x] Auto-export to any OTel-compatible backend

## Phase 1.5 — Framework Adapters ✅

- [x] LangGraph adapter (StateGraph, AIMessage, ToolMessage)
- [x] CrewAI adapter (Task objects, token_usage)
- [x] AutoGen adapter (message content, initiate_chat)
- [x] Strands adapter (tool-use agents, model invocations)
- [x] Auto-detection and registration

## Phase 2 — Replay Engine + Eval ✅

- [x] `@replayable` decorator for recording non-deterministic calls
- [x] `recording()` / `replaying()` context managers
- [x] JSON-based session storage
- [x] Deterministic seeding
- [x] Golden-set evaluation (`eval_golden_set`)
- [x] LLM-as-judge (`llm_judge`)

## Phase 3 — Self-Healing + RCA ✅

- [x] `@self_healing` decorator with policy chain
- [x] RetryPolicy (exponential backoff)
- [x] FallbackPolicy (alternative callable)
- [x] EscalatePolicy (human handler)
- [x] PruneMemoryPolicy (context reduction)
- [x] RCA graph builder from OTel spans
- [x] Graphviz DOT export

## Phase 4 — Simulation + Coordination ✅ (v0.2.0)

- [x] `SimulationEnvironment` — sandbox for testing agent behaviors
- [x] `simulation()` context manager
- [x] `@simulate` decorator
- [x] Loop detection, budget enforcement, cascade testing
- [x] Token budget tracking
- [x] `check_consensus()` — multi-agent agreement verification
- [x] `check_memory_integrity()` — state divergence detection
- [x] `check_divergence()` — behavioral drift via edit distance
- [x] Integration with replay, eval, and healing layers
- [x] 120+ tests passing

## Phase 5 — CLI Tooling + Dashboards (In Progress)

- [x] `specops-demo` — browser-based visual examples runner with live streaming
- [ ] `specops-ai eval run` CLI command
- [ ] `specops-ai replay` CLI command
- [ ] `specops-ai sim` CLI for running simulation scenarios
- [ ] Grafana dashboard templates
- [ ] Datadog integration guide
- [ ] HTML report generation for eval results

## Phase 6 — Chaos Engineering + Regression Testing ✅

- [x] Chaos injection: hallucination, infinite loops, memory drift, tool failures, coordination disagreements, cascade failures
- [x] ChaosEngine with detection and self-healing verification
- [x] Behavioral regression testing: record golden runs, detect drift
- [x] `golden()` / `check_regression()` context managers
- [x] `@regression_test` decorator
- [x] Drift detection: step count, step order, tool usage, loops, timing

## Phase 6.5 — Health Score + Shareable Replay ✅ (v0.4.5)

- [x] `compute_health_score()` — weighted 0-100 score from reliability signals
- [x] `@health_check` decorator — auto-check after every agent invocation
- [x] `HealthReport` with grade (A–F), signal breakdown, pass/fail
- [x] `export_replay()` — export sessions as portable JSON with environment + diagnostics
- [x] `import_replay()` — import and replay shared sessions
- [x] `ReplayFile` bundles session, environment, health, chaos, and regression data
- [ ] Community eval datasets
- [ ] Plugin system for custom policies
- [ ] Multi-language support exploration (TypeScript)

---

## Principles

1. **Spec-first** — Every feature starts as a specification
2. **Framework-agnostic** — No vendor lock-in, works with any agent framework
3. **OTel-native** — Built on OpenTelemetry, not a proprietary format
4. **Production-grade** — Designed for real workloads, not just demos
5. **Minimal footprint** — Low overhead, opt-in instrumentation

---

## Release History

| Version | Date | Highlights |
|---------|------|------------|
| v0.4.6 | 2026-05-17 | Visual Demo Runner (`specops-demo`), 30 new tests, browser-based UI |
| v0.4.5 | 2026-05-17 | Health Score engine, Shareable Replay Sessions (export/import) |
| v0.4.0 | 2026-05-10 | Chaos engineering, behavioral regression testing, 250+ tests |
| v0.3.0 | 2026-05-10 | Strands adapter, provider examples, 187 tests at 96% coverage |
| v0.2.0 | 2026-05-08 | Simulation sandbox, multi-agent coordination, 120+ tests |
| v0.1.0 | 2026-05-07 | Core tracing, replay, eval, self-healing, RCA, adapters |

<p align="center">
  <h1 align="center">🛠️ SpecOps</h1>
  <p align="center"><strong>Agent Reliability Kit</strong></p>
  <p align="center">
    Framework-agnostic, OTel-native toolkit for reliable, evaluatable, debuggable, and self-healing LLM agents in production.
  </p>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#features">Features</a> •
  <a href="ROADMAP.md">Roadmap</a> •
  <a href="CONTRIBUTING.md">Contributing</a> •
  <a href="docs/specs/">Specs</a>
</p>

---

## The Problem

LLM agents fail silently. They hallucinate, loop, drift off-task, and degrade without warning. Teams building agentic systems today lack:

- **Observability** — No standardized way to trace agent reasoning, tool calls, and decision paths
- **Evaluation** — No framework-agnostic way to measure if agents actually do what they're supposed to
- **Debugging** — When agents fail, root-cause analysis is guesswork
- **Self-healing** — Agents crash and stay crashed; no recovery patterns exist

Production agent systems need the same reliability engineering that backend services got from OpenTelemetry, circuit breakers, and chaos engineering — but purpose-built for non-deterministic AI workloads.

## Vision

SpecOps is the **robot doctor toolbox** for agentic engineering. It provides:

1. **Structured observability** via OpenTelemetry-native tracing of agent internals
2. **Evaluation harnesses** that work across any agent framework
3. **Debugging tools** that replay and inspect agent decision paths
4. **Self-healing primitives** — retry strategies, fallback chains, and circuit breakers designed for LLM workloads

Framework-agnostic. Works with LangChain, CrewAI, AutoGen, custom agents, or anything that calls an LLM.

## Quickstart

```bash
pip install specops
```

```python
from specops import trace_agent

@trace_agent(name="my-agent")
async def run_agent(task: str):
    # Your agent logic here
    ...
```

> ⚠️ SpecOps is in early development (v0.1.0). APIs will change. See the [Roadmap](ROADMAP.md).

## Features

| Category | Status | Description |
|----------|--------|-------------|
| **OTel Tracing** | 🚧 Phase 1 | Trace agent runs, tool calls, LLM requests with OpenTelemetry spans |
| **Eval Harness** | 📋 Phase 2 | Framework-agnostic evaluation: task completion, faithfulness, tool accuracy |
| **Debug Replay** | 📋 Phase 2 | Record and replay agent sessions for deterministic debugging |
| **Self-Healing** | 📋 Phase 3 | Circuit breakers, retry with backoff, fallback chains for LLM calls |
| **Anomaly Detection** | 📋 Phase 3 | Detect loops, drift, and degradation in real-time |

## Architecture

```
┌─────────────────────────────────────────────┐
│              Your Agent Code                 │
│  (LangChain / CrewAI / Custom / etc.)       │
├─────────────────────────────────────────────┤
│            SpecOps SDK Layer                 │
│  trace · eval · debug · heal                │
├─────────────────────────────────────────────┤
│         OpenTelemetry Protocol               │
│  spans · metrics · logs                      │
├─────────────────────────────────────────────┤
│           Any OTel Backend                   │
│  Jaeger · Grafana · Datadog · etc.          │
└─────────────────────────────────────────────┘
```

## Project Structure

```
specops/
├── src/specops/          # Core library
├── tests/                # Test suite
├── examples/             # Usage examples
├── docs/specs/           # Specifications (requirements, design, tasks)
├── pyproject.toml        # Build config (hatch + ruff + pytest)
└── ROADMAP.md            # Development phases
```

## Contributing

We use **spec-driven development** — every feature starts as a specification before code is written. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

```
Idea → Spec (requirements + design + tasks) → Implementation → Review
```

## License

[MIT](LICENSE)

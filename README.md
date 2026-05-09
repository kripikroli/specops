<p align="center">
  <h1 align="center">🛠️ SpecOps</h1>
  <p align="center"><strong>Agent Reliability Kit</strong></p>
  <p align="center">
    Framework-agnostic, OTel-native toolkit for reliable, evaluatable, debuggable, and self-healing LLM agents in production.
  </p>
</p>

<p align="center">
  <a href="https://pypi.org/project/specops/"><img src="https://img.shields.io/pypi/v/specops?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/specops/"><img src="https://img.shields.io/pypi/pyversions/specops" alt="Python"></a>
  <a href="https://github.com/kripikroli/specops/actions"><img src="https://img.shields.io/github/actions/workflow/status/kripikroli/specops/ci.yml?branch=main" alt="CI"></a>
  <a href="https://codecov.io/gh/kripikroli/specops"><img src="https://img.shields.io/codecov/c/github/specops-kit/specops?color=green" alt="Coverage"></a>
  <a href="https://github.com/kripikroli/specops/blob/main/LICENSE"><img src="https://img.shields.io/github/license/kripikroli/specops" alt="License"></a>
</p>

<p align="center">
  <a href="#getting-started">Getting Started</a> •
  <a href="#features">Features</a> •
  <a href="#simulation-sandbox">Simulation</a> •
  <a href="#multi-agent-coordination">Coordination</a> •
  <a href="ROADMAP.md">Roadmap</a> •
  <a href="CONTRIBUTING.md">Contributing</a>
</p>

---

## The Problem

LLM agents fail silently. They hallucinate, loop, drift off-task, and degrade without warning. Teams building agentic systems today lack:

- **Observability** — No standardized way to trace agent reasoning, tool calls, and decision paths
- **Evaluation** — No framework-agnostic way to measure if agents actually do what they're supposed to
- **Debugging** — When agents fail, root-cause analysis is guesswork
- **Self-healing** — Agents crash and stay crashed; no recovery patterns exist
- **Simulation** — No way to test for emergent failures before they hit production

## Getting Started

### Installation

```bash
pip install specops
```

With framework adapters:

```bash
pip install specops[langgraph]   # LangGraph support
pip install specops[crewai]      # CrewAI support
pip install specops[all]         # All adapters
```

### One-Line Quickstart

```python
from specops import trace_agent

@trace_agent(name="my-agent")
def agent(task: str) -> str:
    return "done"  # Your agent logic — now fully traced via OTel
```

### Trace Any Agent

```python
from specops import trace_agent, trace_tool, trace_llm

@trace_tool(name="search")
def search(query: str) -> list[str]:
    return ["result1", "result2"]

@trace_llm(model="gpt-4o", provider="openai")
def call_llm(prompt: str) -> dict:
    return {"text": "...", "model": "gpt-4o", "input_tokens": 10, "output_tokens": 25}

@trace_agent(name="research-agent")
def agent(task: str) -> str:
    results = search(task)
    return call_llm(f"Summarize: {results}")["text"]
```

### Record & Replay

```python
from specops import replayable, recording, replaying

@replayable
def call_llm(prompt: str) -> str:
    return "..."  # Your LLM call

# Record
with recording(session_id="session-1", seed=42) as session:
    result = call_llm("What is 2+2?")

# Replay deterministically
with replaying("session-1"):
    same_result = call_llm("What is 2+2?")  # Identical output
```

### Self-Healing

```python
from specops import self_healing, RetryPolicy, FallbackPolicy

@self_healing(
    retry=RetryPolicy(max_retries=3, base_delay=0.5),
    fallback=FallbackPolicy(fallback_fn=backup_llm),
)
def call_llm(prompt: str) -> str:
    ...  # Auto-retries, falls back if exhausted
```

### Simulation Sandbox

```python
from specops import simulation

with simulation("loop-test", max_steps=50, loop_threshold=3) as sim:
    for action in agent_actions:
        event = sim.record("my-agent", action)
        if event.anomaly:
            print(f"Detected: {event.anomaly.value}")
    result = sim.stop()
    assert result.passed
```

### Multi-Agent Coordination

```python
from specops import check_consensus, check_divergence, AgentOutput, BehaviorTrace

# Consensus check
result = check_consensus([
    AgentOutput(agent="a", output="yes"),
    AgentOutput(agent="b", output="yes"),
    AgentOutput(agent="c", output="no"),
], quorum=0.6)

# Divergence detection
result = check_divergence([
    BehaviorTrace(agent="a", actions=["search", "summarize", "respond"]),
    BehaviorTrace(agent="b", actions=["search", "summarize", "respond"]),
], max_edit_distance=2)
```

### Evaluation

```python
from specops import eval_golden_set, EvalCase, llm_judge

results = eval_golden_set(
    agent_fn=my_agent,
    cases=[EvalCase(input="2+2", expected="4")],
)

verdict = llm_judge(output, criteria="correctness", judge_fn=my_llm)
```

### RCA Graph

```python
from specops import build_rca_graph, to_dot

graph = build_rca_graph(spans)
print(f"Root causes: {[n.name for n in graph.root_causes]}")
dot_output = to_dot(graph, title="Failure Analysis")
```

> ⚠️ SpecOps is in early development (v0.2.0). APIs may change. See the [Roadmap](ROADMAP.md).

## Features

| Category | Status | Description |
|----------|--------|-------------|
| **OTel Tracing** | ✅ | Trace agent runs, tool calls, LLM requests with OpenTelemetry spans |
| **Replay Engine** | ✅ | Record and replay agent sessions deterministically |
| **Eval Harness** | ✅ | Golden-set comparison + LLM-as-judge for behavioral evaluation |
| **Self-Healing** | ✅ | Retry with backoff, fallback chains, escalation, memory pruning |
| **RCA Graphs** | ✅ | Root-cause analysis from OTel spans, Graphviz DOT export |
| **Simulation Sandbox** | ✅ | Test for loops, drift, cascades, and token overflow in a sandbox |
| **Coordination Checks** | ✅ | Consensus, memory integrity, and divergence detection for multi-agent systems |
| **Framework Adapters** | ✅ | LangGraph, CrewAI, AutoGen adapters (auto-detected) |

## Simulation Sandbox

The simulation sandbox lets you test agent behaviors in a controlled environment before they hit production:

- **Loop detection** — Catch agents stuck repeating the same action
- **Budget enforcement** — Set max steps, duration, and token limits
- **Cascade testing** — Simulate failure propagation across agent pipelines
- **OTel integration** — All simulation events produce spans for analysis

```python
from specops import simulate, SimulationEnvironment

@simulate("my-scenario", max_steps=100, token_budget=10000)
def test_agent(sim: SimulationEnvironment):
    for task in tasks:
        sim.record("agent", task)
        sim.add_tokens(500)
```

## Multi-Agent Coordination

Built-in checks for multi-agent systems:

| Check | Purpose |
|-------|---------|
| `check_consensus()` | Verify agents agree on outputs (configurable quorum) |
| `check_memory_integrity()` | Detect state divergence and stale reads |
| `check_divergence()` | Flag behavioral drift via edit distance |

## Architecture

```
┌─────────────────────────────────────────────┐
│              Your Agent Code                 │
│  (LangChain / CrewAI / Custom / etc.)       │
├─────────────────────────────────────────────┤
│            SpecOps SDK Layer                 │
│  trace · eval · replay · heal · simulate    │
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
│   ├── trace.py          # OTel tracing decorators
│   ├── replay.py         # Record/replay engine
│   ├── eval.py           # Evaluation harness
│   ├── heal.py           # Self-healing policies
│   ├── simulate.py       # Simulation sandbox
│   ├── coordinate.py     # Multi-agent coordination
│   ├── rca.py            # Root-cause analysis
│   └── adapters/         # Framework adapters
├── tests/                # Test suite (120+ tests)
├── examples/             # Usage examples
├── docs/specs/           # Specifications
└── pyproject.toml        # Build config (hatch + ruff + pytest)
```

## Contributing

We use **spec-driven development** — every feature starts as a specification before code is written. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow.

```bash
# Setup
uv sync

# Run tests
uv run pytest

# Lint & format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run mypy src/
```

## License

[MIT](LICENSE)

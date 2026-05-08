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

# Optional framework support
pip install specops[langgraph]
pip install specops[crewai]
pip install specops[all]
```

### Plain Python

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

### LangGraph

```python
from specops import trace_agent, trace_tool

@trace_tool(name="calculator")
def calculator(expr: str) -> str:
    return str(eval(expr))

@trace_agent(name="math-agent", framework="langgraph")
def run_graph(state: dict) -> str:
    # Your StateGraph logic here
    return calculator(state["input"])
```

### CrewAI

```python
from specops import trace_agent, trace_llm

@trace_agent(name="content-crew", framework="crewai")
def run_crew(inputs: dict) -> str:
    # Your Crew(agents=[...], tasks=[...]).kickoff() here
    ...
```

> ⚠️ SpecOps is in early development (v0.2.0). APIs will change. See the [Roadmap](ROADMAP.md).

### Replay & Evaluation

```python
from specops import replayable, recording, replaying, eval_golden_set, EvalCase, llm_judge

@replayable
def call_llm(prompt: str) -> str:
    # Your LLM call here
    return "..."

# Record a session
with recording(session_id="my-session", seed=42) as session:
    result = call_llm("What is 2+2?")

# Replay deterministically
with replaying("my-session"):
    same_result = call_llm("What is 2+2?")  # Identical output

# Golden-set evaluation
results = eval_golden_set(
    agent_fn=my_agent,
    cases=[EvalCase(input="2+2", expected="4")],
)

# LLM-as-judge
verdict = llm_judge(output, criteria="correctness", judge_fn=my_llm)
```

## Features

| Category | Status | Description |
|----------|--------|-------------|
| **OTel Tracing** | ✅ Phase 1 | Trace agent runs, tool calls, LLM requests with OpenTelemetry spans |
| **Replay Engine** | ✅ Phase 3.0 | Record and replay agent sessions deterministically |
| **Eval Harness** | ✅ Phase 3.0 | Golden-set comparison + LLM-as-judge for behavioral evaluation |
| **Self-Healing** | 📋 Phase 4 | Circuit breakers, retry with backoff, fallback chains for LLM calls |
| **Anomaly Detection** | 📋 Phase 4 | Detect loops, drift, and degradation in real-time |

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

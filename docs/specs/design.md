# SpecOps — Design Specification

> Version: 0.1 | Status: Draft | Last Updated: 2026-05-07

## 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────┐
│                  User's Agent Code                    │
└──────────────┬───────────────────────────────────────┘
               │ decorators / context managers
┌──────────────▼───────────────────────────────────────┐
│                 SpecOps SDK                           │
│                                                      │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ │
│  │  Trace   │ │   Eval   │ │ Debug  │ │   Heal   │ │
│  │  Module  │ │  Module  │ │ Module │ │  Module  │ │
│  └────┬─────┘ └────┬─────┘ └───┬────┘ └────┬─────┘ │
│       │             │           │            │       │
│  ┌────▼─────────────▼───────────▼────────────▼────┐  │
│  │              Core Runtime                      │  │
│  │  context · config · registry · events          │  │
│  └────────────────────┬──────────────────────────┘  │
└───────────────────────┼──────────────────────────────┘
                        │ OTel Protocol
┌───────────────────────▼──────────────────────────────┐
│              OTel Collector / Backend                 │
│  Jaeger · Grafana Tempo · Datadog · Honeycomb        │
└──────────────────────────────────────────────────────┘
```

## 2. Module Design

### 2.1 Trace Module (`specops.trace`)

**Purpose:** Instrument agent code with OpenTelemetry spans.

**Public API:**

```python
from specops import trace_agent, trace_tool, trace_llm

@trace_agent(name="researcher")
async def research(query: str) -> str: ...

@trace_tool(name="web-search")
def search(query: str) -> list[str]: ...

@trace_llm(model="gpt-4")
async def call_llm(prompt: str) -> str: ...
```

**Internal Design:**
- Uses `opentelemetry.trace` to create spans
- Decorators are thin wrappers that start/end spans and attach attributes
- Context propagation via `contextvars` for async support
- Auto-detects OTel exporter from environment (`OTEL_EXPORTER_OTLP_ENDPOINT`)

**Span Attributes:**

| Attribute | Type | Example |
|-----------|------|---------|
| `specops.agent.name` | string | `"researcher"` |
| `specops.agent.task` | string | `"find papers on X"` |
| `specops.tool.name` | string | `"web-search"` |
| `specops.llm.model` | string | `"gpt-4"` |
| `specops.llm.tokens.input` | int | `150` |
| `specops.llm.tokens.output` | int | `500` |
| `specops.llm.latency_ms` | float | `1200.5` |

### 2.2 Eval Module (`specops.eval`)

**Purpose:** Run agents against test cases and score results.

**Public API:**

```python
from specops.eval import EvalSuite, Case, metrics

suite = EvalSuite(
    agent=my_agent,
    cases=[
        Case(input="summarize X", expected="contains key points"),
    ],
    metrics=[metrics.task_completion, metrics.faithfulness],
)

results = await suite.run()
```

**Internal Design:**
- `EvalSuite` orchestrates running agent on each case
- Metrics are functions: `(input, output, expected) -> float`
- Results stored as structured data (exportable to JSON/CSV)
- pytest integration via `assert results.score("task_completion") > 0.8`

### 2.3 Debug Module (`specops.debug`)

**Purpose:** Record and replay agent sessions.

**Public API:**

```python
from specops.debug import record, replay, diff

# Record
session = await record(agent, input="do X")

# Replay with mocked LLM
result = await replay(session, mock_llm=cached_responses)

# Compare runs
changes = diff(session_a, session_b)
```

**Internal Design:**
- Recording captures all span data + LLM request/response pairs
- Replay injects recorded LLM responses via mock provider
- Diff compares span trees structurally (added/removed/changed steps)

### 2.4 Heal Module (`specops.heal`)

**Purpose:** Recovery primitives for LLM agent failures.

**Public API:**

```python
from specops.heal import retry, fallback, circuit_breaker

@retry(max_attempts=3, backoff="exponential")
@fallback(chain=["gpt-4", "gpt-3.5-turbo", "cached"])
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def call_model(prompt: str) -> str: ...
```

**Internal Design:**
- `retry`: Wraps calls with configurable backoff (exponential, jitter)
- `fallback`: Ordered list of alternatives; tries next on failure
- `circuit_breaker`: Tracks failures per provider; opens circuit after threshold
- Loop detection: Monitors span patterns for repetition; raises `AgentLoopError`

## 3. Configuration

```python
# specops.toml or environment variables
[specops]
service_name = "my-agent-service"
export_endpoint = "http://localhost:4317"

[specops.heal]
default_retry_attempts = 3
circuit_breaker_threshold = 5
```

## 4. Development Tooling

| Tool | Purpose | Command |
|------|---------|---------|
| **uv** | Package manager & virtualenv | `uv sync`, `uv add`, `uv run` |
| **hatch** | Build backend | via `uv build` |
| **ruff** | Lint + format | `uv run ruff check`, `uv run ruff format` |
| **mypy** | Type checking | `uv run mypy src/` |
| **pytest** | Testing | `uv run pytest` |

All commands are run through `uv run` to ensure the correct virtualenv and dependencies. The `uv.lock` file is committed for reproducible installs across all environments.

## 5. Trade-offs & Decisions

| Decision | Rationale |
|----------|-----------|
| Decorators over middleware | Lower barrier to entry; works with any function |
| OTel-native over custom format | Leverage existing ecosystem; no vendor lock-in |
| Async-first | Most agent frameworks are async; sync support via wrapper |
| No framework plugins in core | Keep core minimal; plugins live in separate packages |
| Python-only initially | Largest agent ecosystem; expand later based on demand |

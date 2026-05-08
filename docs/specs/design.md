# SpecOps — Design Specification

> Version: 0.2 | Status: Active | Last Updated: 2026-05-07

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
│  │  context · config · adapters · constants       │  │
│  └────────────────────┬──────────────────────────┘  │
└───────────────────────┼──────────────────────────────┘
                        │ OTel Protocol
┌───────────────────────▼──────────────────────────────┐
│              OTel Collector / Backend                 │
│  Jaeger · Grafana Tempo · Datadog · Honeycomb        │
└──────────────────────────────────────────────────────┘
```

## 2. Phase 1 — Trace Module Design

### 2.1 Semantic Conventions (`specops._constants`)

All attribute keys follow the `specops.*` namespace to avoid collision with upstream OTel semconv.

```python
# Agent attributes
AGENT_NAME = "specops.agent.name"
AGENT_TASK = "specops.agent.task"
AGENT_FRAMEWORK = "specops.agent.framework"
AGENT_STEP = "specops.agent.step"
AGENT_DECISION = "specops.agent.decision"

# Tool attributes
TOOL_NAME = "specops.tool.name"
TOOL_ARGS = "specops.tool.args"
TOOL_RESULT = "specops.tool.result"

# LLM attributes
LLM_MODEL = "specops.llm.model"
LLM_PROVIDER = "specops.llm.provider"
LLM_TOKENS_INPUT = "specops.llm.tokens.input"
LLM_TOKENS_OUTPUT = "specops.llm.tokens.output"
LLM_TEMPERATURE = "specops.llm.temperature"
LLM_SEED = "specops.llm.seed"

# Coordination / multi-agent
COORDINATION_EVENT = "specops.coordination.event"
MEMORY_ACCESS = "specops.memory.access"

# Replay support
REPLAY_SEED = "specops.replay.seed"
REPLAY_SESSION_ID = "specops.replay.session_id"
```

### 2.2 Decorator API (`specops.trace`)

#### `@trace_agent`

```python
def trace_agent(
    name: str,
    *,
    framework: str = "plain",
) -> Callable:
    """Trace an agent function as a root/parent span.

    Args:
        name: Human-readable agent name (becomes span name prefix).
        framework: Agent framework identifier (plain, langgraph, crewai, autogen).

    The first positional arg of the decorated function is captured as `specops.agent.task`.
    """
```

**Span produced:** `agent:{name}` with attributes `specops.agent.name`, `specops.agent.task`, `specops.agent.framework`.

#### `@trace_tool`

```python
def trace_tool(
    name: str | None = None,
) -> Callable:
    """Trace a tool/function call as a child span.

    Args:
        name: Tool name. Defaults to the function's __name__.

    Captures serialized args as `specops.tool.args` and return value as `specops.tool.result`
    (truncated to 1024 chars).
    """
```

**Span produced:** `tool:{name}` with attributes `specops.tool.name`, `specops.tool.args`, `specops.tool.result`.

#### `@trace_llm`

```python
def trace_llm(
    model: str = "",
    *,
    provider: str = "",
    capture_result: bool = False,
) -> Callable:
    """Trace an LLM invocation as a child span.

    Args:
        model: Model identifier (e.g. "gpt-4o"). Can be overridden at runtime via return dict.
        provider: Provider name (e.g. "openai").
        capture_result: If True, store the LLM response text as a span attribute.

    If the decorated function returns a dict with keys `input_tokens`, `output_tokens`,
    `model`, those values are used to populate span attributes.
    """
```

**Span produced:** `llm:{model}` with attributes `specops.llm.model`, `specops.llm.provider`, `specops.llm.tokens.input`, `specops.llm.tokens.output`.

### 2.3 Context Propagation (`specops._context`)

```python
from contextvars import ContextVar

# Current agent span context — allows child spans to nest under the active agent
_current_agent_ctx: ContextVar[Context | None] = ContextVar("specops_agent_ctx", default=None)

def get_current_context() -> Context | None:
    """Return the active SpecOps trace context (for nesting child spans)."""

def set_current_context(ctx: Context) -> Token:
    """Set the active context. Returns a token for reset."""
```

Uses `opentelemetry.context` for span propagation. The `contextvars` layer ensures correct behavior across `asyncio.gather()`, `create_task()`, and nested awaits.

### 2.4 Adapter System (`specops.adapters`)

Adapters normalize framework-specific metadata into SpecOps semantic attributes.

```python
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    """Base class for framework adapters."""

    @abstractmethod
    def extract_task(self, args: tuple, kwargs: dict) -> str:
        """Extract the agent task from function arguments."""

    @abstractmethod
    def extract_llm_metadata(self, result: Any) -> dict[str, Any]:
        """Extract LLM metadata (tokens, model) from a call result."""

    @abstractmethod
    def extract_tool_metadata(self, args: tuple, kwargs: dict, result: Any) -> dict[str, Any]:
        """Extract tool metadata from a call."""


class PlainAdapter(BaseAdapter):
    """Default adapter for plain Python agent code."""
    ...
```

#### Concrete Adapters (Phase 1.5)

| Adapter | Framework | Key Patterns |
|---------|-----------|--------------|
| `PlainAdapter` | Plain Python | First arg = task, dict results |
| `LangGraphAdapter` | LangGraph | StateGraph state dicts, AIMessage, ToolMessage |
| `CrewAIAdapter` | CrewAI | Task objects, kickoff inputs, token_usage |
| `AutoGenAdapter` | AutoGen (stub) | Message content, initiate_chat args |

Adapters are auto-registered on import via `_auto_register()`. Framework libraries are optional — adapters gracefully degrade if the framework is not installed.

Adapters are selected via the `framework=` parameter on `@trace_agent` or auto-detected.

### 2.5 Configuration (`specops.config`)

```python
def configure(
    service_name: str | None = None,
    endpoint: str | None = None,
    *,
    enabled: bool = True,
) -> None:
    """Configure the SpecOps tracer.

    Falls back to environment variables:
      - OTEL_SERVICE_NAME (default: "specops")
      - OTEL_EXPORTER_OTLP_ENDPOINT (default: None → console exporter)
      - SPECOPS_ENABLED (default: "true")

    If no OTLP endpoint is set, uses ConsoleSpanExporter for local dev.
    """
```

Auto-configures on first decorator use (lazy init). No manual `configure()` call required for basic usage.

### 2.6 Public API (`specops.__init__`)

```python
from specops.trace import trace_agent, trace_tool, trace_llm
from specops.config import configure
from specops.adapters import BaseAdapter, PlainAdapter

__all__ = [
    "trace_agent",
    "trace_tool",
    "trace_llm",
    "configure",
    "BaseAdapter",
    "PlainAdapter",
]
```

## 3. Modules (Phase 2+)

### 3.1 Eval Module (`specops.eval`) — Phase 2

(Unchanged from v0.1 design)

### 3.2 Debug Module (`specops.debug`) — Phase 2

(Unchanged from v0.1 design)

### 3.3 Heal Module (`specops.heal`) — Phase 3

(Unchanged from v0.1 design)

## 4. Development Tooling

| Tool | Purpose | Command |
|------|---------|---------|
| **uv** | Package manager & virtualenv | `uv sync`, `uv add`, `uv run` |
| **hatch** | Build backend | via `uv build` |
| **ruff** | Lint + format | `uv run ruff check`, `uv run ruff format` |
| **mypy** | Type checking | `uv run mypy src/` |
| **pytest** | Testing | `uv run pytest` |

## 5. Trade-offs & Decisions

| Decision | Rationale |
|----------|-----------|
| Decorators over middleware | Lower barrier to entry; works with any function |
| OTel-native over custom format | Leverage existing ecosystem; no vendor lock-in |
| Async-first with sync fallback | Most agent frameworks are async; `inspect.iscoroutinefunction` to auto-detect |
| `contextvars` for propagation | Works with asyncio natively; no monkey-patching |
| Lazy tracer init | Zero-config: first decorator use triggers setup |
| Adapter pattern for frameworks | Keeps core generic; framework specifics isolated |
| Truncate tool args/results to 1024 chars | Prevents span bloat from large payloads |
| Console exporter as default | Works out of the box for local dev; OTLP when endpoint is set |
| No Pydantic in core | Minimal deps; use dataclasses/TypedDict for internal types |

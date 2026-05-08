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

## 3. Phase 3.0 — Replay Engine + Behavioral Evaluation

### 3.1 Replay Engine (`specops.replay`)

The replay engine records non-deterministic function outputs (LLM calls, tool calls with external side effects) during a session, stores them, and replays them deterministically.

#### 3.1.1 Architecture

```
┌─────────────────────────────────────────────┐
│           @replayable decorator             │
│  (wraps functions to record/replay calls)   │
├─────────────────────────────────────────────┤
│            ReplaySession                     │
│  (manages recording/replaying state)        │
├─────────────────────────────────────────────┤
│            ReplayStore                       │
│  (JSON file persistence of recorded calls)  │
└─────────────────────────────────────────────┘
```

#### 3.1.2 Core Types

```python
@dataclass
class RecordedCall:
    """A single recorded function call."""
    func_name: str
    args_hash: str          # SHA-256 of serialized args for matching
    result: Any             # The captured return value
    timestamp: str          # ISO-8601
    call_index: int         # Ordering within session

@dataclass
class ReplaySession:
    """A recorded session containing all captured calls."""
    session_id: str
    seed: int
    recorded_at: str
    calls: list[RecordedCall]
```

#### 3.1.3 `@replayable` Decorator

```python
def replayable(fn: F) -> F:
    """Mark a function as replayable.

    In RECORD mode: executes normally, captures result.
    In REPLAY mode: returns the previously recorded result (matched by func_name + args_hash).
    """
```

#### 3.1.4 Context Manager

```python
@contextmanager
def recording(session_id: str | None = None, seed: int | None = None) -> Iterator[ReplaySession]:
    """Context manager to record all @replayable calls within the block."""

@contextmanager
def replaying(session: ReplaySession | str | Path) -> Iterator[ReplaySession]:
    """Context manager to replay from a stored session (path or object)."""
```

#### 3.1.5 Storage

Sessions are stored as JSON files. Default location: `.specops/replays/{session_id}.json`.

```python
class ReplayStore:
    """Persist and load replay sessions."""
    def __init__(self, base_dir: Path = Path(".specops/replays")): ...
    def save(self, session: ReplaySession) -> Path: ...
    def load(self, session_id: str) -> ReplaySession: ...
    def list_sessions(self) -> list[str]: ...
```

#### 3.1.6 Deterministic Seeding

When entering a `recording()` or `replaying()` context, the engine sets `random.seed(seed)` to ensure any random-dependent logic is reproducible. The seed is stored in the session and propagated as the `specops.replay.seed` OTel attribute.

### 3.2 Behavioral Evaluation Harness (`specops.eval`)

#### 3.2.1 Golden-Set Evaluation

```python
@dataclass
class EvalCase:
    """A single evaluation test case."""
    input: Any
    expected: Any
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalResult:
    """Result of evaluating one case."""
    case: EvalCase
    actual: Any
    passed: bool
    score: float            # 0.0–1.0
    details: str = ""

def eval_golden_set(
    agent_fn: Callable,
    cases: list[EvalCase],
    *,
    comparator: Callable[[Any, Any], float] | None = None,
    threshold: float = 0.8,
) -> list[EvalResult]:
    """Run agent against golden-set cases and score results."""
```

#### 3.2.2 LLM-as-Judge

```python
@dataclass
class JudgeVerdict:
    """Verdict from an LLM judge."""
    score: float            # 0.0–1.0
    reasoning: str
    criteria: str

def llm_judge(
    agent_output: Any,
    *,
    criteria: str,
    judge_fn: Callable[[str], str],
    context: str = "",
) -> JudgeVerdict:
    """Use an LLM to judge agent output quality.

    Args:
        agent_output: The output to evaluate.
        criteria: What to evaluate (e.g. "correctness", "helpfulness").
        judge_fn: A callable that takes a prompt and returns LLM text response.
        context: Optional context about the task.
    """
```

#### 3.2.3 Integration with Replay

Evaluation can use replay sessions to ensure deterministic re-evaluation:

```python
def eval_with_replay(
    agent_fn: Callable,
    cases: list[EvalCase],
    replay_dir: Path,
    **kwargs,
) -> list[EvalResult]:
    """Run evaluation using replay for deterministic results."""
```

### 3.3 Heal Module (`specops.heal`) — Phase 4

(Deferred to future phase)

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

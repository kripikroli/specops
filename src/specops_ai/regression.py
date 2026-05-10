"""Automated Behavioral Regression Testing for SpecOps AI.

Records 'golden' agent runs and detects behavioral drift in future runs,
even when final outputs appear identical. Compares step sequences, tool usage,
timing patterns, and coordination behavior.
"""

from __future__ import annotations

import functools
import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# --- Core Types ---


@dataclass
class BehaviorStep:
    """A single behavioral step in an agent run."""

    name: str
    step_type: str  # "tool_call", "llm_call", "action", "memory_access"
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GoldenRun:
    """A recorded golden agent run capturing full behavior."""

    run_id: str
    agent_name: str
    task: str
    steps: list[BehaviorStep] = field(default_factory=list)
    final_output: Any = None
    total_duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Drift:
    """A detected behavioral drift between golden and current run."""

    drift_type: (
        str  # "step_count", "step_order", "tool_usage", "loop", "timing", "output"
    )
    severity: str  # "low", "medium", "high"
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegressionResult:
    """Result of comparing a current run against a golden run."""

    passed: bool
    golden_run_id: str
    drifts: list[Drift] = field(default_factory=list)
    current_steps: list[BehaviorStep] = field(default_factory=list)
    score: float = 1.0  # 1.0 = identical, 0.0 = completely different

    @property
    def has_regressions(self) -> bool:
        """True if any high-severity drifts detected."""
        return any(d.severity == "high" for d in self.drifts)


# --- Context State ---


class _RegressionState:
    """Mutable state for the current regression recording context."""

    def __init__(self, run_id: str, agent_name: str, task: str) -> None:
        self.run_id = run_id
        self.agent_name = agent_name
        self.task = task
        self.steps: list[BehaviorStep] = []
        self.start_time = time.time()


_regression_ctx: ContextVar[_RegressionState | None] = ContextVar(
    "specops_regression_ctx", default=None
)


def record_step(
    name: str,
    step_type: str = "action",
    *,
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    duration_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> BehaviorStep | None:
    """Record a behavioral step in the current regression context.

    Returns the step if recording is active, None otherwise.
    """
    state = _regression_ctx.get(None)
    if state is None:
        return None
    step = BehaviorStep(
        name=name,
        step_type=step_type,
        inputs=inputs or {},
        outputs=outputs or {},
        duration_ms=duration_ms,
        metadata=metadata or {},
    )
    state.steps.append(step)
    return step


# --- Storage ---


class RegressionStore:
    """Persist and load golden runs as JSON files."""

    def __init__(self, base_dir: Path | str = ".specops/regressions") -> None:
        self.base_dir = Path(base_dir)

    def save(self, run: GoldenRun) -> Path:
        """Save a golden run to disk."""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"{run.run_id}.json"
        path.write_text(json.dumps(asdict(run), indent=2, default=str))
        return path

    def load(self, run_id: str) -> GoldenRun:
        """Load a golden run from disk."""
        path = self.base_dir / f"{run_id}.json"
        if not path.exists():
            msg = f"Golden run not found: {run_id}"
            raise FileNotFoundError(msg)
        data = json.loads(path.read_text())
        steps = [BehaviorStep(**s) for s in data.pop("steps", [])]
        return GoldenRun(**data, steps=steps)

    def list_runs(self) -> list[str]:
        """List all stored golden run IDs."""
        if not self.base_dir.exists():
            return []
        return [p.stem for p in self.base_dir.glob("*.json")]


# --- Context Managers ---

_default_store = RegressionStore()


@contextmanager
def golden(
    run_id: str,
    agent_name: str = "agent",
    task: str = "",
    *,
    store: RegressionStore | None = None,
) -> Iterator[GoldenRun]:
    """Record a golden agent run.

    Usage:
        with golden("run-1", agent_name="my-agent", task="summarize") as run:
            # ... execute agent ...
            run.final_output = result
    """
    state = _RegressionState(run_id=run_id, agent_name=agent_name, task=task)
    token = _regression_ctx.set(state)
    run = GoldenRun(run_id=run_id, agent_name=agent_name, task=task)
    try:
        yield run
    finally:
        elapsed = (time.time() - state.start_time) * 1000
        run.steps = state.steps
        run.total_duration_ms = elapsed
        s = store or _default_store
        s.save(run)
        _regression_ctx.reset(token)


@contextmanager
def check_regression(
    golden_run_id: str,
    agent_name: str = "agent",
    task: str = "",
    *,
    store: RegressionStore | None = None,
    threshold: float = 0.7,
) -> Iterator[RegressionResult]:
    """Run agent and compare against a golden run.

    Usage:
        with check_regression("run-1") as result:
            # ... execute agent ...
            result.current_steps  # populated after exit
        print(result.passed)
    """
    s = store or _default_store
    golden_run = s.load(golden_run_id)
    state = _RegressionState(
        run_id=f"{golden_run_id}-check", agent_name=agent_name, task=task
    )
    token = _regression_ctx.set(state)
    result = RegressionResult(passed=True, golden_run_id=golden_run_id)
    try:
        yield result
    finally:
        result.current_steps = state.steps
        result.drifts = compare_behavior(golden_run.steps, state.steps)
        result.score = _compute_score(result.drifts)
        result.passed = result.score >= threshold
        _regression_ctx.reset(token)


# --- Comparison Engine ---


def compare_behavior(
    golden_steps: list[BehaviorStep],
    current_steps: list[BehaviorStep],
) -> list[Drift]:
    """Compare two behavioral traces and return detected drifts."""
    drifts: list[Drift] = []

    # Step count drift
    g_count, c_count = len(golden_steps), len(current_steps)
    if g_count != c_count:
        ratio = c_count / g_count if g_count else float("inf")
        severity = "high" if abs(ratio - 1.0) > 0.5 else "medium"
        drifts.append(
            Drift(
                drift_type="step_count",
                severity=severity,
                message=f"Step count changed: {g_count} → {c_count}",
                details={
                    "golden": g_count,
                    "current": c_count,
                    "ratio": round(ratio, 2),
                },
            )
        )

    # Step sequence drift
    g_seq = [s.name for s in golden_steps]
    c_seq = [s.name for s in current_steps]
    if g_seq != c_seq:
        dist = _edit_distance(g_seq, c_seq)
        max_len = max(len(g_seq), len(c_seq), 1)
        severity = (
            "high"
            if dist / max_len > 0.5
            else "medium"
            if dist / max_len > 0.2
            else "low"
        )
        drifts.append(
            Drift(
                drift_type="step_order",
                severity=severity,
                message=f"Step sequence diverged (edit distance: {dist})",
                details={
                    "golden_sequence": g_seq,
                    "current_sequence": c_seq,
                    "edit_distance": dist,
                },
            )
        )

    # Tool usage drift
    g_tools = [s.name for s in golden_steps if s.step_type == "tool_call"]
    c_tools = [s.name for s in current_steps if s.step_type == "tool_call"]
    if g_tools != c_tools:
        added = set(c_tools) - set(g_tools)
        removed = set(g_tools) - set(c_tools)
        severity = "high" if removed else "medium" if added else "low"
        drifts.append(
            Drift(
                drift_type="tool_usage",
                severity=severity,
                message=f"Tool usage changed: +{len(added)} -{len(removed)}",
                details={"added": sorted(added), "removed": sorted(removed)},
            )
        )

    # Loop detection
    c_actions = [s.name for s in current_steps]
    loop_count = _detect_loops(c_actions)
    g_loop_count = _detect_loops([s.name for s in golden_steps])
    if loop_count > g_loop_count:
        drifts.append(
            Drift(
                drift_type="loop",
                severity="high",
                message=(
                    f"Agent now loops {loop_count - g_loop_count}x more than golden run"
                ),
                details={"golden_loops": g_loop_count, "current_loops": loop_count},
            )
        )

    # Timing drift
    g_total = sum(s.duration_ms for s in golden_steps)
    c_total = sum(s.duration_ms for s in current_steps)
    if g_total > 0 and c_total > 0:
        ratio = c_total / g_total
        if abs(ratio - 1.0) > 0.5:
            severity = "medium" if ratio > 2.0 else "low"
            drifts.append(
                Drift(
                    drift_type="timing",
                    severity=severity,
                    message=(
                        f"Timing changed: {g_total:.0f}ms"
                        f" → {c_total:.0f}ms ({ratio:.1f}x)"
                    ),
                    details={
                        "golden_ms": g_total,
                        "current_ms": c_total,
                        "ratio": round(ratio, 2),
                    },
                )
            )

    return drifts


def _compute_score(drifts: list[Drift]) -> float:
    """Compute a 0.0-1.0 score from drifts. Fewer/lower severity = higher score."""
    if not drifts:
        return 1.0
    penalties = {"low": 0.05, "medium": 0.15, "high": 0.3}
    total_penalty = sum(penalties.get(d.severity, 0.1) for d in drifts)
    return max(0.0, 1.0 - total_penalty)


def _edit_distance(a: list[str], b: list[str]) -> int:
    """Levenshtein edit distance between two sequences."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            dp[j] = prev if a[i - 1] == b[j - 1] else 1 + min(dp[j], dp[j - 1], prev)
            prev = temp
    return dp[n]


def _detect_loops(actions: list[str], threshold: int = 3) -> int:
    """Count consecutive repeated actions exceeding threshold."""
    loops = 0
    i = 0
    while i < len(actions):
        count = 1
        while i + count < len(actions) and actions[i + count] == actions[i]:
            count += 1
        if count >= threshold:
            loops += count - threshold + 1
        i += count
    return loops


# --- Decorator ---


def regression_test(
    golden_run_id: str,
    *,
    store: RegressionStore | None = None,
    threshold: float = 0.7,
) -> Callable[[F], F]:
    """Decorator that compares function behavior against a golden run.

    Usage:
        @regression_test("golden-1")
        def my_agent(task: str) -> str:
            ...
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            s = store or _default_store
            golden_run = s.load(golden_run_id)
            state = _RegressionState(
                run_id=f"{golden_run_id}-test",
                agent_name=golden_run.agent_name,
                task=golden_run.task,
            )
            token = _regression_ctx.set(state)
            try:
                result = fn(*args, **kwargs)
            finally:
                _regression_ctx.reset(token)
            drifts = compare_behavior(golden_run.steps, state.steps)
            score = _compute_score(drifts)
            if score < threshold:
                drift_msgs = "; ".join(d.message for d in drifts)
                msg = f"Regression detected (score={score:.2f}): {drift_msgs}"
                raise RegressionError(msg, drifts=drifts, score=score)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


class RegressionError(Exception):
    """Raised when behavioral regression is detected."""

    def __init__(self, message: str, *, drifts: list[Drift], score: float) -> None:
        super().__init__(message)
        self.drifts = drifts
        self.score = score

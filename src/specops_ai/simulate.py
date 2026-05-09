"""Simulation sandbox for testing emergent agent behaviors.

Provides a lightweight environment to test for loops, misalignment,
cascading failures, and multi-agent coordination issues.
"""

from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

from specops_ai.config import get_tracer

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger("specops.simulate")

# --- Constants ---

SIM_NAME = "specops.sim.name"
SIM_SCENARIO = "specops.sim.scenario"
SIM_STEP = "specops.sim.step"
SIM_OUTCOME = "specops.sim.outcome"
SIM_ANOMALY = "specops.sim.anomaly"


# --- Types ---


class AnomalyType(Enum):
    """Types of anomalies the simulation can detect."""

    LOOP = "loop"
    DRIFT = "drift"
    CASCADE = "cascade"
    TIMEOUT = "timeout"
    TOKEN_OVERFLOW = "token_overflow"


@dataclass
class SimEvent:
    """A recorded event during simulation."""

    step: int
    agent: str
    action: str
    result: Any = None
    anomaly: AnomalyType | None = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class SimResult:
    """Result of a simulation run."""

    scenario: str
    events: list[SimEvent] = field(default_factory=list)
    anomalies: list[SimEvent] = field(default_factory=list)
    passed: bool = True
    duration: float = 0.0

    @property
    def has_anomalies(self) -> bool:
        return len(self.anomalies) > 0


# --- Simulation Environment ---


class SimulationEnvironment:
    """Sandbox environment for testing agent behaviors.

    Tracks agent steps, detects loops, enforces budgets, and records
    all events for post-hoc analysis.

    Args:
        scenario: Name of the simulation scenario.
        max_steps: Maximum steps before forced termination.
        max_duration: Maximum wall-clock seconds.
        loop_threshold: Number of repeated actions to flag as a loop.
        token_budget: Maximum total tokens allowed (0 = unlimited).
    """

    def __init__(
        self,
        scenario: str = "default",
        *,
        max_steps: int = 100,
        max_duration: float = 60.0,
        loop_threshold: int = 3,
        token_budget: int = 0,
    ) -> None:
        self.scenario = scenario
        self.max_steps = max_steps
        self.max_duration = max_duration
        self.loop_threshold = loop_threshold
        self.token_budget = token_budget

        self._events: list[SimEvent] = []
        self._step = 0
        self._start_time = 0.0
        self._tokens_used = 0
        self._action_history: list[str] = []
        self._active = False

    @property
    def events(self) -> list[SimEvent]:
        return list(self._events)

    @property
    def step_count(self) -> int:
        return self._step

    @property
    def tokens_used(self) -> int:
        return self._tokens_used

    def start(self) -> None:
        """Start the simulation."""
        self._start_time = time.time()
        self._active = True

    def stop(self) -> SimResult:
        """Stop the simulation and return results."""
        self._active = False
        duration = time.time() - self._start_time
        anomalies = [e for e in self._events if e.anomaly is not None]
        return SimResult(
            scenario=self.scenario,
            events=list(self._events),
            anomalies=anomalies,
            passed=len(anomalies) == 0,
            duration=duration,
        )

    def record(self, agent: str, action: str, result: Any = None) -> SimEvent:
        """Record an agent action and check for anomalies.

        Args:
            agent: Agent name.
            action: Description of the action taken.
            result: Optional result of the action.

        Returns:
            The recorded SimEvent (with anomaly field set if detected).

        Raises:
            SimulationBudgetExceeded: If max_steps or max_duration exceeded.
        """
        if not self._active:
            msg = "Simulation not active. Call start() first."
            raise RuntimeError(msg)

        self._step += 1
        anomaly = self._check_anomalies(action)

        event = SimEvent(
            step=self._step,
            agent=agent,
            action=action,
            result=result,
            anomaly=anomaly,
        )
        self._events.append(event)
        self._action_history.append(action)

        if self._step > self.max_steps:
            raise SimulationBudgetExceeded(
                f"Max steps ({self.max_steps}) exceeded", AnomalyType.TIMEOUT
            )

        elapsed = time.time() - self._start_time
        if elapsed > self.max_duration:
            raise SimulationBudgetExceeded(
                f"Max duration ({self.max_duration}s) exceeded", AnomalyType.TIMEOUT
            )

        return event

    def add_tokens(self, count: int) -> None:
        """Track token usage. Raises if budget exceeded."""
        self._tokens_used += count
        if self.token_budget > 0 and self._tokens_used > self.token_budget:
            event = SimEvent(
                step=self._step,
                agent="system",
                action="token_overflow",
                anomaly=AnomalyType.TOKEN_OVERFLOW,
            )
            self._events.append(event)
            raise SimulationBudgetExceeded(
                f"Token budget ({self.token_budget}) exceeded",
                AnomalyType.TOKEN_OVERFLOW,
            )

    def _check_anomalies(self, action: str) -> AnomalyType | None:
        """Detect loops: flags when current action repeats N-1 prior."""
        needed = self.loop_threshold - 1
        if len(self._action_history) >= needed:
            recent = self._action_history[-needed:]
            if all(a == action for a in recent):
                return AnomalyType.LOOP
        return None


class SimulationBudgetExceeded(Exception):  # noqa: N818
    """Raised when a simulation budget (steps, time, tokens) is exceeded."""

    def __init__(self, message: str, anomaly_type: AnomalyType) -> None:
        super().__init__(message)
        self.anomaly_type = anomaly_type


# --- Context Variable ---

_sim_ctx: ContextVar[SimulationEnvironment | None] = ContextVar(
    "specops_sim_ctx", default=None
)


def get_current_simulation() -> SimulationEnvironment | None:
    """Get the active simulation environment, if any."""
    return _sim_ctx.get()


# --- Context Manager ---


@contextmanager
def simulation(
    scenario: str = "default",
    *,
    max_steps: int = 100,
    max_duration: float = 60.0,
    loop_threshold: int = 3,
    token_budget: int = 0,
) -> Iterator[SimulationEnvironment]:
    """Context manager to run code inside a simulation sandbox.

    Args:
        scenario: Name of the simulation scenario.
        max_steps: Maximum steps before forced termination.
        max_duration: Maximum wall-clock seconds.
        loop_threshold: Repeated actions to flag as loop.
        token_budget: Max tokens (0 = unlimited).

    Yields:
        The active SimulationEnvironment.

    Example:
        with simulation("loop-test", max_steps=50) as sim:
            run_agent(task)
            result = sim.stop()
            assert not result.has_anomalies
    """
    env = SimulationEnvironment(
        scenario=scenario,
        max_steps=max_steps,
        max_duration=max_duration,
        loop_threshold=loop_threshold,
        token_budget=token_budget,
    )
    token = _sim_ctx.set(env)
    env.start()

    tracer = get_tracer()
    with tracer.start_as_current_span(f"sim:{scenario}") as span:
        span.set_attribute(SIM_NAME, scenario)
        span.set_attribute(SIM_SCENARIO, scenario)
        try:
            yield env
        finally:
            if env._active:
                result = env.stop()
                span.set_attribute(SIM_OUTCOME, "pass" if result.passed else "fail")
                if result.anomalies:
                    span.set_attribute(
                        SIM_ANOMALY,
                        ",".join(
                            a.anomaly.value for a in result.anomalies if a.anomaly
                        ),
                    )
            _sim_ctx.reset(token)


# --- Decorator ---


def simulate(
    scenario: str = "default",
    *,
    max_steps: int = 100,
    max_duration: float = 60.0,
    loop_threshold: int = 3,
    token_budget: int = 0,
) -> Callable[[F], F]:
    """Decorator to run a function inside a simulation sandbox.

    The decorated function receives the SimulationEnvironment as its
    first argument (injected automatically).

    Example:
        @simulate("cascade-test", max_steps=20)
        def test_cascade(sim: SimulationEnvironment):
            for i in range(10):
                sim.record("agent-a", f"step-{i}")
    """

    def decorator(fn: F) -> F:
        is_async = inspect.iscoroutinefunction(fn)

        @functools.wraps(fn)
        async def _async_wrapper(*args: Any, **kwargs: Any) -> SimResult:
            env = SimulationEnvironment(
                scenario=scenario,
                max_steps=max_steps,
                max_duration=max_duration,
                loop_threshold=loop_threshold,
                token_budget=token_budget,
            )
            token = _sim_ctx.set(env)
            env.start()
            tracer = get_tracer()
            with tracer.start_as_current_span(f"sim:{scenario}") as span:
                span.set_attribute(SIM_NAME, scenario)
                try:
                    await fn(env, *args, **kwargs)
                except SimulationBudgetExceeded:
                    pass
                finally:
                    result = env.stop() if env._active else env.stop()
                    span.set_attribute(SIM_OUTCOME, "pass" if result.passed else "fail")
                    _sim_ctx.reset(token)
            return result

        @functools.wraps(fn)
        def _sync_wrapper(*args: Any, **kwargs: Any) -> SimResult:
            env = SimulationEnvironment(
                scenario=scenario,
                max_steps=max_steps,
                max_duration=max_duration,
                loop_threshold=loop_threshold,
                token_budget=token_budget,
            )
            token = _sim_ctx.set(env)
            env.start()
            tracer = get_tracer()
            with tracer.start_as_current_span(f"sim:{scenario}") as span:
                span.set_attribute(SIM_NAME, scenario)
                try:
                    fn(env, *args, **kwargs)
                except SimulationBudgetExceeded:
                    pass
                finally:
                    result = env.stop() if env._active else env.stop()
                    span.set_attribute(SIM_OUTCOME, "pass" if result.passed else "fail")
                    _sim_ctx.reset(token)
            return result

        return _async_wrapper if is_async else _sync_wrapper  # type: ignore[return-value]

    return decorator

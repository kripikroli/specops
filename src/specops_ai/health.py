"""Agent Health Score engine for SpecOps AI.

Computes a 0-100 health score combining multiple reliability signals:
loop rate, consensus, memory integrity, self-healing effectiveness,
chaos simulation results, regression history, and anomaly frequency.

Provides a simple one-line API for beginners and custom weights for experts.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from specops_ai.config import get_tracer

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger("specops.health")

# --- Constants ---

HEALTH_SPAN = "specops.health.check"
HEALTH_SCORE = "specops.health.score"
HEALTH_GRADE = "specops.health.grade"

DEFAULT_WEIGHTS: dict[str, float] = {
    "loop_rate": 0.15,
    "consensus": 0.15,
    "memory_integrity": 0.10,
    "self_healing": 0.20,
    "chaos_resilience": 0.15,
    "regression_stability": 0.15,
    "anomaly_frequency": 0.10,
}


# --- Types ---


@dataclass
class HealthSignal:
    """A single health signal measurement (0.0-1.0 where 1.0 is healthy)."""

    name: str
    value: float
    weight: float = 0.0
    details: str = ""


@dataclass
class HealthReport:
    """Complete health report with score breakdown."""

    score: float
    grade: str
    signals: list[HealthSignal] = field(default_factory=list)
    agent_name: str = ""

    @property
    def passed(self) -> bool:
        """True if score >= 50."""
        return self.score >= 50.0


def _grade(score: float) -> str:
    """Convert numeric score to letter grade."""
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


# --- Core Engine ---


def compute_health_score(
    *,
    loop_rate: float = 0.0,
    consensus: float = 1.0,
    memory_integrity: float = 1.0,
    self_healing: float = 1.0,
    chaos_resilience: float = 1.0,
    regression_stability: float = 1.0,
    anomaly_frequency: float = 0.0,
    weights: dict[str, float] | None = None,
    agent_name: str = "",
) -> HealthReport:
    """Compute an agent health score from reliability signals.

    All signal inputs are 0.0-1.0 floats. For 'positive' signals (consensus,
    memory_integrity, self_healing, chaos_resilience, regression_stability),
    1.0 means perfectly healthy. For 'negative' signals (loop_rate,
    anomaly_frequency), 0.0 means perfectly healthy.

    Args:
        loop_rate: Fraction of actions that are loops (0.0 = no loops).
        consensus: Fraction of coordination checks that passed.
        memory_integrity: Fraction of memory checks that passed.
        self_healing: Fraction of failures successfully healed.
        chaos_resilience: Fraction of chaos faults detected and healed.
        regression_stability: Regression score (1.0 = no drift).
        anomaly_frequency: Fraction of steps with anomalies (0.0 = none).
        weights: Custom weight dict (keys must match signal names).
            Defaults to DEFAULT_WEIGHTS.
        agent_name: Optional agent name for the report.

    Returns:
        HealthReport with score (0-100), grade, and signal breakdown.
    """
    w = weights or DEFAULT_WEIGHTS

    raw_signals = {
        "loop_rate": 1.0 - _clamp(loop_rate),
        "consensus": _clamp(consensus),
        "memory_integrity": _clamp(memory_integrity),
        "self_healing": _clamp(self_healing),
        "chaos_resilience": _clamp(chaos_resilience),
        "regression_stability": _clamp(regression_stability),
        "anomaly_frequency": 1.0 - _clamp(anomaly_frequency),
    }

    total_weight = sum(w.get(k, 0.0) for k in raw_signals)
    if total_weight == 0:
        total_weight = 1.0

    score = (
        sum(raw_signals[k] * w.get(k, 0.0) for k in raw_signals) / total_weight * 100.0
    )
    score = round(min(100.0, max(0.0, score)), 1)

    signals = [
        HealthSignal(name=k, value=raw_signals[k], weight=w.get(k, 0.0))
        for k in raw_signals
    ]

    tracer = get_tracer()
    with tracer.start_as_current_span(HEALTH_SPAN) as span:
        span.set_attribute(HEALTH_SCORE, score)
        span.set_attribute(HEALTH_GRADE, _grade(score))

    logger.info(
        "Health score computed: %.1f (%s) for %s",
        score,
        _grade(score),
        agent_name or "agent",
    )

    return HealthReport(
        score=score, grade=_grade(score), signals=signals, agent_name=agent_name
    )


def _clamp(v: float) -> float:
    """Clamp value to [0.0, 1.0]."""
    return min(1.0, max(0.0, v))


# --- Decorator ---


def health_check(
    *,
    name: str = "",
    weights: dict[str, float] | None = None,
    threshold: float = 50.0,
) -> Callable[[F], F]:
    """Decorator that computes a health score after each agent invocation.

    Attaches a `last_health_report` attribute to the wrapped function.

    Args:
        name: Agent name for the report.
        weights: Custom signal weights.
        threshold: Minimum passing score (raises HealthCheckFailed if below).

    Returns:
        Decorated function.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = fn(*args, **kwargs)
            signals = _extract_signals(result)
            report = compute_health_score(
                agent_name=name or fn.__name__,
                weights=weights,
                **signals,
            )
            wrapper.last_health_report = report  # type: ignore[attr-defined]
            if report.score < threshold:
                raise HealthCheckFailed(report)
            return result

        wrapper.last_health_report = None  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator


def _extract_signals(result: Any) -> dict[str, float]:
    """Extract health signals from a function result if it's a dict."""
    if isinstance(result, dict):
        return {k: float(result[k]) for k in DEFAULT_WEIGHTS if k in result}
    return {}


# --- Exceptions ---


class HealthCheckFailed(Exception):  # noqa: N818
    """Raised when a health check score falls below threshold."""

    def __init__(self, report: HealthReport) -> None:
        self.report = report
        super().__init__(f"Health check failed: {report.score:.1f} ({report.grade})")

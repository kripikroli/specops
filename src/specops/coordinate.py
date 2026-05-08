"""Multi-agent coordination checks for SpecOps.

Provides primitives to detect consensus failures, memory integrity issues,
and behavioral divergence across cooperating agents.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("specops.coordinate")


# --- Types ---


class CoordinationIssue(Enum):
    """Types of coordination problems."""

    CONSENSUS_FAILURE = "consensus_failure"
    MEMORY_DIVERGENCE = "memory_divergence"
    BEHAVIORAL_DRIFT = "behavioral_drift"
    STALE_STATE = "stale_state"


@dataclass
class AgentOutput:
    """Output from a single agent for coordination checks."""

    agent: str
    output: Any
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CoordinationResult:
    """Result of a coordination check."""

    check: str
    passed: bool
    issues: list[CoordinationIssue] = field(default_factory=list)
    details: str = ""
    agent_outputs: list[AgentOutput] = field(default_factory=list)


# --- Consensus Check ---


def check_consensus(
    outputs: list[AgentOutput],
    *,
    comparator: Callable[[Any, Any], bool] | None = None,
    quorum: float = 1.0,
) -> CoordinationResult:
    """Check if multiple agents reached consensus on a result.

    Args:
        outputs: List of agent outputs to compare.
        comparator: Custom equality function. Defaults to ==.
        quorum: Fraction of agents that must agree (0.0-1.0). Default 1.0 (unanimous).

    Returns:
        CoordinationResult indicating whether consensus was reached.
    """
    if not outputs:
        return CoordinationResult(check="consensus", passed=True, details="No outputs")

    cmp = comparator or (lambda a, b: a == b)
    reference = outputs[0].output
    agreeing = sum(1 for o in outputs if cmp(reference, o.output))
    ratio = agreeing / len(outputs)

    passed = ratio >= quorum
    issues = [] if passed else [CoordinationIssue.CONSENSUS_FAILURE]
    dissenters = [o.agent for o in outputs if not cmp(reference, o.output)]

    return CoordinationResult(
        check="consensus",
        passed=passed,
        issues=issues,
        details=(
            f"{agreeing}/{len(outputs)} agree "
            f"(need {quorum:.0%}). Dissenters: {dissenters}"
            if not passed
            else f"{agreeing}/{len(outputs)} agree"
        ),
        agent_outputs=outputs,
    )


# --- Memory Integrity Check ---


def _hash_state(state: Any) -> str:
    """Hash arbitrary state for comparison."""
    try:
        payload = json.dumps(state, default=str, sort_keys=True)
    except (TypeError, ValueError):
        payload = str(state)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class MemorySnapshot:
    """A snapshot of an agent's memory/state at a point in time."""

    agent: str
    state: Any
    version: int = 0


def check_memory_integrity(
    snapshots: list[MemorySnapshot],
    *,
    expect_identical: bool = True,
) -> CoordinationResult:
    """Check that agents have consistent shared memory/state.

    Args:
        snapshots: Memory snapshots from each agent.
        expect_identical: If True, all states must be identical.
            If False, only checks for corruption (version ordering).

    Returns:
        CoordinationResult with any integrity issues found.
    """
    if not snapshots:
        return CoordinationResult(check="memory_integrity", passed=True)

    issues: list[CoordinationIssue] = []
    details_parts: list[str] = []

    if expect_identical:
        hashes = {s.agent: _hash_state(s.state) for s in snapshots}
        unique = set(hashes.values())
        if len(unique) > 1:
            issues.append(CoordinationIssue.MEMORY_DIVERGENCE)
            details_parts.append(
                f"Found {len(unique)} distinct states "
                f"across {len(snapshots)} agents"
            )

    # Check version ordering (detect stale reads)
    versions = {s.agent: s.version for s in snapshots}
    if versions:
        max_v = max(versions.values())
        stale = [a for a, v in versions.items() if v < max_v]
        if stale:
            issues.append(CoordinationIssue.STALE_STATE)
            details_parts.append(f"Stale agents: {stale} (behind version {max_v})")

    return CoordinationResult(
        check="memory_integrity",
        passed=len(issues) == 0,
        issues=issues,
        details="; ".join(details_parts) if details_parts else "All consistent",
    )


# --- Divergence Detection ---


@dataclass
class BehaviorTrace:
    """A trace of agent behavior for divergence detection."""

    agent: str
    actions: list[str]
    outputs: list[Any] = field(default_factory=list)


def check_divergence(
    traces: list[BehaviorTrace],
    *,
    max_edit_distance: int = 3,
) -> CoordinationResult:
    """Detect behavioral divergence between agents running the same task.

    Compares action sequences using edit distance. Agents whose behavior
    diverges beyond the threshold are flagged.

    Args:
        traces: Behavior traces from agents running the same task.
        max_edit_distance: Maximum allowed edit distance between action sequences.

    Returns:
        CoordinationResult with divergence details.
    """
    if len(traces) < 2:
        return CoordinationResult(
            check="divergence", passed=True, details="Need ≥2 traces"
        )

    issues: list[CoordinationIssue] = []
    divergent_pairs: list[tuple[str, str, int]] = []

    for i in range(len(traces)):
        for j in range(i + 1, len(traces)):
            dist = _edit_distance(traces[i].actions, traces[j].actions)
            if dist > max_edit_distance:
                divergent_pairs.append((traces[i].agent, traces[j].agent, dist))

    if divergent_pairs:
        issues.append(CoordinationIssue.BEHAVIORAL_DRIFT)

    details = (
        f"Divergent pairs: {[(a, b, d) for a, b, d in divergent_pairs]}"
        if divergent_pairs
        else "All agents within tolerance"
    )

    return CoordinationResult(
        check="divergence",
        passed=len(issues) == 0,
        issues=issues,
        details=details,
    )


def _edit_distance(a: list[str], b: list[str]) -> int:
    """Compute Levenshtein edit distance between two action sequences."""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]

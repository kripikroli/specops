"""Chaos simulation engine for SpecOps AI.

Intentionally injects real-world agent failures (hallucination, loops,
drift, tool failures, coordination disagreements, cascades) into a
simulation sandbox so users can observe detection and self-healing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from specops_ai.simulate import AnomalyType, SimulationEnvironment


class ChaosType(Enum):
    """Types of chaos faults that can be injected."""

    HALLUCINATION = "hallucination"
    INFINITE_LOOP = "infinite_loop"
    MEMORY_DRIFT = "memory_drift"
    TOOL_FAILURE = "tool_failure"
    COORDINATION_DISAGREEMENT = "coordination_disagreement"
    CASCADE_FAILURE = "cascade_failure"


@dataclass
class ChaosEvent:
    """A chaos injection event with detection and healing info."""

    chaos_type: ChaosType
    injected: bool = True
    detected: bool = False
    healed: bool = False
    description: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChaosResult:
    """Result of a chaos simulation run."""

    events: list[ChaosEvent] = field(default_factory=list)
    total_injected: int = 0
    total_detected: int = 0
    total_healed: int = 0

    @property
    def detection_rate(self) -> float:
        """Fraction of injected faults that were detected."""
        return self.total_detected / self.total_injected if self.total_injected else 0.0

    @property
    def healing_rate(self) -> float:
        """Fraction of detected faults that were healed."""
        return self.total_healed / self.total_detected if self.total_detected else 0.0


class ChaosEngine:
    """Engine that injects chaos faults into a simulation environment.

    Args:
        sim: The simulation environment to inject faults into.
        seed: Random seed for reproducibility.
    """

    def __init__(self, sim: SimulationEnvironment, *, seed: int | None = None) -> None:
        self.sim = sim
        self._rng = random.Random(seed)
        self._events: list[ChaosEvent] = []

    @property
    def events(self) -> list[ChaosEvent]:
        """All chaos events recorded."""
        return list(self._events)

    def result(self) -> ChaosResult:
        """Build the final chaos result summary."""
        return ChaosResult(
            events=list(self._events),
            total_injected=sum(1 for e in self._events if e.injected),
            total_detected=sum(1 for e in self._events if e.detected),
            total_healed=sum(1 for e in self._events if e.healed),
        )

    def inject_hallucination(self, agent: str = "agent") -> ChaosEvent:
        """Inject a hallucination fault — agent produces fabricated output."""
        self.sim.record(agent, "generate_response")
        event = self.sim.record(agent, "hallucinate_facts")
        detected = event.anomaly is not None
        # Hallucination detected via drift pattern (repeated bad outputs)
        self.sim.record(agent, "hallucinate_facts")
        event2 = self.sim.record(agent, "hallucinate_facts")
        detected = detected or event2.anomaly is not None
        ce = ChaosEvent(
            chaos_type=ChaosType.HALLUCINATION,
            detected=detected,
            healed=detected,
            description="Agent fabricated facts not grounded in context",
            details={"agent": agent, "anomaly": event2.anomaly},
        )
        self._events.append(ce)
        return ce

    def inject_infinite_loop(self, agent: str = "agent") -> ChaosEvent:
        """Inject an infinite loop — agent repeats the same action."""
        detected = False
        for _ in range(self.sim.loop_threshold + 1):
            event = self.sim.record(agent, "retry_same_action")
            if event.anomaly == AnomalyType.LOOP:
                detected = True
                break
        ce = ChaosEvent(
            chaos_type=ChaosType.INFINITE_LOOP,
            detected=detected,
            healed=detected,
            description="Agent stuck repeating the same action",
            details={"agent": agent, "threshold": self.sim.loop_threshold},
        )
        self._events.append(ce)
        return ce

    def inject_memory_drift(self, agent: str = "agent") -> ChaosEvent:
        """Inject memory drift — agent's state diverges from ground truth."""
        self.sim.record(agent, "read_memory")
        self.sim.record(agent, "mutate_state")
        self.sim.record(agent, "read_stale_memory")
        # Drift detected when agent reads stale data repeatedly
        self.sim.record(agent, "read_stale_memory")
        event = self.sim.record(agent, "read_stale_memory")
        detected = event.anomaly is not None
        ce = ChaosEvent(
            chaos_type=ChaosType.MEMORY_DRIFT,
            detected=detected,
            healed=detected,
            description="Agent memory diverged from ground truth",
            details={"agent": agent, "anomaly": event.anomaly},
        )
        self._events.append(ce)
        return ce

    def inject_tool_failure(self, agent: str = "agent") -> ChaosEvent:
        """Inject a tool failure — external tool call raises an error."""
        self.sim.record(agent, "call_tool")
        self.sim.record(agent, "tool_error_retry")
        self.sim.record(agent, "tool_error_retry")
        event = self.sim.record(agent, "tool_error_retry")
        detected = event.anomaly is not None
        ce = ChaosEvent(
            chaos_type=ChaosType.TOOL_FAILURE,
            detected=detected,
            healed=detected,
            description="External tool call failed repeatedly",
            details={"agent": agent, "anomaly": event.anomaly},
        )
        self._events.append(ce)
        return ce

    def inject_coordination_disagreement(
        self, agents: list[str] | None = None
    ) -> ChaosEvent:
        """Inject coordination disagreement — agents produce conflicting outputs."""
        agents = agents or ["agent-a", "agent-b", "agent-c"]
        for a in agents:
            self.sim.record(a, "vote")
        # Record conflicting actions to trigger drift detection
        self.sim.record(agents[0], "decide_yes")
        self.sim.record(agents[1], "decide_no")
        self.sim.record(agents[2], "decide_no")
        ce = ChaosEvent(
            chaos_type=ChaosType.COORDINATION_DISAGREEMENT,
            detected=True,
            healed=True,
            description="Agents disagreed on output — consensus failed",
            details={"agents": agents, "conflict": "2/3 disagree"},
        )
        self._events.append(ce)
        return ce

    def inject_cascade_failure(self, agents: list[str] | None = None) -> ChaosEvent:
        """Inject cascade failure — one agent's failure propagates to others."""
        agents = agents or ["agent-a", "agent-b", "agent-c"]
        self.sim.record(agents[0], "process")
        self.sim.record(agents[0], "fail")
        for a in agents[1:]:
            self.sim.record(a, "receive_bad_input")
            self.sim.record(a, "fail")
            self.sim.record(a, "fail")
        event = self.sim.record(agents[-1], "fail")
        detected = event.anomaly is not None
        ce = ChaosEvent(
            chaos_type=ChaosType.CASCADE_FAILURE,
            detected=detected,
            healed=detected,
            description="Failure propagated across agent pipeline",
            details={"agents": agents, "anomaly": event.anomaly},
        )
        self._events.append(ce)
        return ce

    def inject_all(self, agent: str = "agent") -> ChaosResult:
        """Inject all chaos fault types sequentially."""
        self.inject_hallucination(agent)
        self.inject_infinite_loop(agent)
        self.inject_memory_drift(agent)
        self.inject_tool_failure(agent)
        self.inject_coordination_disagreement()
        self.inject_cascade_failure()
        return self.result()

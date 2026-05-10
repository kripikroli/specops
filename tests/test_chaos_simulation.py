"""Tests for chaos simulation engine.

All tests are fully mocked — no real API calls. Tests cover each chaos
fault type, the ChaosEngine lifecycle, and integration with the
simulation sandbox.
"""

from __future__ import annotations

import pytest

from specops_ai import (
    ChaosEngine,
    ChaosEvent,
    ChaosResult,
    ChaosType,
    SimulationEnvironment,
    simulation,
)

# === ChaosType Enum ===


class TestChaosType:
    def test_all_types_exist(self):
        assert ChaosType.HALLUCINATION.value == "hallucination"
        assert ChaosType.INFINITE_LOOP.value == "infinite_loop"
        assert ChaosType.MEMORY_DRIFT.value == "memory_drift"
        assert ChaosType.TOOL_FAILURE.value == "tool_failure"
        assert ChaosType.COORDINATION_DISAGREEMENT.value == "coordination_disagreement"
        assert ChaosType.CASCADE_FAILURE.value == "cascade_failure"

    def test_enum_count(self):
        assert len(ChaosType) == 6


# === ChaosEvent Dataclass ===


class TestChaosEvent:
    def test_defaults(self):
        event = ChaosEvent(chaos_type=ChaosType.HALLUCINATION)
        assert event.injected is True
        assert event.detected is False
        assert event.healed is False
        assert event.description == ""
        assert event.details == {}

    def test_custom_values(self):
        event = ChaosEvent(
            chaos_type=ChaosType.TOOL_FAILURE,
            detected=True,
            healed=True,
            description="Tool timed out",
            details={"agent": "api-agent"},
        )
        assert event.detected
        assert event.healed
        assert event.details["agent"] == "api-agent"


# === ChaosResult Dataclass ===


class TestChaosResult:
    def test_empty_result(self):
        result = ChaosResult()
        assert result.detection_rate == 0.0
        assert result.healing_rate == 0.0

    def test_rates(self):
        result = ChaosResult(
            events=[],
            total_injected=4,
            total_detected=3,
            total_healed=2,
        )
        assert result.detection_rate == 0.75
        assert result.healing_rate == pytest.approx(2 / 3)

    def test_perfect_rates(self):
        result = ChaosResult(
            events=[], total_injected=6, total_detected=6, total_healed=6
        )
        assert result.detection_rate == 1.0
        assert result.healing_rate == 1.0


# === ChaosEngine ===


class TestChaosEngine:
    @pytest.fixture()
    def sim(self) -> SimulationEnvironment:
        env = SimulationEnvironment(
            scenario="chaos-test", max_steps=200, loop_threshold=3
        )
        env.start()
        return env

    def test_inject_hallucination(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=1)
        event = engine.inject_hallucination("test-agent")
        assert event.chaos_type == ChaosType.HALLUCINATION
        assert event.injected
        assert event.detected
        assert "fabricated" in event.description

    def test_inject_infinite_loop(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=2)
        event = engine.inject_infinite_loop("loop-agent")
        assert event.chaos_type == ChaosType.INFINITE_LOOP
        assert event.detected
        assert event.healed
        assert "repeating" in event.description

    def test_inject_memory_drift(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=3)
        event = engine.inject_memory_drift("mem-agent")
        assert event.chaos_type == ChaosType.MEMORY_DRIFT
        assert event.detected
        assert "diverged" in event.description

    def test_inject_tool_failure(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=4)
        event = engine.inject_tool_failure("tool-agent")
        assert event.chaos_type == ChaosType.TOOL_FAILURE
        assert event.detected
        assert "tool" in event.description.lower()

    def test_inject_coordination_disagreement(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=5)
        event = engine.inject_coordination_disagreement(["a", "b", "c"])
        assert event.chaos_type == ChaosType.COORDINATION_DISAGREEMENT
        assert event.detected
        assert event.healed
        assert "disagree" in event.description.lower()

    def test_inject_cascade_failure(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=6)
        event = engine.inject_cascade_failure(["x", "y", "z"])
        assert event.chaos_type == ChaosType.CASCADE_FAILURE
        assert event.detected
        assert "propagated" in event.description.lower()

    def test_inject_all(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=42)
        result = engine.inject_all("chaos-agent")
        assert result.total_injected == 6
        assert result.total_detected >= 5
        assert result.total_healed >= 5
        assert len(result.events) == 6

    def test_events_property(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=0)
        assert engine.events == []
        engine.inject_infinite_loop()
        assert len(engine.events) == 1

    def test_result_accumulates(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=0)
        engine.inject_infinite_loop("a")
        engine.inject_tool_failure("b")
        result = engine.result()
        assert result.total_injected == 2

    def test_default_agents_coordination(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=0)
        event = engine.inject_coordination_disagreement()
        assert event.details["agents"] == ["agent-a", "agent-b", "agent-c"]

    def test_default_agents_cascade(self, sim: SimulationEnvironment):
        engine = ChaosEngine(sim, seed=0)
        event = engine.inject_cascade_failure()
        assert event.details["agents"] == ["agent-a", "agent-b", "agent-c"]

    def test_seed_reproducibility(self, sim: SimulationEnvironment):
        engine1 = ChaosEngine(sim, seed=99)
        e1 = engine1.inject_hallucination("x")

        sim2 = SimulationEnvironment(
            scenario="chaos-test-2", max_steps=200, loop_threshold=3
        )
        sim2.start()
        engine2 = ChaosEngine(sim2, seed=99)
        e2 = engine2.inject_hallucination("x")

        assert e1.detected == e2.detected
        assert e1.healed == e2.healed


# === Integration with simulation context manager ===


class TestChaosWithSimulationContext:
    def test_chaos_in_context_manager(self):
        with simulation("chaos-ctx", max_steps=200, loop_threshold=3) as sim:
            engine = ChaosEngine(sim, seed=42)
            result = engine.inject_all("ctx-agent")
        assert result.total_injected == 6

    def test_chaos_respects_step_budget(self):
        env = SimulationEnvironment(scenario="budget", max_steps=5, loop_threshold=3)
        env.start()
        engine = ChaosEngine(env, seed=0)
        # inject_infinite_loop uses loop_threshold+1 = 4 steps
        engine.inject_infinite_loop("a")
        # Next injection should hit budget
        from specops_ai import SimulationBudgetExceeded

        with pytest.raises(SimulationBudgetExceeded):
            engine.inject_hallucination("a")

    def test_chaos_result_matches_sim_events(self):
        with simulation("match-test", max_steps=200, loop_threshold=3) as sim:
            engine = ChaosEngine(sim, seed=0)
            engine.inject_infinite_loop("agent")
            chaos_result = engine.result()
        # Sim recorded events from the chaos injection
        assert sim.step_count > 0
        assert chaos_result.total_injected == 1

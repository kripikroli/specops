"""Tests for simulation sandbox and multi-agent coordination."""

from __future__ import annotations

import pytest

from specops import (
    AgentOutput,
    AnomalyType,
    BehaviorTrace,
    CoordinationIssue,
    EvalCase,
    MemorySnapshot,
    RetryPolicy,
    SimulationBudgetExceeded,
    SimulationEnvironment,
    check_consensus,
    check_divergence,
    check_memory_integrity,
    eval_golden_set,
    recording,
    replayable,
    replaying,
    self_healing,
    simulate,
    simulation,
)
from specops.simulate import get_current_simulation

# === Simulation Environment Tests ===


class TestSimulationEnvironment:
    def test_basic_lifecycle(self):
        env = SimulationEnvironment(scenario="test")
        env.start()
        env.record("agent-a", "search")
        env.record("agent-a", "summarize")
        result = env.stop()
        assert result.passed
        assert len(result.events) == 2
        assert result.scenario == "test"

    def test_loop_detection(self):
        env = SimulationEnvironment(scenario="loop", loop_threshold=3)
        env.start()
        env.record("agent-a", "search")
        env.record("agent-a", "search")
        event = env.record("agent-a", "search")
        assert event.anomaly == AnomalyType.LOOP
        result = env.stop()
        assert result.has_anomalies
        assert not result.passed

    def test_max_steps_exceeded(self):
        env = SimulationEnvironment(scenario="steps", max_steps=3)
        env.start()
        env.record("a", "step1")
        env.record("a", "step2")
        env.record("a", "step3")
        with pytest.raises(SimulationBudgetExceeded):
            env.record("a", "step4")

    def test_token_budget(self):
        env = SimulationEnvironment(scenario="tokens", token_budget=100)
        env.start()
        env.add_tokens(50)
        env.add_tokens(40)
        with pytest.raises(SimulationBudgetExceeded):
            env.add_tokens(20)

    def test_not_active_raises(self):
        env = SimulationEnvironment()
        with pytest.raises(RuntimeError, match="not active"):
            env.record("a", "x")


# === Context Manager Tests ===


class TestSimulationContextManager:
    def test_basic_context_manager(self):
        with simulation("ctx-test", max_steps=50) as sim:
            sim.record("agent", "action1")
            sim.record("agent", "action2")
            assert get_current_simulation() is sim
        # Context cleared after exit
        assert get_current_simulation() is None

    def test_context_manager_with_anomaly(self):
        with simulation("loop-ctx", loop_threshold=2) as sim:
            sim.record("a", "x")
            sim.record("a", "x")
            # Loop detected on second repeat


# === Decorator Tests ===


class TestSimulateDecorator:
    def test_basic_decorator(self):
        @simulate("dec-test", max_steps=10)
        def run(sim: SimulationEnvironment):
            for i in range(5):
                sim.record("agent", f"step-{i}")

        result = run()
        assert result.passed
        assert len(result.events) == 5

    def test_decorator_catches_budget_exceeded(self):
        @simulate("budget-test", max_steps=3)
        def run(sim: SimulationEnvironment):
            for i in range(10):
                sim.record("agent", f"step-{i}")

        result = run()
        # Should not raise, decorator catches SimulationBudgetExceeded
        assert len(result.events) >= 3


# === Coordination Tests ===


class TestConsensus:
    def test_unanimous_consensus(self):
        outputs = [
            AgentOutput(agent="a", output="yes"),
            AgentOutput(agent="b", output="yes"),
            AgentOutput(agent="c", output="yes"),
        ]
        result = check_consensus(outputs)
        assert result.passed

    def test_consensus_failure(self):
        outputs = [
            AgentOutput(agent="a", output="yes"),
            AgentOutput(agent="b", output="no"),
            AgentOutput(agent="c", output="yes"),
        ]
        result = check_consensus(outputs)
        assert not result.passed
        assert CoordinationIssue.CONSENSUS_FAILURE in result.issues

    def test_quorum_consensus(self):
        outputs = [
            AgentOutput(agent="a", output="yes"),
            AgentOutput(agent="b", output="yes"),
            AgentOutput(agent="c", output="no"),
        ]
        result = check_consensus(outputs, quorum=0.6)
        assert result.passed

    def test_empty_outputs(self):
        result = check_consensus([])
        assert result.passed


class TestMemoryIntegrity:
    def test_identical_states(self):
        snapshots = [
            MemorySnapshot(agent="a", state={"key": "val"}, version=1),
            MemorySnapshot(agent="b", state={"key": "val"}, version=1),
        ]
        result = check_memory_integrity(snapshots)
        assert result.passed

    def test_divergent_states(self):
        snapshots = [
            MemorySnapshot(agent="a", state={"key": "val1"}, version=1),
            MemorySnapshot(agent="b", state={"key": "val2"}, version=1),
        ]
        result = check_memory_integrity(snapshots)
        assert not result.passed
        assert CoordinationIssue.MEMORY_DIVERGENCE in result.issues

    def test_stale_version(self):
        snapshots = [
            MemorySnapshot(agent="a", state={"x": 1}, version=3),
            MemorySnapshot(agent="b", state={"x": 1}, version=1),
        ]
        result = check_memory_integrity(snapshots)
        assert not result.passed
        assert CoordinationIssue.STALE_STATE in result.issues


class TestDivergence:
    def test_similar_traces(self):
        traces = [
            BehaviorTrace(agent="a", actions=["search", "summarize", "respond"]),
            BehaviorTrace(agent="b", actions=["search", "summarize", "respond"]),
        ]
        result = check_divergence(traces)
        assert result.passed

    def test_divergent_traces(self):
        traces = [
            BehaviorTrace(
                agent="a", actions=["search", "summarize", "respond"]
            ),
            BehaviorTrace(
                agent="b",
                actions=["browse", "analyze", "critique", "rewrite", "respond"],
            ),
        ]
        result = check_divergence(traces, max_edit_distance=2)
        assert not result.passed
        assert CoordinationIssue.BEHAVIORAL_DRIFT in result.issues

    def test_single_trace(self):
        traces = [BehaviorTrace(agent="a", actions=["x"])]
        result = check_divergence(traces)
        assert result.passed


# === Integration: Simulation + Replay ===


class TestSimulationReplayIntegration:
    def test_simulation_with_replay(self, tmp_path):
        from specops.replay import ReplayStore

        store = ReplayStore(base_dir=tmp_path)

        @replayable
        def fake_llm(prompt: str) -> str:
            return f"response to: {prompt}"

        # Record inside simulation
        with (
            simulation("replay-sim", max_steps=10) as sim,
            recording(session_id="sim-session", seed=42, store=store),
        ):
            result = fake_llm("hello")
            sim.record("agent", "llm_call", result=result)

        # Replay inside simulation
        with (
            simulation("replay-sim-2", max_steps=10) as sim,
            replaying("sim-session", store=store),
        ):
            replayed = fake_llm("hello")
            sim.record("agent", "llm_call", result=replayed)

        assert result == replayed


# === Integration: Simulation + Eval ===


class TestSimulationEvalIntegration:
    def test_eval_inside_simulation(self):
        def agent(inp: str) -> str:
            sim = get_current_simulation()
            if sim:
                sim.record("eval-agent", f"process:{inp}")
            return inp.upper()

        with simulation("eval-sim", max_steps=50) as sim:
            results = eval_golden_set(
                agent_fn=agent,
                cases=[
                    EvalCase(input="hello", expected="HELLO"),
                    EvalCase(input="world", expected="WORLD"),
                ],
            )

        assert all(r.passed for r in results)
        assert sim.step_count == 2


# === Integration: Simulation + Self-Healing ===


class TestSimulationHealIntegration:
    def test_healing_inside_simulation(self):
        call_count = 0

        @self_healing(retry=RetryPolicy(max_retries=2, base_delay=0.01))
        def flaky_fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient")
            return "ok"

        with simulation("heal-sim", max_steps=10) as sim:
            result = flaky_fn()
            sim.record("agent", "healed_call", result=result)

        assert result == "ok"
        assert sim.step_count == 1

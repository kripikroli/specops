"""Example: SpecOps Simulation Demo — Core Reliability Features.

A comprehensive demo showcasing how SpecOps detects and handles emergent
agent failures: loops, cascades, self-healing recovery, multi-agent
coordination, and deterministic replay — all in one scenario.

Run:
    uv run examples/simulation_demo.py

Mock mode (no API key needed):
    SPECOPS_EXAMPLE_MODE=mock uv run examples/simulation_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.utils import require_api_key

from specops_ai import (
    AgentOutput,
    BehaviorTrace,
    FallbackPolicy,
    MemorySnapshot,
    RetryPolicy,
    SimulationEnvironment,
    check_consensus,
    check_divergence,
    check_memory_integrity,
    recording,
    replayable,
    replaying,
    self_healing,
    simulate,
    trace_agent,
    trace_llm,
    trace_tool,
)

# --- Graceful skip: require key (mock mode returns placeholder) ---
_api_key = require_api_key("OPENAI_API_KEY", "OpenAI")


# ============================================================
# 1. Self-Healing LLM with Tracing
# ============================================================


def fallback_llm(prompt: str) -> str:
    """Fallback that returns a safe default response."""
    return f"[fallback] Processed: {prompt[:40]}..."


@self_healing(
    retry=RetryPolicy(max_retries=2, base_delay=0.01),
    fallback=FallbackPolicy(fallback_fn=fallback_llm),
)
@trace_llm(model="gpt-4o-mini", provider="openai")
@replayable
def call_llm(prompt: str) -> str:
    """Simulated LLM that fails on long prompts (triggers self-healing)."""
    if len(prompt) > 100:
        raise TimeoutError("LLM timeout on long input")
    return f"Response to: {prompt[:50]}"


@trace_tool(name="search")
@replayable
def search_tool(query: str) -> list[str]:
    """Simulated search tool."""
    return [f"result-1: {query}", f"result-2: {query}"]


# ============================================================
# 2. Simulation: Loop Detection + Cascade
# ============================================================


@simulate("loop-and-cascade", max_steps=30, loop_threshold=3, token_budget=2000)
def run_simulation(sim: SimulationEnvironment) -> None:
    """Demonstrate loop detection and cascade failure in a sandbox."""
    print("\n[Phase 1] Loop Detection")
    print("   Agent repeats 'retry_fetch' — SpecOps catches the loop.")

    # Trigger LOOP anomaly: same action repeated 3 times
    for _i in range(4):
        event = sim.record("data-agent", "retry_fetch")
        if event.anomaly:
            print(f"   [!] LOOP detected at step {event.step}!")
            break

    print("\n[Phase 2] Cascade Failure")
    print("   Pipeline agents propagate failure — SpecOps tracks cascade.")

    # Simulate a cascade: agent-a fails, agent-b and agent-c follow
    sim.record("agent-a", "process_input")
    sim.record("agent-a", "fail_validation")
    sim.record("agent-b", "receive_bad_data")
    sim.record("agent-b", "fail_validation")  # starts repeating
    sim.record("agent-c", "receive_bad_data")
    sim.record("agent-c", "fail_validation")
    sim.record("agent-c", "fail_validation")
    event = sim.record("agent-c", "fail_validation")
    if event.anomaly:
        print(f"   [!] CASCADE pattern at step {event.step}: {event.anomaly.value}")

    print(f"\n   Total steps: {sim.step_count}, Tokens used: {sim.tokens_used}")


# ============================================================
# 3. Self-Healing in Action
# ============================================================


@trace_agent(name="resilient-agent")
def run_self_healing() -> str:
    """Show self-healing: retry + fallback on a failing LLM call."""
    print("\n[Phase 3] Self-Healing")
    print("   Calling LLM with oversized prompt — triggers retry then fallback.")

    long_prompt = "Analyze this data: " + "x" * 200
    result = call_llm(long_prompt)
    print(f"   [OK] Recovered via fallback: {result}")
    return result


# ============================================================
# 4. Multi-Agent Coordination
# ============================================================


def run_coordination() -> None:
    """Demonstrate consensus, memory integrity, and divergence checks."""
    print("\n[Phase 4] Multi-Agent Coordination")

    # Consensus check
    outputs = [
        AgentOutput(agent="analyst-1", output="approve"),
        AgentOutput(agent="analyst-2", output="approve"),
        AgentOutput(agent="analyst-3", output="reject"),
    ]
    consensus = check_consensus(outputs, quorum=0.6)
    print(f"   Consensus (quorum=0.6): passed={consensus.passed}")

    # Memory integrity
    snapshots = [
        MemorySnapshot(agent="writer", state={"count": 10}, version=3),
        MemorySnapshot(agent="reader", state={"count": 10}, version=3),
        MemorySnapshot(agent="stale-reader", state={"count": 7}, version=1),
    ]
    integrity = check_memory_integrity(snapshots)
    print(f"   Memory integrity: passed={integrity.passed}")
    if integrity.issues:
        print(f"   Issues: {[i.value for i in integrity.issues]}")

    # Divergence detection
    traces = [
        BehaviorTrace(agent="a", actions=["search", "summarize", "respond"]),
        BehaviorTrace(agent="b", actions=["search", "summarize", "respond"]),
        BehaviorTrace(agent="c", actions=["browse", "parse", "translate", "respond"]),
    ]
    divergence = check_divergence(traces, max_edit_distance=2)
    print(f"   Divergence (max_edit=2): passed={divergence.passed}")


# ============================================================
# 5. Replay Capability
# ============================================================


def run_replay() -> None:
    """Record and replay agent calls deterministically."""
    print("\n[Phase 5] Deterministic Replay")

    # Record
    with recording(session_id="sim-demo", seed=42) as session:
        r1 = search_tool("specops reliability")
        r2 = call_llm("Summarize: short query")
    print(f"   Recorded {len(session.calls)} calls")

    # Replay
    with replaying("sim-demo"):
        r1_replay = search_tool("specops reliability")
        r2_replay = call_llm("Summarize: short query")

    print(f"   Search match: {r1 == r1_replay}")
    print(f"   LLM match: {r2 == r2_replay}")


# ============================================================
# Main
# ============================================================


def main() -> None:
    """Run the full SpecOps simulation demo."""
    print("=" * 60)
    print("  SpecOps AI — Simulation Demo")
    print("  Demonstrating: Simulation · Self-Healing · Coordination · Replay")
    print("=" * 60)

    # 1. Simulation sandbox (loop + cascade detection)
    result = run_simulation()
    print(f"\n   Simulation passed: {result.passed}")
    print(f"   Anomalies detected: {len(result.anomalies)}")
    for a in result.anomalies:
        print(f"     - Step {a.step}: {a.agent} → {a.anomaly.value}")

    # 2. Self-healing
    run_self_healing()

    # 3. Coordination checks
    run_coordination()

    # 4. Replay
    run_replay()

    print("\n" + "=" * 60)
    print("  Demo complete — all SpecOps reliability features demonstrated!")
    print("=" * 60)


if __name__ == "__main__":
    main()

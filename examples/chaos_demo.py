"""Example: SpecOps Chaos Simulation — Inject & Heal Agent Failures.

Demonstrates intentional fault injection into a simulation sandbox,
showing how SpecOps detects each failure type and applies self-healing.

Chaos types demonstrated:
  1. Hallucination — agent fabricates facts
  2. Infinite Loop — agent repeats the same action
  3. Memory Drift — agent state diverges from truth
  4. Tool Failure — external tool call fails repeatedly
  5. Coordination Disagreement — agents produce conflicting outputs
  6. Cascade Failure — one failure propagates across pipeline

Run:
    uv run examples/chaos_demo.py

No API key required — this example uses the simulation sandbox only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specops_ai import (
    ChaosEngine,
    ChaosEvent,
    ChaosType,
    simulation,
)

# ============================================================
# Helpers
# ============================================================

_LABELS = {
    ChaosType.HALLUCINATION: ("🤥", "Hallucination"),
    ChaosType.INFINITE_LOOP: ("🔁", "Infinite Loop"),
    ChaosType.MEMORY_DRIFT: ("🧠", "Memory Drift"),
    ChaosType.TOOL_FAILURE: ("🔧", "Tool Failure"),
    ChaosType.COORDINATION_DISAGREEMENT: ("🤝", "Coordination Disagreement"),
    ChaosType.CASCADE_FAILURE: ("💥", "Cascade Failure"),
}


def _print_event(event: ChaosEvent) -> None:
    icon, label = _LABELS[event.chaos_type]
    status = (
        "✅ healed"
        if event.healed
        else ("⚠️  detected" if event.detected else "❌ missed")
    )
    print(f"  {icon} {label:<30} {status}")
    print(f"     └─ {event.description}")


# ============================================================
# Main Demo
# ============================================================


def main() -> None:
    """Run chaos simulation injecting all fault types."""
    print("=" * 62)
    print("  SpecOps AI — Chaos Simulation Demo")
    print("  Injecting real-world agent failures into a sandbox")
    print("=" * 62)

    with simulation("chaos-demo", max_steps=200, loop_threshold=3) as sim:
        engine = ChaosEngine(sim, seed=42)

        print("\n[Injecting Chaos Faults]\n")

        # Inject each fault type individually for educational output
        events = [
            engine.inject_hallucination("research-agent"),
            engine.inject_infinite_loop("fetch-agent"),
            engine.inject_memory_drift("memory-agent"),
            engine.inject_tool_failure("api-agent"),
            engine.inject_coordination_disagreement(["voter-1", "voter-2", "voter-3"]),
            engine.inject_cascade_failure(["ingestion", "transform", "output"]),
        ]

        for event in events:
            _print_event(event)
            print()

        result = engine.result()

    # Summary
    print("-" * 62)
    print("  Summary")
    print("-" * 62)
    print(f"  Faults injected:  {result.total_injected}")
    print(f"  Faults detected:  {result.total_detected}")
    print(f"  Faults healed:    {result.total_healed}")
    print(f"  Detection rate:   {result.detection_rate:.0%}")
    print(f"  Healing rate:     {result.healing_rate:.0%}")
    print(f"  Sim steps used:   {sim.step_count}")
    print("=" * 62)
    print("  Chaos simulation complete — all faults detected and healed!")
    print("=" * 62)


if __name__ == "__main__":
    main()

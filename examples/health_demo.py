"""Example: SpecOps Agent Health Score — Instant Reliability Visibility.

Demonstrates the Agent Health Score (0-100) that combines multiple
reliability signals into a single, intuitive metric. Shows both the
simple one-line API and the expert mode with custom weights.

Signals measured:
  1. Loop Rate — How often the agent repeats actions
  2. Consensus — Multi-agent coordination success rate
  3. Memory Integrity — State consistency over time
  4. Self-Healing — Recovery effectiveness after failures
  5. Chaos Resilience — Fault detection and healing rate
  6. Regression Stability — Behavioral consistency vs golden runs
  7. Anomaly Frequency — Rate of unexpected behaviors

Run:
    uv run examples/health_demo.py

No API key required — uses simulated signals for educational output.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from specops_ai import (
    DEFAULT_WEIGHTS,
    HealthCheckFailed,
    compute_health_score,
    health_check,
)

# ============================================================
# Helpers
# ============================================================

_SIGNAL_DESCRIPTIONS = {
    "loop_rate": ("🔁", "Loop Rate", "Fraction of repeated actions (lower is better)"),
    "consensus": ("🤝", "Consensus", "Multi-agent agreement rate"),
    "memory_integrity": ("🧠", "Memory Integrity", "State consistency checks passed"),
    "self_healing": ("💊", "Self-Healing", "Successful recovery from failures"),
    "chaos_resilience": ("🔥", "Chaos Resilience", "Faults detected and healed"),
    "regression_stability": (
        "📏",
        "Regression Stability",
        "Behavioral consistency score",
    ),
    "anomaly_frequency": (
        "⚠️ ",
        "Anomaly Frequency",
        "Rate of anomalies (lower is better)",
    ),
}


def _print_report(report) -> None:  # noqa: ANN001
    """Print a formatted health report with educational breakdown."""
    grade_colors = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "F": "⛔"}
    icon = grade_colors.get(report.grade, "⚪")

    print(f"\n  {icon} Health Score: {report.score:.1f}/100 (Grade: {report.grade})")
    if report.agent_name:
        print(f"     Agent: {report.agent_name}")
    print(f"     Status: {'✅ PASSED' if report.passed else '❌ FAILED'}")
    print()
    print("  Signal Breakdown:")
    print("  " + "-" * 56)
    for signal in report.signals:
        emoji, label, desc = _SIGNAL_DESCRIPTIONS.get(
            signal.name, ("•", signal.name, "")
        )
        bar = "█" * int(signal.value * 10) + "░" * (10 - int(signal.value * 10))
        pct = signal.value * 100
        print(f"  {emoji} {label:<22} [{bar}] {pct:5.1f}%  (w={signal.weight:.2f})")
        if desc:
            print(f"     └─ {desc}")
    print()


# ============================================================
# Demo Scenarios
# ============================================================


def main() -> None:
    """Run health score demo with multiple scenarios."""
    print("=" * 62)
    print("  SpecOps AI — Agent Health Score Demo")
    print("  Instant visibility into agent reliability (0-100)")
    print("=" * 62)

    # --- Scenario 1: Healthy Agent ---
    print("\n" + "─" * 62)
    print("  Scenario 1: Healthy Production Agent")
    print("  All systems nominal — agent operating at peak reliability")
    print("─" * 62)

    report = compute_health_score(
        loop_rate=0.02,
        consensus=0.95,
        memory_integrity=0.98,
        self_healing=0.90,
        chaos_resilience=0.88,
        regression_stability=0.95,
        anomaly_frequency=0.03,
        agent_name="production-agent",
    )
    _print_report(report)

    # --- Scenario 2: Degraded Agent ---
    print("─" * 62)
    print("  Scenario 2: Degraded Agent (Needs Attention)")
    print("  Self-healing struggling, loops detected, some drift")
    print("─" * 62)

    report = compute_health_score(
        loop_rate=0.25,
        consensus=0.70,
        memory_integrity=0.80,
        self_healing=0.50,
        chaos_resilience=0.60,
        regression_stability=0.65,
        anomaly_frequency=0.20,
        agent_name="degraded-agent",
    )
    _print_report(report)

    # --- Scenario 3: Critical Agent ---
    print("─" * 62)
    print("  Scenario 3: Critical Agent (Immediate Action Required)")
    print("  Stuck in loops, consensus failing, high anomaly rate")
    print("─" * 62)

    report = compute_health_score(
        loop_rate=0.80,
        consensus=0.20,
        memory_integrity=0.30,
        self_healing=0.10,
        chaos_resilience=0.15,
        regression_stability=0.25,
        anomaly_frequency=0.70,
        agent_name="critical-agent",
    )
    _print_report(report)

    # --- Scenario 4: Custom Weights (Expert Mode) ---
    print("─" * 62)
    print("  Scenario 4: Expert Mode — Custom Weights")
    print("  Prioritizing self-healing and chaos resilience for a")
    print("  fault-tolerant pipeline where loops are acceptable")
    print("─" * 62)

    custom_weights = {
        "loop_rate": 0.05,
        "consensus": 0.10,
        "memory_integrity": 0.10,
        "self_healing": 0.30,
        "chaos_resilience": 0.30,
        "regression_stability": 0.10,
        "anomaly_frequency": 0.05,
    }
    report = compute_health_score(
        loop_rate=0.40,
        consensus=0.60,
        memory_integrity=0.70,
        self_healing=0.95,
        chaos_resilience=0.92,
        regression_stability=0.80,
        anomaly_frequency=0.15,
        weights=custom_weights,
        agent_name="fault-tolerant-pipeline",
    )
    _print_report(report)
    print("  💡 With custom weights emphasizing healing over loops,")
    print("     this agent scores well despite moderate loop rate.")

    # --- Scenario 5: @health_check Decorator ---
    print("\n" + "─" * 62)
    print("  Scenario 5: @health_check Decorator")
    print("  Automatic health monitoring on every agent call")
    print("─" * 62)

    @health_check(name="monitored-agent", threshold=40.0)
    def my_agent(task: str) -> dict[str, float]:
        # Simulate agent returning its own health signals
        return {
            "loop_rate": 0.05,
            "consensus": 0.90,
            "self_healing": 0.85,
            "chaos_resilience": 0.80,
        }

    result = my_agent("summarize documents")
    print(f"\n  Agent returned: {result}")
    _print_report(my_agent.last_health_report)

    # --- Scenario 6: Health Check Failure ---
    print("─" * 62)
    print("  Scenario 6: Health Check Failure (Threshold Enforcement)")
    print("  Agent below minimum health threshold → exception raised")
    print("─" * 62)

    @health_check(name="failing-agent", threshold=70.0)
    def bad_agent() -> dict[str, float]:
        return {"self_healing": 0.0, "consensus": 0.1, "loop_rate": 0.9}

    try:
        bad_agent()
    except HealthCheckFailed as e:
        print(f"\n  ⛔ HealthCheckFailed: {e}")
        print(f"     Score: {e.report.score:.1f}, Threshold: 70.0")
        print("     → Agent needs intervention before resuming")

    # --- Summary ---
    print("\n" + "=" * 62)
    print("  Summary: Default Signal Weights")
    print("=" * 62)
    print()
    for name, weight in DEFAULT_WEIGHTS.items():
        emoji = _SIGNAL_DESCRIPTIONS[name][0]
        label = _SIGNAL_DESCRIPTIONS[name][1]
        print(f"  {emoji} {label:<22} {weight:.0%}")
    print()
    print("  Total: 100%")
    print()
    print("=" * 62)
    print("  Health score demo complete!")
    print("  Use compute_health_score() for one-line health checks")
    print("  Use @health_check for automatic monitoring on every call")
    print("=" * 62)


if __name__ == "__main__":
    main()

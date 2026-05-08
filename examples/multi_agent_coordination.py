"""Example: Multi-agent coordination checks.

Demonstrates consensus checking, memory integrity validation,
and behavioral divergence detection across cooperating agents.
"""

from specops import (
    AgentOutput,
    BehaviorTrace,
    MemorySnapshot,
    check_consensus,
    check_divergence,
    check_memory_integrity,
)


def consensus_example():
    """Check if multiple agents agree on a classification task."""
    # Three agents classify the same input
    outputs = [
        AgentOutput(agent="classifier-1", output="positive", metadata={"confidence": 0.92}),
        AgentOutput(agent="classifier-2", output="positive", metadata={"confidence": 0.87}),
        AgentOutput(agent="classifier-3", output="negative", metadata={"confidence": 0.51}),
    ]

    # Require unanimous agreement
    result = check_consensus(outputs, quorum=1.0)
    print(f"Unanimous: passed={result.passed}")
    print(f"  Details: {result.details}")

    # Require 2/3 majority
    result = check_consensus(outputs, quorum=0.6)
    print(f"Majority:  passed={result.passed}")
    print(f"  Details: {result.details}")


def memory_integrity_example():
    """Verify agents have consistent shared state."""
    # Agents reading from shared memory
    snapshots = [
        MemorySnapshot(agent="writer", state={"counter": 42, "status": "active"}, version=5),
        MemorySnapshot(agent="reader-1", state={"counter": 42, "status": "active"}, version=5),
        MemorySnapshot(agent="reader-2", state={"counter": 40, "status": "active"}, version=3),
    ]

    result = check_memory_integrity(snapshots)
    print(f"Memory check: passed={result.passed}")
    print(f"  Details: {result.details}")
    for issue in result.issues:
        print(f"  Issue: {issue.value}")


def divergence_example():
    """Detect when agents solving the same task take very different paths."""
    traces = [
        BehaviorTrace(
            agent="agent-a",
            actions=["search", "read", "summarize", "respond"],
        ),
        BehaviorTrace(
            agent="agent-b",
            actions=["search", "read", "verify", "summarize", "respond"],
        ),
        BehaviorTrace(
            agent="agent-c",
            actions=["browse", "download", "parse", "reformat", "translate", "respond"],
        ),
    ]

    # Allow up to 2 edits difference
    result = check_divergence(traces, max_edit_distance=2)
    print(f"Divergence check: passed={result.passed}")
    print(f"  Details: {result.details}")


if __name__ == "__main__":
    print("=== Consensus Check ===")
    consensus_example()

    print("\n=== Memory Integrity ===")
    memory_integrity_example()

    print("\n=== Divergence Detection ===")
    divergence_example()

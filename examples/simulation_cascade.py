"""Example: Simulating cascading failures with self-healing.

Demonstrates combining the simulation sandbox with self-healing policies
to test how agents recover from cascading failures.
"""

from specops import (
    FallbackPolicy,
    RetryPolicy,
    SimulationEnvironment,
    self_healing,
    simulation,
)


def backup_summarizer(text: str) -> str:
    """Fallback that returns a simple extractive summary."""
    sentences = text.split(". ")
    return sentences[0] if sentences else text[:100]


@self_healing(
    retry=RetryPolicy(max_retries=2, base_delay=0.01),
    fallback=FallbackPolicy(fallback_fn=backup_summarizer),
)
def summarize(text: str) -> str:
    """Simulated LLM summarizer that fails intermittently."""
    # In a real scenario, this would call an LLM API
    if len(text) > 200:
        raise TimeoutError("LLM timeout on long input")
    return f"Summary: {text[:50]}..."


def run_cascade_simulation():
    """Simulate a pipeline where failures cascade through agents."""
    documents = [
        "Short document about AI safety.",
        "A" * 300,  # Long doc that triggers timeout
        "Medium length document about multi-agent systems and coordination.",
    ]

    with simulation("cascade-test", max_steps=20, token_budget=1000) as sim:
        results = []
        for i, doc in enumerate(documents):
            sim.record("orchestrator", f"dispatch-doc-{i}")
            try:
                summary = summarize(doc)
                sim.record("summarizer", f"success-doc-{i}", result=summary)
                sim.add_tokens(len(doc))
            except Exception as e:
                sim.record("summarizer", f"failed-doc-{i}", result=str(e))
            results.append(summary if "summary" in dir() else None)

        result = sim.stop()

    print(f"Scenario: {result.scenario}")
    print(f"Steps: {len(result.events)}")
    print(f"Passed: {result.passed}")
    print(f"Duration: {result.duration:.3f}s")
    for event in result.events:
        status = f" [{event.anomaly.value}]" if event.anomaly else ""
        print(f"  Step {event.step}: {event.agent} → {event.action}{status}")


if __name__ == "__main__":
    print("=== Cascade Failure Simulation ===")
    run_cascade_simulation()

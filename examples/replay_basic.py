"""Example: Recording and replaying an agent session.

Demonstrates how to use @replayable + recording/replaying context managers
to capture non-deterministic LLM calls and replay them deterministically.
"""

import random

from specops_ai import recording, replayable, replaying, trace_agent, trace_tool


@replayable
def call_llm(prompt: str) -> str:
    """Simulate a non-deterministic LLM call."""
    responses = [
        "The capital of France is Paris.",
        "Paris is the capital of France.",
        "France's capital city is Paris.",
    ]
    return random.choice(responses)


@trace_tool(name="search")
@replayable
def search(query: str) -> list[str]:
    """Simulate a search tool with non-deterministic results."""
    return [f"result_{random.randint(1, 100)}" for _ in range(3)]


@trace_agent(name="research-agent")
def research_agent(task: str) -> str:
    results = search(task)
    prompt = f"Summarize these results about '{task}': {results}"
    return call_llm(prompt)


def main() -> None:
    # --- Record a session ---
    print("=== Recording Session ===")
    with recording(session_id="demo-session", seed=42) as session:
        result1 = research_agent("capital of France")
        print(f"Result: {result1}")
        print(f"Recorded {len(session.calls)} calls")

    print(f"\nSession saved: {session.session_id}")
    print(f"Seed: {session.seed}")

    # --- Replay the same session ---
    print("\n=== Replaying Session ===")
    with replaying("demo-session") as replay_session:  # noqa: F841
        result2 = research_agent("capital of France")
        print(f"Result: {result2}")

    # Results are identical
    print(f"\nResults match: {result1 == result2}")


if __name__ == "__main__":
    main()

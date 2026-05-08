"""Example: Async replay combined with evaluation.

Shows how to record an async agent session and then evaluate it
deterministically using replay + golden-set comparison.
"""

import asyncio
import random

from specops import (
    EvalCase,
    eval_golden_set_async,
    replayable,
    recording,
    replaying,
    trace_agent,
)


@replayable
async def async_llm_call(prompt: str) -> str:
    """Simulate an async LLM call."""
    await asyncio.sleep(0.01)  # Simulate latency
    templates = [
        f"Answer: {random.randint(1, 10)}",
        f"The result is {random.randint(1, 10)}",
    ]
    return random.choice(templates)


@trace_agent(name="async-math-agent")
async def math_agent(task: str) -> str:
    """Agent that answers math questions (simulated)."""
    return await async_llm_call(f"Solve: {task}")


async def main() -> None:
    # Record a session with a fixed seed for reproducibility
    print("=== Recording Async Session ===")
    with recording(session_id="async-demo", seed=123):
        r1 = await math_agent("2+2")
        r2 = await math_agent("3*3")
        print(f"  2+2 → {r1}")
        print(f"  3*3 → {r2}")

    # Replay produces identical results
    print("\n=== Replaying Async Session ===")
    with replaying("async-demo"):
        r1_replay = await math_agent("2+2")
        r2_replay = await math_agent("3*3")
        print(f"  2+2 → {r1_replay}")
        print(f"  3*3 → {r2_replay}")

    print(f"\n  Deterministic: {r1 == r1_replay and r2 == r2_replay}")

    # Evaluate using the replayed (deterministic) agent
    print("\n=== Async Evaluation with Replay ===")
    cases = [
        EvalCase(input="2+2", expected=r1),  # Use recorded output as golden
        EvalCase(input="3*3", expected=r2),
    ]

    async def replayed_agent(task: str) -> str:
        with replaying("async-demo"):
            return await math_agent(task)

    results = await eval_golden_set_async(replayed_agent, cases)
    for r in results:
        status = "✓" if r.passed else "✗"
        print(f"  {status} '{r.case.input}' → score={r.score:.1f}")


if __name__ == "__main__":
    asyncio.run(main())

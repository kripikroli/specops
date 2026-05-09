"""Example: Self-healing LLM calls with retry and fallback.

Demonstrates how to use @self_healing to automatically recover from
LLM provider failures using retry with backoff and fallback to a
cheaper model.
"""

from specops_ai import (
    FallbackPolicy,
    RetryPolicy,
    self_healing,
    trace_agent,
    trace_llm,
)

# Simulate a flaky primary model
_call_count = 0


def fallback_llm(prompt: str) -> str:
    """Cheap fallback model that always works."""
    return f"[fallback] Summary of: {prompt[:50]}"


@self_healing(
    retry=RetryPolicy(max_retries=2, base_delay=0.1),
    fallback=FallbackPolicy(fallback_fn=fallback_llm),
)
@trace_llm(model="gpt-4o", provider="openai")
def call_primary_llm(prompt: str) -> dict[str, str | int]:
    """Simulate a flaky LLM that fails 2 out of 3 times."""
    global _call_count
    _call_count += 1
    if _call_count % 3 != 0:
        raise TimeoutError("LLM provider timeout")
    return {
        "text": f"Summary: {prompt[:30]}",
        "model": "gpt-4o",
        "input_tokens": 10,
        "output_tokens": 25,
    }


@trace_agent(name="resilient-agent")
def run(task: str) -> str:
    """Agent that uses self-healing LLM calls."""
    result = call_primary_llm(f"Summarize: {task}")
    if isinstance(result, dict):
        return str(result["text"])
    return str(result)


if __name__ == "__main__":
    print("=== Self-Healing Example ===")
    for i in range(3):
        result = run(f"Task {i}: Explain quantum computing")
        print(f"  Run {i + 1}: {result}")
    print("\nAll calls succeeded despite flaky provider!")

"""Example: Self-healing with memory pruning and escalation.

Demonstrates the full healing chain: retry → prune_memory → escalate.
Shows how token limit errors trigger memory pruning before escalation.
"""

from specops_ai import (
    EscalatePolicy,
    PruneMemoryPolicy,
    RetryPolicy,
    self_healing,
    trace_agent,
    trace_llm,
)

# Simulate token limit tracking
_max_tokens = 100


def prune_context(
    args: tuple[object, ...], kwargs: dict[str, object]
) -> tuple[tuple[object, ...], dict[str, object]]:
    """Prune the prompt by keeping only the last half."""
    if args:
        prompt = str(args[0])
        pruned = prompt[len(prompt) // 2 :]
        return (pruned, *args[1:]), kwargs
    return args, kwargs


def human_handler(
    func_name: str, args: tuple[object, ...], kwargs: dict[str, object], exc: Exception
) -> str:
    """Simulate human escalation."""
    print(f"  [ESCALATED] {func_name} failed: {exc}")
    return "[human-provided answer]"


@self_healing(
    retry=RetryPolicy(max_retries=1, base_delay=0.05),
    prune_memory=PruneMemoryPolicy(prune_fn=prune_context, max_prunes=2),
    escalate=EscalatePolicy(handler=human_handler),
)
@trace_llm(model="gpt-4o", provider="openai")
def call_llm(prompt: str) -> dict[str, str | int]:
    """LLM that fails on long prompts (simulating token limits)."""
    if len(prompt) > _max_tokens:
        raise ValueError(f"Token limit exceeded: {len(prompt)} > {_max_tokens}")
    return {
        "text": f"Answer for: {prompt[:30]}...",
        "model": "gpt-4o",
        "input_tokens": len(prompt),
        "output_tokens": 20,
    }


@trace_agent(name="memory-aware-agent")
def run(task: str) -> str:
    """Agent that handles token limits via memory pruning."""
    # Build a long context that exceeds token limit
    context = f"Context: {'x' * 200}\nTask: {task}"
    result = call_llm(context)
    if isinstance(result, dict):
        return str(result["text"])
    return str(result)


if __name__ == "__main__":
    print("=== Self-Healing with Memory Pruning ===")
    result = run("What is the meaning of life?")
    print(f"  Result: {result}")
    print("\nAgent recovered via memory pruning or escalation!")

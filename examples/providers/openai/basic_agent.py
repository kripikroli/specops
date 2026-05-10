"""Example: Basic OpenAI agent with SpecOps tracing.

A minimal example using the OpenAI API directly (no LangGraph).

Run:
    uv run examples/providers/openai/basic_agent.py

Mock mode:
    SPECOPS_EXAMPLE_MODE=mock uv run examples/providers/openai/basic_agent.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_examples_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_examples_dir))

from shared.models import get_model  # noqa: E402
from shared.utils import require_api_key  # noqa: E402

from specops_ai import trace_agent  # noqa: E402

api_key = require_api_key("OPENAI_API_KEY", "OpenAI")


@trace_agent(name="basic-openai-agent")
def run_agent(task: str) -> str:
    """Ask OpenAI a question with SpecOps tracing."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        return "SpecOps AI is a toolkit for making LLM agents reliable. (mock)"

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    model = get_model("openai")
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": task}],
        temperature=0,
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print("=" * 60)
    print("SpecOps AI — Basic Agent (OpenAI)")
    print("=" * 60)

    task = "Explain what SpecOps AI is in one sentence."
    print(f"\nTask: {task}")
    print("-" * 60)

    answer = run_agent(task)

    print(f"\nAnswer: {answer}")
    print("-" * 60)
    print("✓ Tracing active (trace_agent span emitted)")
    print("=" * 60)

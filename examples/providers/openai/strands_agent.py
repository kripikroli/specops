"""Example: Strands Agents SDK with SpecOps tracing (OpenAI).

Demonstrates a Strands agent with tool use and SpecOps tracing.

Setup:
    pip install specops-ai[strands]
    cp .env.example .env  # fill in OPENAI_API_KEY

Run:
    uv run examples/providers/openai/strands_agent.py

Mock mode (no API key or strands needed):
    SPECOPS_EXAMPLE_MODE=mock uv run examples/providers/openai/strands_agent.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_examples_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_examples_dir))

from shared.models import get_model  # noqa: E402
from shared.utils import require_api_key  # noqa: E402

from specops_ai import trace_agent, trace_tool  # noqa: E402

api_key = require_api_key("OPENAI_API_KEY", "OpenAI")


@trace_tool(name="search_docs")
def search_docs(query: str) -> str:
    """Search documentation for relevant information."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        return f"Doc result: {query} — agents use OTel spans for observability."
    return f"Documentation about: {query}"


@trace_agent(name="strands-openai-agent", framework="strands")
def run_strands_agent(prompt: str) -> str:
    """Run a Strands agent with OpenAI backend."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        print("  [mock] Agent processing prompt")
        result = search_docs(prompt)
        print(f"  [mock] Tool result: {result}")
        summary = f"Based on research: {result}"
        print(f"  [mock] Agent response: {summary}")
        return summary

    try:
        from strands import Agent
        from strands.models.openai import OpenAIModel
    except ImportError:
        print(
            "[SKIP] strands-agents not installed. Run: pip install specops-ai[strands]"
        )
        sys.exit(0)

    model = OpenAIModel(
        client_args={"api_key": api_key},
        model_id=get_model("openai"),
    )
    agent = Agent(model=model)
    response = agent(prompt)
    return str(response)


if __name__ == "__main__":
    print("=" * 60)
    print("SpecOps AI — Strands Agent Example (OpenAI)")
    print("=" * 60)

    prompt = "Explain how SpecOps AI improves agent reliability"
    print(f"\nPrompt: {prompt}")
    print("-" * 60)

    output = run_strands_agent(prompt)

    print(f"\nFinal output:\n{output}")
    print("-" * 60)
    print("✓ Tracing active (trace_agent + trace_tool spans emitted)")
    print("=" * 60)

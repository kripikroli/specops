"""Example: AutoGen multi-agent chat with SpecOps tracing (Anthropic).

Demonstrates a RoundRobinGroupChat with Researcher + Writer agents.

Setup:
    pip install specops-ai[autogen]
    cp .env.example .env  # fill in ANTHROPIC_API_KEY

Run:
    uv run examples/providers/anthropic/autogen_agent.py

Mock mode (no API key or autogen needed):
    SPECOPS_EXAMPLE_MODE=mock uv run examples/providers/anthropic/autogen_agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_examples_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_examples_dir))

from shared.models import get_model  # noqa: E402
from shared.utils import require_api_key  # noqa: E402

from specops_ai import trace_agent, trace_tool  # noqa: E402

api_key = require_api_key("ANTHROPIC_API_KEY", "Anthropic")


@trace_tool(name="lookup_fact")
def lookup_fact(topic: str) -> str:
    """Tool that looks up a fact about a topic."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        return f"Fact: {topic} enables reliable AI agents via OTel-native tracing."
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=get_model("anthropic"),
        max_tokens=256,
        messages=[{"role": "user", "content": f"State one key fact about: {topic}"}],
    )
    return message.content[0].text


@trace_agent(name="autogen-research-chat", framework="autogen")
def run_autogen_chat(topic: str) -> str:
    """Run an AutoGen RoundRobinGroupChat: Researcher + Writer."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        print("  [mock] Researcher: researching topic")
        print("  [mock] Tool: lookup_fact called")
        fact = lookup_fact(topic)
        print(f"  [mock] Researcher: {fact}")
        print("  [mock] Writer: drafting summary")
        summary = f"Summary of '{topic}': {fact} This makes it production-ready."
        print(f"  [mock] Writer: {summary}")
        return summary

    try:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_agentchat.conditions import TextMentionTermination
        from autogen_agentchat.teams import RoundRobinGroupChat
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError:
        print("[SKIP] autogen not installed. Run: pip install specops-ai[autogen]")
        sys.exit(0)

    # Anthropic via OpenAI-compatible client (base_url + model prefix)
    model_client = OpenAIChatCompletionClient(
        model=get_model("anthropic"),
        api_key=api_key,
        base_url="https://api.anthropic.com/v1/",
        model_info={
            "vision": True,
            "function_calling": True,
            "json_output": True,
            "family": "claude",
        },
    )

    researcher = AssistantAgent(
        name="Researcher",
        model_client=model_client,
        system_message="You research topics and provide key facts. Be concise.",
    )
    writer = AssistantAgent(
        name="Writer",
        model_client=model_client,
        system_message=(
            "You write a 2-sentence summary from the researcher's findings. "
            "End your message with DONE when finished."
        ),
    )

    termination = TextMentionTermination("DONE")
    team = RoundRobinGroupChat(
        participants=[researcher, writer],
        termination_condition=termination,
        max_turns=4,
    )

    result = asyncio.run(team.run(task=f"Research and summarize: {topic}"))
    return str(result.messages[-1].content)


if __name__ == "__main__":
    print("=" * 60)
    print("SpecOps AI — AutoGen Multi-Agent Example (Anthropic)")
    print("=" * 60)

    topic = "SpecOps AI agent reliability toolkit"
    print(f"\nTopic: {topic}")
    print("-" * 60)

    output = run_autogen_chat(topic)

    print(f"\nFinal output:\n{output}")
    print("-" * 60)
    print("✓ Tracing active (trace_agent + trace_tool spans emitted)")
    print("=" * 60)

"""Example: CrewAI multi-agent crew with SpecOps tracing (Grok/xAI).

Demonstrates a Researcher → Writer → Critic crew with real CrewAI agents.

Setup:
    pip install specops-ai[crewai]
    cp .env.example .env  # fill in GROK_API_KEY

Run:
    uv run examples/providers/grok/crewai_agent.py

Mock mode (no API key or crewai needed):
    SPECOPS_EXAMPLE_MODE=mock uv run examples/providers/grok/crewai_agent.py
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

api_key = require_api_key("GROK_API_KEY", "Grok/xAI")


@trace_tool(name="summarize_topic")
def summarize_topic(topic: str) -> str:
    """Research tool that summarizes a topic."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        return f"Summary: {topic} is a framework-agnostic AI reliability toolkit."
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    resp = client.chat.completions.create(
        model=get_model("grok"),
        messages=[{"role": "user", "content": f"Summarize in 2 sentences: {topic}"}],
        temperature=0,
    )
    return resp.choices[0].message.content or ""


@trace_agent(name="crewai-content-crew", framework="crewai")
def run_crew(topic: str) -> str:
    """Run a CrewAI crew: Researcher → Writer → Critic."""
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        print("  [mock] Agent: Researcher — researching topic")
        print("  [mock] Tool: summarize_topic called")
        print("  [mock] Agent: Writer — drafting article")
        print("  [mock] Agent: Critic — reviewing draft")
        return (
            f"Final article on '{topic}':\n"
            "SpecOps AI provides observability, evaluation, and self-healing "
            "for LLM agents in production. (mock mode)"
        )

    try:
        from crewai import Agent, Crew, LLM, Process, Task
    except ImportError:
        print("[SKIP] crewai not installed. Run: pip install specops-ai[crewai]")
        return "crewai not installed"

    llm = LLM(
        model=get_model("grok"),
        provider="openai",
        api_key=api_key,
        base_url="https://api.x.ai/v1",
    )

    researcher = Agent(
        role="Researcher",
        goal=f"Research {topic} thoroughly",
        backstory="You are an expert technical researcher.",
        llm=llm,
        verbose=True,
    )
    writer = Agent(
        role="Writer",
        goal="Write a concise, engaging summary",
        backstory="You are a technical writer who makes complex topics accessible.",
        llm=llm,
        verbose=True,
    )
    critic = Agent(
        role="Critic",
        goal="Review and improve the draft for clarity and accuracy",
        backstory="You are a meticulous editor focused on quality.",
        llm=llm,
        verbose=True,
    )

    research_task = Task(
        description=f"Research the topic: {topic}. Provide key findings.",
        expected_output="A bullet-point summary of key findings.",
        agent=researcher,
    )
    write_task = Task(
        description="Write a short article based on the research findings.",
        expected_output="A 3-4 sentence article.",
        agent=writer,
    )
    review_task = Task(
        description="Review the article for clarity. Output the final version.",
        expected_output="The polished final article.",
        agent=critic,
    )

    crew = Crew(
        agents=[researcher, writer, critic],
        tasks=[research_task, write_task, review_task],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    return str(result)


if __name__ == "__main__":
    print("=" * 60)
    print("SpecOps AI — CrewAI Multi-Agent Example (Grok/xAI)")
    print("=" * 60)

    topic = "SpecOps AI agent reliability toolkit"
    print(f"\nTopic: {topic}")
    print("-" * 60)

    output = run_crew(topic)

    print(f"\nFinal output:\n{output}")
    print("-" * 60)
    print("✓ Tracing active (trace_agent + trace_tool spans emitted)")
    print("=" * 60)

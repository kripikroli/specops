"""Example: CrewAI agent with SpecOps tracing.

Demonstrates tracing a CrewAI Crew execution. This example uses
mock objects to show the pattern without requiring crewai installed.

Install with CrewAI support:
    pip install specops-ai[crewai]

Run:
    uv run python examples/crewai_agent.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from specops_ai import trace_agent, trace_llm, trace_tool

# --- Mock CrewAI types (replace with real imports in production) ---


@dataclass
class Task:
    """Mock CrewAI Task."""

    description: str
    expected_output: str = ""


@dataclass
class CrewOutput:
    """Mock CrewAI output with token usage."""

    raw: str
    token_usage: dict[str, Any] | None = None


# --- Agent implementation ---


@trace_tool(name="web_scraper")
def scrape_website(url: str) -> str:
    """Simulate scraping a website."""
    return f"Content from {url}: Latest AI news and developments..."


@trace_llm(model="gpt-4o", provider="openai")
def researcher_llm(prompt: str) -> dict:
    """Simulate the researcher agent's LLM call."""
    return {
        "text": "Based on my research, AI agents are becoming more reliable...",
        "model": "gpt-4o",
        "input_tokens": len(prompt.split()),
        "output_tokens": 45,
    }


@trace_llm(model="gpt-4o", provider="openai")
def writer_llm(prompt: str) -> dict:
    """Simulate the writer agent's LLM call."""
    return {
        "text": "# AI Agent Reliability\n\nAgents need observability...",
        "model": "gpt-4o",
        "input_tokens": len(prompt.split()),
        "output_tokens": 120,
    }


@trace_agent(name="crewai-content-crew", framework="crewai")
def run_crew(inputs: dict[str, str]) -> CrewOutput:
    """Simulate a CrewAI Crew with researcher + writer agents.

    In production, this would be:
        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, write_task],
            process=Process.sequential,
        )
        result = crew.kickoff(inputs=inputs)
    """
    topic = inputs.get("topic", "AI")

    # Researcher agent
    raw_data = scrape_website(f"https://news.example.com/search?q={topic}")
    research = researcher_llm(f"Research this topic: {topic}\nData: {raw_data}")

    # Writer agent
    prompt = f"Write an article about: {topic}\nResearch: {research['text']}"
    article = writer_llm(prompt)

    return CrewOutput(
        raw=article["text"],
        token_usage={
            "prompt_tokens": research["input_tokens"] + article["input_tokens"],
            "completion_tokens": research["output_tokens"] + article["output_tokens"],
            "model": "gpt-4o",
        },
    )


if __name__ == "__main__":
    result = run_crew(inputs={"topic": "AI Agent Reliability"})
    print(f"\nCrew output:\n{result.raw}")

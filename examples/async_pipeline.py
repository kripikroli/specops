"""Example: Async multi-agent pipeline with SpecOps tracing.

Demonstrates tracing multiple cooperating agents with nested spans,
async execution, and tool calls.

Run:
    uv run python examples/async_pipeline.py
"""

from __future__ import annotations

import asyncio

from specops import trace_agent, trace_llm, trace_tool


@trace_tool(name="fetch_data")
async def fetch_data(source: str) -> dict:
    """Simulate fetching data from an API."""
    await asyncio.sleep(0.01)  # Simulate network latency
    return {"source": source, "records": 42, "status": "ok"}


@trace_tool(name="validate")
async def validate(data: dict) -> dict:
    """Validate and clean data."""
    await asyncio.sleep(0.01)
    return {**data, "validated": True, "clean_records": data.get("records", 0) - 2}


@trace_llm(model="gpt-4o-mini", provider="openai")
async def analyze(prompt: str) -> dict:
    """Simulate LLM analysis."""
    await asyncio.sleep(0.01)
    return {
        "text": "Analysis complete. Found 3 key insights.",
        "model": "gpt-4o-mini",
        "input_tokens": len(prompt.split()),
        "output_tokens": 30,
    }


@trace_agent(name="data-collector")
async def collector_agent(task: str) -> dict:
    """Agent that collects and validates data."""
    raw = await fetch_data(task)
    clean = await validate(raw)
    return clean


@trace_agent(name="analyst")
async def analyst_agent(task: str) -> str:
    """Agent that analyzes collected data."""
    data = await collector_agent(task)
    prompt = f"Analyze {data['clean_records']} records from {data['source']}"
    result = await analyze(prompt)
    return result["text"]


@trace_agent(name="pipeline-orchestrator")
async def orchestrator(task: str) -> list[str]:
    """Top-level agent that coordinates the pipeline across multiple sources."""
    sources = ["database", "api", "cache"]
    results = await asyncio.gather(*[analyst_agent(src) for src in sources])
    return list(results)


if __name__ == "__main__":
    results = asyncio.run(orchestrator("Analyze all data sources"))
    print(f"\nPipeline results ({len(results)} sources):")
    for r in results:
        print(f"  - {r}")

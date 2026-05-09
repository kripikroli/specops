"""Example: Plain Python agent with SpecOps tracing.

Demonstrates @trace_agent, @trace_tool, and @trace_llm decorators
with a simple research agent that searches and summarizes.

Run:
    uv run python examples/plain_agent.py
"""

from specops_ai import trace_agent, trace_llm, trace_tool


@trace_tool(name="web_search")
def web_search(query: str) -> list[str]:
    """Simulate a web search tool."""
    return [
        f"Result 1 for '{query}': Python is a programming language.",
        f"Result 2 for '{query}': Python was created by Guido van Rossum.",
    ]


@trace_llm(model="gpt-4o", provider="openai")
def call_llm(prompt: str) -> dict:
    """Simulate an LLM call."""
    return {
        "text": "Summary: Based on the search results, here's what I found.",
        "model": "gpt-4o",
        "input_tokens": len(prompt.split()),
        "output_tokens": 25,
    }


@trace_agent(name="research-agent")
def research_agent(task: str) -> str:
    """A simple research agent that searches and summarizes."""
    results = web_search(task)
    context = "\n".join(results)
    response = call_llm(f"Summarize these results about '{task}':\n{context}")
    return response["text"]


if __name__ == "__main__":
    answer = research_agent("What is Python?")
    print(f"\nAgent response: {answer}")

"""Example: LangGraph agent with SpecOps tracing and real OpenAI calls.

Demonstrates tracing a LangGraph ReAct agent with a real LLM.

Setup:
    cp .env.example .env  # then fill in your OPENAI_API_KEY
    uv sync

Run:
    uv run examples/providers/openai/langgraph_agent.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Add examples/ dir to path so shared utils can be imported
_examples_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_examples_dir))

from shared.utils import require_api_key  # noqa: E402

api_key = require_api_key("OPENAI_API_KEY", "OpenAI")

import os  # noqa: E402

from langchain_core.messages import HumanMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from langgraph.prebuilt import create_react_agent  # noqa: E402

from specops_ai import trace_agent, trace_tool  # noqa: E402

# Ensure the key is available for langchain
os.environ.setdefault("OPENAI_API_KEY", api_key)


@tool
@trace_tool(name="calculator")
def calculator(expression: str) -> str:
    """Evaluate a math expression. Supports basic arithmetic and math functions."""
    allowed = {
        k: v for k, v in math.__dict__.items() if not k.startswith("_") and callable(v)
    }
    allowed.update({"abs": abs, "round": round})
    try:
        result = eval(expression, {"__builtins__": {}}, allowed)  # noqa: S307
    except Exception as e:
        return f"Error: {e}"
    return str(result)


@trace_agent(name="langgraph-math-agent", framework="langgraph")
def run_agent(task: str) -> str:
    """Run a LangGraph ReAct agent with the calculator tool."""
    # In mock mode, return a canned response
    if os.environ.get("SPECOPS_EXAMPLE_MODE") == "mock":
        print("  [mock] tool:calculator called")
        return "The answer is 21 (mock mode)"

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    agent = create_react_agent(llm, [calculator])
    result = agent.invoke({"messages": [HumanMessage(content=task)]})
    final = result["messages"][-1].content
    return final


if __name__ == "__main__":
    print("=" * 60)
    print("SpecOps AI — LangGraph Agent Example (OpenAI)")
    print("=" * 60)

    query = "What is the square root of 144 plus 3 squared?"
    print(f"\nTask: {query}")
    print("-" * 60)

    response = run_agent(query)

    print(f"\nAgent response: {response}")
    print("-" * 60)
    print("✓ Tracing active (trace_agent + trace_tool spans emitted)")
    print("=" * 60)

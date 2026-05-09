"""Example: LangGraph agent with SpecOps tracing.

Demonstrates tracing a LangGraph StateGraph agent. This example uses
mock objects to show the pattern without requiring langchain installed.

Install with LangGraph support:
    pip install specops-ai[langgraph]

Run:
    uv run python examples/langgraph_agent.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from specops_ai import trace_agent, trace_llm, trace_tool

# --- Mock LangGraph types (replace with real imports in production) ---


@dataclass
class AIMessage:
    """Mock AIMessage with usage_metadata."""

    content: str
    usage_metadata: dict[str, int] = field(default_factory=dict)
    response_metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentState:
    """Simulated LangGraph state."""

    messages: list[Any] = field(default_factory=list)
    input: str = ""


# --- Agent implementation ---


@trace_tool(name="calculator")
def calculator(expression: str) -> str:
    """A calculator tool."""
    try:
        result = eval(expression)  # noqa: S307
    except Exception:
        result = "Error"
    return str(result)


@trace_llm(model="gpt-4o", provider="openai")
def call_model(messages: list[Any]) -> AIMessage:
    """Simulate LLM call returning an AIMessage."""
    last_content = messages[-1] if messages else ""
    # Simulate the model deciding to use a tool or respond
    if "calculate" in str(last_content).lower():
        return AIMessage(
            content="The answer is 42.",
            usage_metadata={"input_tokens": 15, "output_tokens": 8},
            response_metadata={"model_name": "gpt-4o"},
        )
    return AIMessage(
        content=f"I can help with that. Let me think about: {last_content}",
        usage_metadata={"input_tokens": 10, "output_tokens": 20},
        response_metadata={"model_name": "gpt-4o"},
    )


@trace_agent(name="langgraph-math-agent", framework="langgraph")
def run_graph(state: dict[str, Any]) -> str:
    """Simulate a LangGraph StateGraph execution.

    In production, this would be:
        graph = StateGraph(AgentState)
        graph.add_node("agent", call_model)
        graph.add_node("tools", tool_node)
        app = graph.compile()
        result = app.invoke(state)
    """
    messages = state.get("messages", [])
    user_input = state.get("input", "")

    # Step 1: Call the model
    response = call_model(messages + [user_input])

    # Step 2: If tool use detected, call tool
    if "calculate" in user_input.lower():
        tool_result = calculator("6 * 7")
        return f"Tool result: {tool_result}, Model says: {response.content}"

    return response.content


if __name__ == "__main__":
    result = run_graph({"input": "Please calculate 6 * 7", "messages": []})
    print(f"\nAgent response: {result}")

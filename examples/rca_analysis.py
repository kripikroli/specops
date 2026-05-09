"""Example: Root Cause Analysis with RCA graph.

Demonstrates building an RCA graph from OTel spans after an agent
failure, identifying root causes and infection paths, and exporting
to Graphviz DOT format.
"""

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import specops_ai
from specops_ai import build_rca_graph, to_dot, trace_agent, trace_llm, trace_tool


def setup_tracing() -> InMemorySpanExporter:
    """Set up in-memory tracing for RCA analysis."""
    from opentelemetry import trace

    specops_ai.reset()
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    specops_ai.configure()
    return exporter


@trace_tool(name="database_query")
def query_db(sql: str) -> str:
    """Simulate a database query that fails."""
    raise ConnectionError("Database connection pool exhausted")


@trace_llm(model="gpt-4o", provider="openai")
def call_llm(prompt: str) -> dict[str, str | int]:
    """LLM call that depends on DB results."""
    return {
        "text": "response",
        "model": "gpt-4o",
        "input_tokens": 5,
        "output_tokens": 10,
    }


@trace_agent(name="data-agent")
def run_agent(task: str) -> str:
    """Agent that queries DB then calls LLM."""
    try:
        data = query_db("SELECT * FROM users")
    except ConnectionError:
        data = "no data"
    return str(call_llm(f"Analyze: {data}"))


if __name__ == "__main__":
    exporter = setup_tracing()

    # Run agent (will have a failed DB span)
    import contextlib

    with contextlib.suppress(Exception):
        run_agent("Analyze user behavior")

    # Build RCA graph from collected spans
    spans = exporter.get_finished_spans()
    graph = build_rca_graph(list(spans))

    print("=== RCA Graph Analysis ===")
    print(f"Total nodes: {len(graph.nodes)}")
    print(f"Total edges: {len(graph.edges)}")
    print(f"Error nodes: {len(graph.error_nodes)}")
    print(f"Root causes: {len(graph.root_causes)}")

    for rc in graph.root_causes:
        print(f"  → {rc.name}: {rc.error_message}")

    # Export to DOT
    dot = to_dot(graph, title="Agent Failure RCA")
    print(f"\n=== DOT Output ({len(dot)} chars) ===")
    print(dot[:500])

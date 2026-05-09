"""Root Cause Analysis (RCA) graph generator for SpecOps.

Builds a directed graph of span relationships and failure cascades from
OTel trace data. Identifies infection paths and root causes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import StatusCode

# --- Core Types ---


@dataclass
class RCANode:
    """A node in the RCA graph representing a span."""

    span_id: str
    name: str
    status: str  # "ok", "error", "unset"
    error_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    start_time: int = 0
    end_time: int = 0

    @property
    def is_error(self) -> bool:
        """Check if this node represents a failed span."""
        return self.status == "error"


@dataclass
class RCAEdge:
    """A directed edge in the RCA graph (parent → child)."""

    source: str  # parent span_id
    target: str  # child span_id
    relationship: str = "parent_of"  # parent_of, caused_by, infected_by


@dataclass
class RCAGraph:
    """Directed graph of span relationships and failure cascades.

    Nodes are spans, edges represent parent-child or causal relationships.
    """

    nodes: dict[str, RCANode] = field(default_factory=dict)
    edges: list[RCAEdge] = field(default_factory=list)

    def add_node(self, node: RCANode) -> None:
        """Add a node to the graph."""
        self.nodes[node.span_id] = node

    def add_edge(self, edge: RCAEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    @property
    def root_causes(self) -> list[RCANode]:
        """Find root cause nodes (error nodes with no error parents)."""
        error_nodes = {sid for sid, n in self.nodes.items() if n.is_error}
        # A root cause is an error node whose parent is NOT an error
        # (or has no parent)
        children_with_error_parents: set[str] = set()
        for edge in self.edges:
            if edge.source in error_nodes and edge.target in error_nodes:
                children_with_error_parents.add(edge.target)

        return [
            self.nodes[sid]
            for sid in error_nodes
            if sid not in children_with_error_parents
        ]

    @property
    def infection_paths(self) -> list[list[str]]:
        """Find paths from root causes through infected nodes."""
        paths: list[list[str]] = []
        for root in self.root_causes:
            path = self._trace_infection(root.span_id)
            if len(path) > 1:
                paths.append(path)
        return paths

    def _trace_infection(self, start: str) -> list[str]:
        """Trace infection path from a root cause node."""
        path = [start]
        visited: set[str] = {start}
        current = start
        while True:
            children = [
                e.target
                for e in self.edges
                if e.source == current and e.target not in visited
            ]
            error_children = [
                c for c in children if self.nodes.get(c, RCANode("", "", "ok")).is_error
            ]
            if not error_children:
                break
            # Follow the first error child (BFS would give all paths)
            current = error_children[0]
            visited.add(current)
            path.append(current)
        return path

    @property
    def error_nodes(self) -> list[RCANode]:
        """Get all error nodes."""
        return [n for n in self.nodes.values() if n.is_error]


# --- Graph Builder ---


def build_rca_graph(spans: list[ReadableSpan]) -> RCAGraph:
    """Build an RCA graph from a list of OTel spans.

    Args:
        spans: List of ReadableSpan objects (e.g. from InMemorySpanExporter).

    Returns:
        RCAGraph with nodes and edges representing the trace tree.
    """
    graph = RCAGraph()

    for span in spans:
        ctx = span.get_span_context()  # type: ignore[no-untyped-call]
        if ctx is None:
            continue

        span_id = format(ctx.span_id, "016x")
        status = "ok"
        error_msg = ""
        if span.status and span.status.status_code == StatusCode.ERROR:
            status = "error"
            error_msg = span.status.description or ""
        elif span.status and span.status.status_code == StatusCode.UNSET:
            status = "unset"

        attrs: dict[str, Any] = {}
        if span.attributes:
            attrs = dict(span.attributes)

        node = RCANode(
            span_id=span_id,
            name=span.name or "",
            status=status,
            error_message=error_msg,
            attributes=attrs,
            start_time=span.start_time or 0,
            end_time=span.end_time or 0,
        )
        graph.add_node(node)

    # Build edges from parent-child relationships
    for span in spans:
        ctx = span.get_span_context()  # type: ignore[no-untyped-call]
        if ctx is None:
            continue
        span_id = format(ctx.span_id, "016x")
        parent = span.parent
        if parent is not None:
            parent_id = format(parent.span_id, "016x")
            if parent_id in graph.nodes:
                graph.add_edge(RCAEdge(source=parent_id, target=span_id))

    # Add causal edges for error propagation
    _add_causal_edges(graph)

    return graph


def _add_causal_edges(graph: RCAGraph) -> None:
    """Add 'caused_by' edges where child errors precede parent errors."""
    parent_children: dict[str, list[str]] = {}
    for edge in graph.edges:
        parent_children.setdefault(edge.source, []).append(edge.target)

    for parent_id, children in parent_children.items():
        parent_node = graph.nodes.get(parent_id)
        if parent_node is None or not parent_node.is_error:
            continue
        for child_id in children:
            child_node = graph.nodes.get(child_id)
            if (
                child_node
                and child_node.is_error
                and child_node.end_time <= parent_node.end_time
            ):
                graph.add_edge(
                    RCAEdge(
                        source=child_id,
                        target=parent_id,
                        relationship="caused_by",
                    )
                )

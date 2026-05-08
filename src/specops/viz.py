"""Visualization helpers for RCA graphs.

Exports RCA graphs to Graphviz DOT format for rendering.
No external dependencies required — produces DOT strings directly.
"""

from __future__ import annotations

from specops.rca import RCAGraph


def to_dot(graph: RCAGraph, *, title: str = "RCA Graph") -> str:
    """Export an RCA graph to Graphviz DOT format.

    Args:
        graph: The RCA graph to visualize.
        title: Title for the graph.

    Returns:
        DOT format string that can be rendered with `dot -Tpng`.
    """
    lines: list[str] = []
    lines.append(f'digraph "{title}" {{')
    lines.append("  rankdir=TB;")
    lines.append('  node [shape=box, style=filled, fontname="Helvetica"];')
    lines.append("")

    # Nodes
    for node in graph.nodes.values():
        color = "#ff6b6b" if node.is_error else "#69db7c"
        label = node.name
        if node.error_message:
            # Escape quotes and truncate
            msg = node.error_message[:60].replace('"', '\\"')
            label = f"{node.name}\\n{msg}"
        lines.append(f'  "{node.span_id}" [label="{label}", fillcolor="{color}"];')

    lines.append("")

    # Edges
    for edge in graph.edges:
        style = "solid"
        color = "black"
        if edge.relationship == "caused_by":
            style = "dashed"
            color = "red"
        lines.append(
            f'  "{edge.source}" -> "{edge.target}" '
            f'[style={style}, color="{color}", label="{edge.relationship}"];'
        )

    lines.append("}")
    return "\n".join(lines)


def save_dot(graph: RCAGraph, path: str, *, title: str = "RCA Graph") -> str:
    """Save an RCA graph as a DOT file.

    Args:
        graph: The RCA graph to visualize.
        path: File path to write the DOT file.
        title: Title for the graph.

    Returns:
        The path written to.
    """
    dot = to_dot(graph, title=title)
    with open(path, "w") as f:
        f.write(dot)
    return path

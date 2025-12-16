from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..graph.model import Node


def visualize(target: LazyResult[Any]) -> str:
    """
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
        '  rankdir="TB";',
        '  node [shape=box, style="rounded,filled", fillcolor=white];',
    ]

    # 1. Define Nodes
    for node in graph.nodes:
        shape = _get_node_shape(node)
        label = f"{node.name}\\n({node.node_type})"
        dot_parts.append(f'  "{node.id}" [label="{label}", shape={shape}];')

    # 2. Define Edges
    for edge in graph.edges:
        style = ""
        if edge.arg_name == "_condition":
            style = ' [style=dashed, color=gray, label="run_if"]'
        elif edge.arg_name == "_implicit_dependency":
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.router:
            style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')

    dot_parts.append("}")
    return "\n".join(dot_parts)


def _get_node_shape(node: Node) -> str:
    """Returns the Graphviz shape for a given node type."""
    if node.node_type == "param":
        return "ellipse"
    if node.node_type == "map":
        return "hexagon"
    # Future: Routers could be a diamond, but they are edges in our model
    return "box"
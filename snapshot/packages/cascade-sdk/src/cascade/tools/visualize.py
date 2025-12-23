from typing import Any
from cascade.graph.build import build_graph
from cascade.graph.model import Node, EdgeType


def visualize(target: Any) -> str:
    """
    Builds the computation graph for a target and returns its representation
    in the Graphviz DOT language format.
    """
    graph, _ = build_graph(target)

    dot_parts = [
        "digraph CascadeWorkflow {",
        '  rankdir="TB";',
        '  node [shape=box, style="rounded,filled", fillcolor=white];',
    ]

    # 1. Define Nodes
    for node in graph.nodes:
        shape = _get_node_shape(node)

        # Default Style
        style = '"rounded,filled"'
        fillcolor = "white"
        fontcolor = "black"
        label_suffix = ""

        # Shadow Style Override
        if node.is_shadow:
            style = '"dashed,filled"'
            fillcolor = "whitesmoke"  # Very light gray
            fontcolor = "gray50"
            label_suffix = "\\n(Potential)"

        label = f"{node.name}\\n({node.node_type}){label_suffix}"

        dot_parts.append(
            f'  "{node.id}" [label="{label}", shape={shape}, style={style}, '
            f"fillcolor={fillcolor}, fontcolor={fontcolor}];"
        )

    # 2. Define Edges
    for edge in graph.edges:
        style = ""

        if edge.edge_type == EdgeType.CONDITION:
            style = ' [style=dashed, color=gray, label="run_if"]'
        elif edge.edge_type == EdgeType.IMPLICIT:
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.edge_type == EdgeType.ROUTER_ROUTE:
            # Router route edge
            style = ' [style=dashed, color=orange, arrowhead=open, label="route"]'
        elif edge.router:
            # Router selector edge (which is EdgeType.DATA)
            style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
        elif edge.edge_type == EdgeType.CONSTRAINT:
            style = (
                f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
            )
        elif edge.edge_type == EdgeType.SEQUENCE:
            style = ' [style=dashed, color=darkgray, arrowhead=open, label="next"]'
        elif edge.edge_type == EdgeType.POTENTIAL:
            # Use a reddish color to indicate a predicted/potential path, dashed
            style = ' [style=dashed, color="#d9534f", fontcolor="#d9534f", arrowhead=open, label="potential"]'
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

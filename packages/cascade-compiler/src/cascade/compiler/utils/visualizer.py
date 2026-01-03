from typing import List
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsDataNode, PhysicsFuncNode, PhysicsNode


class GraphDumper:
    def to_dot(self, graph: BipartiteGraph) -> str:
        lines: List[str] = [
            "digraph G {",
            "  rankdir=LR;",
            '  node [fontname="Helvetica", fontsize=10];',
            '  edge [fontname="Helvetica", fontsize=8];',
        ]

        # 1. Render Nodes
        for node_id, node in graph.nodes.items():
            attrs = self._get_node_attributes(node)
            attr_str = ", ".join([f'{k}="{v}"' for k, v in attrs.items()])
            lines.append(f'  "{node_id}" [{attr_str}];')

        # 2. Render Edges (Channels)
        for channel in graph.channels:
            src = channel.source_node_id
            tgt = channel.target_node_id

            label = f"{channel.source_port} -> {channel.target_port}"

            # Check for Observability edges to style them differently (dashed)
            style = "solid"
            color = "black"
            if "obs" in channel.source_port or "obs" in channel.target_port:
                style = "dashed"
                color = "#9e9e9e"  # Grey

            lines.append(
                f'  "{src}" -> "{tgt}" [label="{label}", style="{style}", color="{color}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def _get_node_attributes(self, node: PhysicsNode) -> dict:
        attrs = {
            "label": f"{node.name}\\n({node.id})",
            "style": "filled",
        }

        if isinstance(node, PhysicsDataNode):
            attrs["shape"] = "ellipse"
            attrs["fillcolor"] = "#e1f5fe"  # Light Blue
            attrs["color"] = "#01579b"

            # Highlight nodes with initial potential energy
            if node.initial_tokens > 0:
                attrs["penwidth"] = "2"
                attrs["label"] += f"\\nTokens: {node.initial_tokens}"

            # Special coloring for Resources buffers/ledgers
            if "resource" in node.id or "ledger" in node.id:
                attrs["fillcolor"] = "#e0f7fa"  # Cyan tint
            elif "trace" in node.id:
                attrs["fillcolor"] = "#f5f5f5"  # Grey (less important)

        elif isinstance(node, PhysicsFuncNode):
            attrs["shape"] = "box"
            attrs["fillcolor"] = "#fff9c4"  # Light Yellow (Default Worker)
            attrs["color"] = "#fbc02d"

            # Color coding based on role heuristics
            if ".bleach" in node.id:
                attrs["fillcolor"] = "#ffccbc"  # Light Orange
                attrs["color"] = "#d84315"
            elif ".stain" in node.id:
                attrs["fillcolor"] = "#c8e6c9"  # Light Green
                attrs["color"] = "#2e7d32"
            elif "allocator" in node.id:
                attrs["fillcolor"] = "#b2ebf2"  # Cyan
                attrs["color"] = "#006064"
            elif "reclaimer" in node.id:
                attrs["fillcolor"] = "#b2dfdb"  # Teal
                attrs["color"] = "#004d40"
            elif "observer" in node.id:
                attrs["fillcolor"] = "#e1bee7"  # Purple
                attrs["color"] = "#4a148c"
            elif "probe" in node.id:
                attrs["fillcolor"] = "#ffecb3"  # Amber
                attrs["shape"] = "hexagon"

        return attrs

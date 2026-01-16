from typing import List
from cascade.spec.physical.topology import BipartiteGraph
from cascade.spec.physical.nodes import PhysicsDataNode, PhysicsFuncNode, PhysicsNode
from cascade.spec.physical.dyad import LauncherNode, LanderNode
from cascade.spec.physical.constants import NodePrefix


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
            attrs["fillcolor"] = "#ffffff"  # Default White
            attrs["color"] = "#333333"

            # Heuristics based on NodePrefix
            if node.id.startswith(f"{NodePrefix.CONST}."):
                attrs["fillcolor"] = "#e1f5fe"  # Light Blue (Data Source)
                attrs["color"] = "#01579b"
            elif node.id.startswith(f"{NodePrefix.PULSE}."):
                attrs["fillcolor"] = "#e8eaf6"  # Indigo Tint (Trigger)
                attrs["color"] = "#1a237e"
            elif NodePrefix.LEDGER in node.id or "resource" in node.id:
                attrs["fillcolor"] = "#e0f7fa"  # Cyan tint (Resource State)
                attrs["color"] = "#006064"
            elif node.id.endswith(f".{NodePrefix.RESULT}"):
                attrs["fillcolor"] = "#f3e5f5"  # Purple Tint (Landing Pad)
                attrs["color"] = "#4a148c"

            # Highlight nodes with initial potential energy
            if node.initial_tokens > 0:
                attrs["penwidth"] = "2"
                attrs["label"] += f"\\nTokens: {node.initial_tokens}"

        elif isinstance(node, PhysicsFuncNode):
            attrs["shape"] = "box"
            attrs["fillcolor"] = "#fff9c4"  # Default Worker (Yellow)
            attrs["color"] = "#fbc02d"

            # 1. Check Dyad Roles
            if isinstance(node, LauncherNode):
                attrs["fillcolor"] = "#c8e6c9"  # Light Green (The Starter)
                attrs["color"] = "#2e7d32"
            elif isinstance(node, LanderNode):
                attrs["fillcolor"] = "#ffccbc"  # Light Orange (The Finisher)
                attrs["color"] = "#d84315"

            # 2. Check System ICs based on prefixes
            elif node.id.startswith(f"{NodePrefix.EGRESS}."):
                attrs["fillcolor"] = "#f8bbd0"  # Pink (System Exit)
                attrs["color"] = "#880e4f"
            elif "allocator" in node.id:
                attrs["fillcolor"] = "#b2ebf2"  # Cyan (Broker)
                attrs["color"] = "#006064"
            elif "reclaimer" in node.id:
                attrs["fillcolor"] = "#b2dfdb"  # Teal (Broker)
                attrs["color"] = "#004d40"
            elif "observer" in node.id:
                attrs["fillcolor"] = "#e1bee7"  # Purple (Observability)
                attrs["color"] = "#4a148c"
            elif "gate" in node.id:
                attrs["fillcolor"] = "#fff3e0"  # Orange Tint (Control)
                attrs["color"] = "#e65100"

        return attrs

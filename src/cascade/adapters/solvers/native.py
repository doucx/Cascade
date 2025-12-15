from graphlib import TopologicalSorter
from typing import Dict
from cascade.graph.model import Graph, Node
from cascade.runtime.protocols import ExecutionPlan


class NativeSolver:
    """
    A solver that uses Python's standard library `graphlib` to produce
    a sequential execution plan.
    """

    def resolve(self, graph: Graph) -> ExecutionPlan:
        # Create a mapping from node ID to node object for quick lookup
        node_map: Dict[str, Node] = {node.id: node for node in graph.nodes}

        # Build the dependency structure for TopologicalSorter
        # Format: {node_id: {dep1_id, dep2_id, ...}}
        deps: Dict[str, set] = {node.id: set() for node in graph.nodes}
        for edge in graph.edges:
            deps[edge.target.id].add(edge.source.id)

        # Perform the sort
        ts = TopologicalSorter(deps)
        sorted_node_ids = list(ts.static_order())

        # Map sorted IDs back to Node objects
        plan = [node_map[node_id] for node_id in sorted_node_ids]
        return plan

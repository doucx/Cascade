from typing import List, Set, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode
from cascade.vm.memory import VolatileMemory

class Reactor:
    """
    The heart of the physics engine.
    Scans the topology for excited states and fires transitions.
    """

    def __init__(self, graph: BipartiteGraph, memory: VolatileMemory):
        self.graph = graph
        self.memory = memory
        # Pre-compute the input data nodes for each function node for fast lookups
        self._func_inputs: Dict[str, List[str]] = {}
        self._func_nodes: List[PhysicsFuncNode] = []

        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []

        for channel in self.graph.channels:
            target_node = self.graph.nodes.get(channel.target_node_id)
            source_node = self.graph.nodes.get(channel.source_node_id)
            
            # We are interested in D -> F connections
            if isinstance(target_node, PhysicsFuncNode) and isinstance(source_node, PhysicsDataNode):
                self._func_inputs[target_node.id].append(source_node.id)

    def step(self) -> int:
        """
        Performs a single scan cycle of the entire graph.

        Returns:
            int: The number of nodes that fired during this step.
        """
        ready_nodes: List[PhysicsFuncNode] = []
        for f_node in self._func_nodes:
            input_ids = self._func_inputs.get(f_node.id, [])
            
            # A node with no inputs is not considered ready unless explicitly defined so.
            # Our "Full-Input Firing" model means a node with inputs must have them all excited.
            if not input_ids:
                continue

            is_ready = all(self.memory.is_excited(d_node_id) for d_node_id in input_ids)

            if is_ready:
                ready_nodes.append(f_node)

        for node_to_fire in ready_nodes:
            self._fire(node_to_fire)

        return len(ready_nodes)

    def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. (Future) Submits the actual payload to an Executor.
        """
        input_ids = self._func_inputs.get(node.id, [])
        for d_node_id in input_ids:
            self.memory.take(d_node_id)
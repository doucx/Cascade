from typing import List, Callable, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor

class Reactor:
    """
    The heart of the physics engine.
    Scans the topology for excited states and fires transitions.
    """

    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        
        # Pre-compute the input/output data nodes for each function node
        self._func_inputs: Dict[str, List[str]] = {}
        self._func_outputs: Dict[str, List[str]] = {}
        self._func_nodes: List[PhysicsFuncNode] = []

        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []
                self._func_outputs[node.id] = []

        for channel in self.graph.channels:
            target_node = self.graph.nodes.get(channel.target_node_id)
            source_node = self.graph.nodes.get(channel.source_node_id)
            
            # D -> F connections define inputs
            if isinstance(target_node, PhysicsFuncNode) and isinstance(source_node, PhysicsDataNode):
                self._func_inputs[target_node.id].append(source_node.id)
            
            # F -> D connections define outputs
            elif isinstance(source_node, PhysicsFuncNode) and isinstance(target_node, PhysicsDataNode):
                self._func_outputs[source_node.id].append(target_node.id)

    async def step(self) -> int:
        """
        Performs a single scan cycle of the entire graph.
        
        Returns:
            int: The number of nodes that fired during this step.
        """
        raise NotImplementedError

    async def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. Submits the actual payload to an Executor.
        3. Puts the resulting token into the output slots.
        """
        raise NotImplementedError
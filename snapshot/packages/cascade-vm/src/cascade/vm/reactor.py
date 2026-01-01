import asyncio
from typing import List, Callable, Dict
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
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
            if isinstance(target_node, PhysicsFuncNode) and isinstance(
                source_node, PhysicsDataNode
            ):
                self._func_inputs[target_node.id].append(source_node.id)

            # F -> D connections define outputs
            elif isinstance(source_node, PhysicsFuncNode) and isinstance(
                target_node, PhysicsDataNode
            ):
                self._func_outputs[source_node.id].append(target_node.id)

    async def step(self) -> int:
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

        if not ready_nodes:
            return 0

        # Fire all ready nodes in parallel
        await asyncio.gather(*(self._fire(node) for node in ready_nodes))

        return len(ready_nodes)

    async def _fire(self, node: PhysicsFuncNode) -> None:
        """
        Internal method to execute a node transition.
        1. Atomically consumes tokens from all input slots.
        2. Submits the actual payload to an Executor.
        3. Puts the resulting token into the output slots.
        """
        # 1. Consume inputs
        input_ids = self._func_inputs.get(node.id, [])
        input_tokens = [self.memory.take(d_node_id) for d_node_id in input_ids]
        args = [t.payload for t in input_tokens]

        # 2. Execute
        func = self.function_map.get(node.id)
        if not func:
            # In a robust system, this might log an error or emit an error token.
            # For now, we raise to fail fast during testing.
            raise ValueError(f"No function mapped for node {node.id}")

        result_payload = await self.executor.submit(func, tuple(args))

        # 3. Produce outputs
        output_ids = self._func_outputs.get(node.id, [])
        # In a real Triad, StainNode would handle wrapping.
        # Here we create a simple token.
        output_token = Token(payload=result_payload)

        for out_id in output_ids:
            # We need the PhysicsDataNode object to call put.
            # Since we pre-validated topology in __init__, we can safely access nodes.
            out_node = self.graph.nodes[out_id]
            # Ensure it is a DataNode to satisfy type checker (though logic guarantees it)
            if isinstance(out_node, PhysicsDataNode):
                self.memory.put(out_node, output_token)

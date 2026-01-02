import asyncio
from typing import List, Callable, Dict, Tuple
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor


class Reactor:
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

        # Indexing for O(1) lookups during step/fire
        self._func_nodes: List[PhysicsFuncNode] = []
        # node_id -> List[(source_data_node_id, target_port_name)]
        self._func_inputs: Dict[str, List[Tuple[str, str]]] = {}
        # node_id -> List[Channel]
        self._outbound_channels: Dict[str, List[Channel]] = {}

        # 1. Identify Function Nodes
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsFuncNode):
                self._func_nodes.append(node)
                self._func_inputs[node.id] = []
                self._outbound_channels[node.id] = []

        # 2. Build Connectivity Index
        for channel in self.graph.channels:
            source = self.graph.nodes.get(channel.source_node_id)
            target = self.graph.nodes.get(channel.target_node_id)

            if not source or not target:
                continue

            # Case A: Data -> Func (Input wiring)
            if isinstance(source, PhysicsDataNode) and isinstance(
                target, PhysicsFuncNode
            ):
                # Record that Target(F) needs input from Source(D) on specific Port
                self._func_inputs[target.id].append((source.id, channel.target_port))

            # Case B: Func -> Data (Output wiring)
            elif isinstance(source, PhysicsFuncNode) and isinstance(
                target, PhysicsDataNode
            ):
                # Record the full channel to support filtering logic later
                self._outbound_channels[source.id].append(channel)

    def prime(self) -> None:
        """
        Injects initial potential energy (tokens) into the system
        based on PhysicsDataNode.initial_tokens.
        """
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    self.memory.put(node, Token(payload=node.initial_payload))

    async def step(self) -> int:
        nodes_to_fire: List[PhysicsFuncNode] = []
        inputs_for_fire: Dict[str, Dict[str, Token]] = {}

        # --- ATOMIC SCAN & CONSUME ---
        # This loop is single-threaded and sequential. The state of `memory`
        # changes within the loop, ensuring that a resource token consumed by an
        # early node is unavailable for a later node in the same step.
        for f_node in self._func_nodes:
            inputs_def = self._func_inputs.get(f_node.id, [])
            if not inputs_def:
                continue

            # Check if this node CAN fire based on the CURRENT memory state
            if all(self.memory.is_excited(src_id) for src_id, _ in inputs_def):
                # It can. Atomically consume its inputs NOW.
                # This action affects subsequent nodes in this same loop.
                consumed_inputs = {
                    port: self.memory.take(src_id) for src_id, port in inputs_def
                }
                nodes_to_fire.append(f_node)
                inputs_for_fire[f_node.id] = consumed_inputs

        if not nodes_to_fire:
            return 0

        # Now, fire all nodes that successfully reserved their inputs in parallel.
        await asyncio.gather(
            *(self._fire(node, inputs_for_fire[node.id]) for node in nodes_to_fire)
        )

        return len(nodes_to_fire)

    async def _fire(self, node: PhysicsFuncNode, input_data: Dict[str, Token]) -> None:
        # 1. Consumption is already done. `input_data` is given.

        # 2. Execution
        func = self.function_map.get(node.id)
        if not func:
            raise ValueError(f"No function mapped for node {node.id}")

        # We pass the node instance as the second argument to the instruction
        # to allow access to static port definitions (PortDef).
        result_tokens: Dict[str, Token] = await self.executor.submit(
            func, (input_data, node)
        )

        if not isinstance(result_tokens, dict):
            raise ValueError(
                f"Function for node {node.id} must return a Dict[str, Token], "
                f"got {type(result_tokens)}"
            )

        # 3. Emission & Spectrum Filtering
        outbound = self._outbound_channels.get(node.id, [])

        for channel in outbound:
            token = result_tokens.get(channel.source_port)
            if token is None:
                continue

            if channel.tag_filter and channel.tag_filter != token.tag:
                continue

            target_node = self.graph.nodes[channel.target_node_id]
            if isinstance(target_node, PhysicsDataNode):
                self.memory.put(target_node, token)

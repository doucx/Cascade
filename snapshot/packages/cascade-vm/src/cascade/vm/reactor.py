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
                    # Initial tokens are pure potential; no payload, no trace.
                    self.memory.put(node, Token(payload=None))

    async def step(self) -> int:
        ready_nodes: List[PhysicsFuncNode] = []

        for f_node in self._func_nodes:
            inputs = self._func_inputs.get(f_node.id, [])

            # Full-Input Firing Rule: All connected input slots must be excited.
            if not inputs:
                continue

            # Check if all source DataNodes have tokens
            is_ready = all(
                self.memory.is_excited(src_id) for src_id, _ in inputs
            )

            if is_ready:
                ready_nodes.append(f_node)

        if not ready_nodes:
            return 0

        # Fire all ready nodes in parallel
        await asyncio.gather(*(self._fire(node) for node in ready_nodes))

        return len(ready_nodes)

    async def _fire(self, node: PhysicsFuncNode) -> None:
        # 1. Atomic Consumption (Hydration)
        # We must pull tokens from memory and map them to the function's expected argument names (ports).
        input_data: Dict[str, Token] = {}
        inputs = self._func_inputs.get(node.id, [])
        
        for src_id, target_port in inputs:
            token = self.memory.take(src_id)
            input_data[target_port] = token

        # 2. Execution
        func = self.function_map.get(node.id)
        if not func:
            raise ValueError(f"No function mapped for node {node.id}")

        # The contract is now strict: FuncNodes must accept Dict[str, Token] and return Dict[str, Token]
        result_tokens: Dict[str, Token] = await self.executor.submit(func, (input_data,))

        if not isinstance(result_tokens, dict):
             raise ValueError(f"Function for node {node.id} must return a Dict[str, Token], got {type(result_tokens)}")

        # 3. Emission & Spectrum Filtering
        outbound = self._outbound_channels.get(node.id, [])
        
        for channel in outbound:
            # Locate the token produced for this specific source port
            token = result_tokens.get(channel.source_port)
            
            if token is None:
                # It is legal for a node NOT to emit on a declared port (e.g. conditional output)
                continue

            # --- THE PRISM: Spectrum Filtering ---
            if channel.tag_filter and channel.tag_filter != token.tag:
                # Physics Block: The token's color (tag) does not match the channel's filter.
                continue
            # -------------------------------------

            # Transport to target DataNode
            target_node = self.graph.nodes[channel.target_node_id]
            if isinstance(target_node, PhysicsDataNode):
                self.memory.put(target_node, token)
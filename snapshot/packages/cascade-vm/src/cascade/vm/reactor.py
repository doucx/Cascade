import asyncio
import inspect
import logging
from typing import List, Callable, Dict, Tuple, Awaitable, Optional
from cascade.spec.topology import BipartiteGraph, Channel
from cascade.spec.physics import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.executor import PhysicsExecutor
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        executor: PhysicsExecutor,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.executor = executor
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()

        # State
        self.active_task_count = 0
        # node_id -> port_name -> list of callbacks
        self.sinks: Dict[str, Dict[str, List[Callable[[Token], Awaitable[None]]]]] = {}

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

    def add_sink(
        self,
        node_id: str,
        port_name: str,
        callback: Callable[[Token], Awaitable[None]],
    ) -> None:
        if node_id not in self.sinks:
            self.sinks[node_id] = {}
        if port_name not in self.sinks[node_id]:
            self.sinks[node_id][port_name] = []
        self.sinks[node_id][port_name].append(callback)

    def prime(self) -> None:
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
                consumed_inputs = {
                    port: self.memory.take(src_id) for src_id, port in inputs_def
                }
                nodes_to_fire.append(f_node)
                inputs_for_fire[f_node.id] = consumed_inputs

        if not nodes_to_fire:
            return 0

        # Schedule execution
        for node in nodes_to_fire:
            self._schedule_task(node, inputs_for_fire[node.id])

        return len(nodes_to_fire)

    def _schedule_task(self, node: PhysicsFuncNode, input_data: Dict[str, Token]):
        self.active_task_count += 1
        asyncio.create_task(self._execute_task(node, input_data))

    async def _execute_task(
        self, node: PhysicsFuncNode, input_data: Dict[str, Token]
    ) -> None:
        try:
            # 1. Execution
            func = self.function_map.get(node.id)
            if not func:
                raise ValueError(f"No function mapped for node {node.id}")

            # The new standard signature for all physical functions is (inputs, node, resources)
            if inspect.iscoroutinefunction(func):
                result_tokens = await func(input_data, node, self.resource_registry)
            else:
                result_tokens = await self.executor.submit(
                    func, (input_data, node, self.resource_registry)
                )

            if not isinstance(result_tokens, dict):
                raise ValueError(
                    f"Function for node {node.id} must return a Dict[str, Token], "
                    f"got {type(result_tokens)}"
                )

            # 2. Emission & Sinks
            outbound = self._outbound_channels.get(node.id, [])
            node_sinks = self.sinks.get(node.id, {})

            # We iterate over all result tokens to handle both Sinks and Channels
            for port_name, token in result_tokens.items():
                if token is None:
                    continue

                # A. Handle Sinks (Direct callback)
                if port_name in node_sinks:
                    for cb in node_sinks[port_name]:
                        try:
                            await cb(token)
                        except Exception as e:
                            logger.exception(
                                f"Sink callback failed for {node.id}:{port_name}: {e}"
                            )

                # B. Handle Outbound Channels (Topological Flow)
                # Find channels connected to this source port
                matching_channels = [c for c in outbound if c.source_port == port_name]

                for channel in matching_channels:
                    target_node = self.graph.nodes[channel.target_node_id]
                    if isinstance(target_node, PhysicsDataNode):
                        self.memory.put(target_node, token)

        except Exception as e:
            logger.exception(f"Error executing task {node.id}: {e}")
            # TODO: Emit error token to a special error port or DLQ?
            # For now, we just log. In v3.0 specs, errors are propagated as tokens.
            # If the func raised, it means it crashed HARD.
        finally:
            self.active_task_count -= 1
            # If we hit 0, we might want to signal an event?
            # For now, relying on memory mutation events is enough for forward progress.

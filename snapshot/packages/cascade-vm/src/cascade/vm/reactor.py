import asyncio
import inspect
import logging
from typing import List, Callable, Dict, Tuple, Awaitable, Optional, Any
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.vm.memory import VolatileMemory
from cascade.vm.resource_registry import ResourceRegistry

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        function_map: Dict[str, Callable],
        resource_registry: Optional[ResourceRegistry] = None,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.function_map = function_map
        self.resource_registry = resource_registry or ResourceRegistry()
        self.ingress_queue = ingress_queue

        # State
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

    def prime(self, genesis_trace: Optional[Dict[str, Any]] = None) -> None:
        genesis_trace = genesis_trace or {}
        for node in self.graph.nodes.values():
            if isinstance(node, PhysicsDataNode) and node.initial_tokens > 0:
                for _ in range(node.initial_tokens):
                    # Initial tokens use the node's defined payload (for constants) or None.
                    # We inject the genesis trace (e.g. run_id) into these primordial tokens.
                    self.memory.put(
                        node,
                        Token(payload=node.initial_payload, trace=genesis_trace.copy()),
                    )

    def step(self) -> int:
        # 0. Ingress Cycle
        self._process_ingress()

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

        # --- DIRECT DRIVE EXECUTION ---
        for node in nodes_to_fire:
            inputs = inputs_for_fire[node.id]
            try:
                # 1. Synchronous Execution
                func = self.function_map.get(node.id)
                if not func:
                    raise ValueError(f"No function mapped for node {node.id}")
                
                results = func(inputs, node, self.resource_registry)
                
                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)
                
            except Exception as e:
                logger.exception(f"Kernel panic at node '{node.id}': {e}")
                # TODO: In v3.2, implement exception tokens for fault tolerance.
                # For now, we log and suppress to keep the reactor alive.

        return len(nodes_to_fire)

    def _handle_results_immediate(self, node: PhysicsFuncNode, results: Dict[str, Token]) -> None:
        if not isinstance(results, dict):
            logger.error(f"Function for node {node.id} returned {type(results)}, expected dict.")
            return

        outbound = self._outbound_channels.get(node.id, [])
        node_sinks = self.sinks.get(node.id, {})

        for port_name, token in results.items():
            if token is None:
                continue

            # A. Handle Sinks (Callbacks)
            # Note: Sinks in the physical layer MUST be non-blocking.
            # If they return a coroutine, we schedule it on the loop but do NOT await.
            if port_name in node_sinks:
                for cb in node_sinks[port_name]:
                    try:
                        res = cb(token)
                        if inspect.isawaitable(res):
                            # Fire and forget for async sinks
                            asyncio.create_task(res)
                    except Exception as e:
                        logger.exception(f"Sink callback failed for {node.id}:{port_name}: {e}")

            # B. Handle Outbound Channels (Topological Flow)
            matching_channels = [c for c in outbound if c.source_port == port_name]
            for channel in matching_channels:
                target_node = self.graph.nodes[channel.target_node_id]
                if isinstance(target_node, PhysicsDataNode):
                    self.memory.put(target_node, token)

    def _process_ingress(self):
        if not self.ingress_queue:
            return

        while not self.ingress_queue.empty():
            try:
                reply_to_nid, result_token = self.ingress_queue.get_nowait()
                node = self.graph.nodes.get(reply_to_nid)
                if isinstance(node, PhysicsDataNode):
                    self.memory.put(node, result_token)
                else:
                    logger.warning(
                        f"Invalid reply_to_nid '{reply_to_nid}': not a DataNode."
                    )
            except asyncio.QueueEmpty:
                break

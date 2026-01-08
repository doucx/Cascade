import asyncio
import logging
from typing import List, Dict, Tuple, Optional, Any
from cascade.spec.physical.topology import BipartiteGraph, Channel
from cascade.spec.physical.nodes import PhysicsFuncNode, PhysicsDataNode, Token
from cascade.spec.runtime.system import SystemControlToken, ControlCommand
from cascade.vm.memory import VolatileMemory
from cascade.vm.kernel import PhysicsKernel

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(
        self,
        graph: BipartiteGraph,
        memory: VolatileMemory,
        kernel: PhysicsKernel,
        ingress_queue: Optional[asyncio.Queue] = None,
    ):
        self.graph = graph
        self.memory = memory
        self.kernel = kernel
        self.ingress_queue = ingress_queue

        # Lifecycle Signals
        self.shutdown_event = asyncio.Event()
        self.drain_event = asyncio.Event()

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
                # 1. Synchronous Execution via Kernel
                results = self.kernel.execute(node, inputs)

                # 2. Immediate Result Handling
                self._handle_results_immediate(node, results)

            except Exception as e:
                # Kernel panic is already logged by the kernel, but we handle the signal here
                # Upgrade kernel panic to System Error Signal
                self._handle_control_signal(
                    SystemControlToken(command=ControlCommand.ERROR, payload=e)
                )

        return len(nodes_to_fire)

    def _handle_results_immediate(
        self, node: PhysicsFuncNode, results: Dict[str, Token]
    ) -> None:
        if not isinstance(results, dict):
            logger.error(
                f"Function for node {node.id} returned {type(results)}, expected dict."
            )
            return

        outbound = self._outbound_channels.get(node.id, [])

        for port_name, token in results.items():
            if token is None:
                continue

            # 0. Intercept System Control Tokens
            if isinstance(token.payload, SystemControlToken):
                self._handle_control_signal(token.payload)

            # A. Handle Outbound Channels (Topological Flow)
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

    def _handle_control_signal(self, ctrl: SystemControlToken) -> None:
        logger.info(f"Reactor received control signal: {ctrl.command}")
        if ctrl.command == ControlCommand.HALT:
            self.shutdown_event.set()
        elif ctrl.command == ControlCommand.DRAIN:
            logger.info("DRAIN signal received. System entering draining mode.")
            self.drain_event.set()
        elif ctrl.command == ControlCommand.ERROR:
            logger.error(f"System Critical Error: {ctrl.payload}")
            self.shutdown_event.set()

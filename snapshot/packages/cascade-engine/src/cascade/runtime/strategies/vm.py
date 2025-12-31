import asyncio
from contextlib import ExitStack
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass

from cascade.spec.protocols import StateBackend, Executor
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.bus import MessageBus

from cascade.compiler.frontend import Frontend
from cascade.compiler.backend import Backend
from cascade.spec.ir.models import TaskDef
from cascade.spec.physics import Token
from cascade.spec.topology import BipartiteGraph
from cascade.vm.reactor import Reactor, ExecutionFinished
from cascade.graph.model import TaskNode  # Used as shim for LocalExecutor


@dataclass
class _RuntimeMetadata:
    """Helper to store metadata needed for execution but not present in Physics nodes."""
    definition: TaskDef
    func: Callable


class _ReactorAdapter:
    """
    Bridges the gap between the abstract Physics Reactor and the concrete Python Executor.
    Responsible for:
    1. Linking PhysicsNode -> TaskDef -> Callable
    2. Unpacking Token payloads into args/kwargs
    3. Constructing shims for LocalExecutor
    4. Feeding results back into the Reactor as events
    """

    def __init__(
        self,
        executor: Executor,
        reactor: Reactor,
        metadata_map: Dict[str, _RuntimeMetadata],
    ):
        self.executor = executor
        self.reactor = reactor
        self.metadata_map = metadata_map

    async def submit(self, node: Any, inputs: Dict[str, Token]) -> None:
        """
        Callback called by Reactor when a node fires.
        """
        # 1. Retrieve Metadata
        meta = self.metadata_map.get(node.current_node_instance_hash)
        if not meta:
            raise RuntimeError(
                f"Linking failed: No metadata found for node {node.current_node_instance_hash} ({node.name})"
            )

        # 2. Unpack Inputs (Tokens -> Args/Kwargs)
        args: List[Any] = []
        kwargs: Dict[str, Any] = {}
        
        # Determine max positional index from inputs keys like "0", "1", ...
        max_idx = -1
        for k in inputs.keys():
            if k.isdigit():
                max_idx = max(max_idx, int(k))
        
        # Pre-fill args list
        if max_idx >= 0:
            args = [None] * (max_idx + 1)

        for k, token in inputs.items():
            if k.isdigit():
                args[int(k)] = token.payload
            else:
                kwargs[k] = token.payload

        # 3. Construct Shim Node for LocalExecutor
        # LocalExecutor expects a Node object with .definition and .callable_obj
        # We create a lightweight wrapper.
        shim_node = TaskNode(
            current_node_instance_hash=node.current_node_instance_hash,
            definition=meta.definition,
            _callable=meta.func,
            # Policies could be injected here if we parsed them from IR
        )

        # 4. Schedule Execution (Non-blocking from Reactor's perspective)
        # We fire-and-forget a task that will push the result back to Reactor event queue.
        asyncio.create_task(self._run_job(shim_node, args, kwargs, node))

    async def _run_job(self, shim_node, args, kwargs, physics_node):
        try:
            result = await self.executor.execute(shim_node, args, kwargs)
            
            # 5. Pack Result (Default output port "result")
            # In the future, we might support multi-port output based on result type
            outputs = {"result": Token(payload=result)}
            
            self.reactor.push_event(
                ExecutionFinished(node=physics_node, outputs=outputs)
            )
        except Exception as e:
            # Handle failure (Propagate error token or fail run)
            self.reactor.push_event(
                ExecutionFinished(node=physics_node, error=e)
            )


class VMExecutionStrategy:
    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
        executor: Executor,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus
        self.executor = executor

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Compile
        compilation_result = Frontend.compile(target)
        graph_ir = compilation_result.ir
        symbol_table = compilation_result.symbol_table

        # 2. Topology Generation
        topology: BipartiteGraph = Backend.compile(graph_ir)

        # 3. Build Runtime Metadata Map (Instance Hash -> Metadata)
        # We need to correlate NodeIR (from GraphIR) with PhysicsFuncNode to enable execution.
        metadata_map: Dict[str, _RuntimeMetadata] = {}
        target_output_slot_hash: Optional[str] = None
        
        # We also need to identify the DataNode that holds the final result.
        # Heuristic: The target (LazyResult) corresponds to the last visited NodeIR in Frontend?
        # Better: Frontend could return the ID of the root node.
        # Current Frontend impl: `Frontend.compile` returns `CompilationResult`. 
        # We can find the NodeIR corresponding to `target._uuid`.
        # Frontend ensures `_visited_lazy_uuids` maps uuid -> structure_id.
        # But `compilation_result` doesn't expose that map directly.
        # Workaround: Re-scan graph_ir to find the root? Or trust that the last node added is root?
        # GraphIR nodes are a list.
        # Let's assume for now we can scan for the node that has no outgoing data edges? No, that's brittle.
        # Let's use the `target` object itself. Frontend uses `hashing_service` to compute ID.
        # We can re-compute the ID of the target to find it in the graph.
        
        # Re-computing ID is safe because it is deterministic.
        from cascade.compiler.hashing import HashingService
        from cascade.compiler.analysis.reflection import ReflectionAnalyzer
        
        # We need to replicate what Frontend did to get the ID.
        # This suggests Frontend should return the root ID.
        # For now, let's assume the LAST node in `graph_ir.nodes` is the root (post-order traversal usually ensures this).
        root_node_ir = graph_ir.nodes[-1] if graph_ir.nodes else None
        
        for node_ir in graph_ir.nodes:
            code_hash = node_ir.definition.fingerprint["current_code_structure_hash"]
            func = symbol_table.get(code_hash)
            if not func:
                raise RuntimeError(f"Missing symbol for code hash {code_hash}")
                
            metadata_map[node_ir.current_node_instance_hash] = _RuntimeMetadata(
                definition=node_ir.definition,
                func=func
            )

        # 4. Setup Reactor
        # We create a dummy reactor first to pass to adapter, then inject adapter back
        # Circular dependency: Reactor needs Executor, Adapter needs Reactor
        # Solution: Reactor accepts executor, Adapter wraps executor logic.
        # We can make Adapter implement the 'submit' method expected by Reactor.
        
        # Reactor expects an object with .submit(node, inputs) method.
        # Adapter implements this.
        
        reactor = Reactor(executor=None, resource_manager=self.resource_manager)
        adapter = _ReactorAdapter(self.executor, reactor, metadata_map)
        reactor.executor = adapter # Patching the executor

        # 5. Load Topology
        for node in topology.func_nodes.values():
            reactor.register_node(node)
        for node in topology.data_nodes.values():
            reactor.register_node(node)
        for channel in topology.channels:
            reactor.register_channel(channel)

        # 6. Inject Initial Values
        from cascade.vm.reactor import TokenGenerated
        for data_hash, value in topology.initial_values.items():
            if data_hash in topology.data_nodes:
                d_node = topology.data_nodes[data_hash]
                reactor.push_event(TokenGenerated(node=d_node, token=Token(value)))

        # 7. Identify Result DataNode
        # Find the output channel of the root FuncNode
        # The Backend guarantees default output channel is named "result"
        if root_node_ir:
            root_func_hash = root_node_ir.current_node_instance_hash
            # Find channel: Source=Root, Port="result", Tag="default"
            result_channel = next((
                c for c in topology.channels 
                if c.source_node_instance_hash == root_func_hash 
                and c.port_name == "result" 
                and c.match("default")
            ), None)
            
            if result_channel:
                target_output_slot_hash = result_channel.target_data_slot_hash

        # 8. Run
        await reactor.run()

        # 9. Extract Result
        if target_output_slot_hash and target_output_slot_hash in topology.data_nodes:
            d_node = topology.data_nodes[target_output_slot_hash]
            if d_node.is_excited():
                return d_node.peek().payload
        
        # Handle void return or failure to find output
        return None
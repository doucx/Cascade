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
from cascade.spec.physics import Token, DataNode, FuncNode, Port
from cascade.spec.topology import BipartiteGraph
from cascade.vm.reactor import Reactor, ExecutionFinished
from cascade.vm.reactor.model import Channel
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

    async def submit(self, node: FuncNode, inputs: Dict[str, Token]) -> None:
        """
        Callback called by Reactor when a node fires.
        The 'node' here is the runtime FuncNode instance.
        We used the hash as the node's name during hydration.
        """
        # 1. Retrieve Metadata using node.name (which stores the instance hash)
        instance_hash = node.name
        meta = self.metadata_map.get(instance_hash)
        if not meta:
            raise RuntimeError(
                f"Linking failed: No metadata found for node {instance_hash}"
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
        shim_node = TaskNode(
            current_node_instance_hash=instance_hash,
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
            # Handle failure
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
        # And identify root node for result extraction
        metadata_map: Dict[str, _RuntimeMetadata] = {}
        
        # Heuristic: The last node added to IR is usually the root
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

        # 4. Initialize Reactor
        reactor = Reactor(executor=None, resource_manager=self.resource_manager)
        adapter = _ReactorAdapter(self.executor, reactor, metadata_map)
        reactor.executor = adapter

        # 5. Hydrate Topology: Static -> Dynamic
        # We need to map static hashes to dynamic instances to wire them up
        dynamic_data_nodes: Dict[str, DataNode] = {}
        dynamic_func_nodes: Dict[str, FuncNode] = {}

        # 5.1 Hydrate DataNodes
        for d_hash, p_node in topology.data_nodes.items():
            # Create dynamic DataNode
            # Name isn't strictly used for logic, but helpful for debugging
            d_instance = DataNode(name=p_node.name)
            dynamic_data_nodes[d_hash] = d_instance
            reactor.register_node(d_instance)

        # 5.2 Hydrate FuncNodes and wire Inputs
        for f_hash, p_node in topology.func_nodes.items():
            # Create dynamic FuncNode
            # CRITICAL: We use the instance hash as the name for metadata lookup
            f_instance = FuncNode(name=f_hash) 
            dynamic_func_nodes[f_hash] = f_instance
            reactor.register_node(f_instance)
            
            # Wire Inputs
            for arg_name, source_data_hash in p_node.inputs.items():
                if source_data_hash in dynamic_data_nodes:
                    source_d = dynamic_data_nodes[source_data_hash]
                    # Create Input Port: DataNode -> FuncNode
                    # Note: physics.FuncNode.add_input expects a Port with a 'source'
                    port = Port(name=arg_name, source=source_d)
                    f_instance.add_input(port)

        # 5.3 Wire Outputs (Channels)
        for ch_def in topology.channels:
            source_f = dynamic_func_nodes.get(ch_def.source_node_instance_hash)
            target_d = dynamic_data_nodes.get(ch_def.target_data_slot_hash)
            
            if source_f and target_d:
                # Create Reactor Channel
                channel = Channel(
                    source=source_f,
                    target=target_d,
                    output_name=ch_def.port_name,
                    tag_filter=ch_def.tag_filter
                )
                reactor.register_channel(channel)
                
                # Also need to add Output Port to FuncNode so it knows where to push?
                # physics.FuncNode.produce_outputs uses 'self.outputs' map.
                # But Reactor's '_handle_execution_finished' uses 'channels_by_source'.
                # So FuncNode only needs to define the existence of the port for validation/reflection?
                # Currently FuncNode.produce_outputs is used by Reactor logic if we were simulating locally?
                # Actually, `Reactor._handle_execution_finished` uses `self._channels_by_source`.
                # So adding output ports to `f_instance` is optional for Reactor logic, 
                # BUT good for consistency.
                
                # We can add a dummy port to f_instance to reflect structure
                if ch_def.port_name not in source_f.outputs:
                    source_f.add_output(Port(name=ch_def.port_name))

        # 6. Inject Initial Values
        from cascade.vm.reactor import TokenGenerated
        for data_hash, value in topology.initial_values.items():
            if data_hash in dynamic_data_nodes:
                d_node = dynamic_data_nodes[data_hash]
                reactor.push_event(TokenGenerated(node=d_node, token=Token(value)))

        # 7. Identify Result DataNode
        target_output_d_node = None
        if root_node_ir:
            root_func_hash = root_node_ir.current_node_instance_hash
            # Look for the channel outputting from root
            # Note: We can look at topology channels again
            result_channel_def = next((
                c for c in topology.channels
                if c.source_node_instance_hash == root_func_hash
                and c.port_name == "result"
                and c.tag_filter == "default"
            ), None)
            
            if result_channel_def:
                target_output_d_node = dynamic_data_nodes.get(result_channel_def.target_data_slot_hash)

        # 8. Run
        await reactor.run()

        # 9. Extract Result
        if target_output_d_node and target_output_d_node.is_excited():
            return target_output_d_node.peek().payload
        
        return None
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Callable

from cascade.spec.protocols import StateBackend, Executor
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.bus import MessageBus

# New Compiler Stack & Physics
from cascade.compiler import Frontend, Backend
from cascade.spec.topology import BipartiteGraph
from cascade.spec.physics import DataNode, FuncNode, TerminatorNode, EmitterNode, Port, Token
from cascade.vm.reactor import Reactor, Channel, TokenGenerated, ExecutionFinished

# Shim for LocalExecutor
from cascade.graph.model import Node as OldNode
from cascade.spec.ir.models import TaskDef
from cascade.spec.fingerprint import Fingerprint

class _ReactorExecutorAdapter:
    """Bridges the Reactor's simple executor protocol with the legacy LocalExecutor."""
    def __init__(self, local_executor: Executor, reactor: Reactor, symbol_table: Dict[str, Callable]):
        self.local_executor = local_executor
        self.reactor = reactor
        self.symbol_table = symbol_table

    async def submit(self, node: FuncNode, inputs: Dict[str, Token]):
        """The interface expected by the Reactor."""
        # This runs in a background task so it doesn't block the reactor loop.
        asyncio.create_task(self._execute_and_report(node, inputs))

    async def _execute_and_report(self, node: FuncNode, inputs: Dict[str, Token]):
        try:
            # 1. Link to find the callable
            func = self.symbol_table[node.code_structure_hash]

            # 2. Unpack payloads
            # Emitter/Terminator don't have inputs in this path
            kwargs = {name: token.payload for name, token in inputs.items()}
            
            # 3. Create a shim Node for LocalExecutor
            # TODO: Propagate is_async and mode properly
            is_async = asyncio.iscoroutinefunction(func)
            shim_def = TaskDef(name=node.name, args=[], fingerprint=Fingerprint(), is_async=is_async)
            shim_node = OldNode(
                current_node_instance_hash=node.name, # Approximation
                definition=shim_def,
                _callable=func
            )
            
            # 4. Execute
            result = await self.local_executor.execute(shim_node, [], kwargs)
            
            # 5. Report back with ExecutionFinished event
            # For now, assume single 'result' output
            output_token = Token(payload=result)
            event = ExecutionFinished(node=node, outputs={"result": output_token})

        except Exception as e:
            event = ExecutionFinished(node=node, error=e)
            
        self.reactor.push_event(event)


class VMExecutionStrategy:
    def __init__(
        self,
        executor: Executor,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
        bus: MessageBus,
    ):
        self.executor = executor
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event
        self.bus = bus

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Frontend: Compile LazyResult to GraphIR
        compilation_result = Frontend.compile(target)
        graph_ir = compilation_result.ir
        
        # Find target node hash to guide backend injection
        from cascade.spec.lazy_types import LazyResult
        target_node_hash = ""
        if isinstance(target, LazyResult):
            # We need to rebuild the hash to find the ID.
            # This is complex. A better way is for Frontend to return the target ID.
            # For now, let's assume the last node in IR is the target (heuristic).
            if graph_ir.nodes:
                target_node_hash = graph_ir.nodes[-1].current_node_instance_hash

        # 2. Backend: Generate autonomous BipartiteGraph
        topology = Backend.compile(graph_ir, target_node_hash)

        # 3. Setup Reactor and its Executor Adapter
        reactor = Reactor(executor=None, resource_manager=self.resource_manager)
        adapter = _ReactorExecutorAdapter(
            local_executor=self.executor,
            reactor=reactor,
            symbol_table=compilation_result.symbol_table
        )
        reactor.executor = adapter # Set the adapter as the executor
        
        # 4. Load Topology into Reactor
        self._load_topology(reactor, topology)
        
        # 5. Setup Sink
        result_future = asyncio.Future()
        reactor.register_sink("main_output", result_future.set_result)

        # 6. Ignite and Wait
        run_task = asyncio.create_task(reactor.run())
        
        # 7. Inject initial values
        for data_hash, value in topology.initial_values.items():
            data_node = next((n for n in reactor._nodes if isinstance(n, DataNode) and n.name == f"const_{data_hash[:8]}"), None)
            if data_node: # This lookup is weak, needs improvement
                 reactor.push_event(TokenGenerated(node=data_node, token=Token(value)))

        await run_task
        
        # 8. Return result from sink
        return await result_future

    def _load_topology(self, reactor: Reactor, topology: BipartiteGraph):
        """Translates static BipartiteGraph into dynamic Reactor objects."""
        
        # 1. Instantiate all nodes (static -> dynamic)
        # We need a map from static hash to dynamic object instance
        d_nodes: Dict[str, DataNode] = {}
        for dn_hash, dn_spec in topology.data_nodes.items():
            d_nodes[dn_hash] = DataNode(name=dn_spec.name)

        f_nodes: Dict[str, FuncNode] = {}
        for fn_hash, fn_spec in topology.func_nodes.items():
            f_nodes[fn_hash] = FuncNode(
                name=fn_spec.name,
                code_structure_hash=fn_spec.code_structure_hash
            ) # TODO: resource reqs
        for en_hash, en_spec in topology.emitter_nodes.items():
            f_nodes[en_hash] = EmitterNode(
                name=en_spec.name,
                sink_id=en_spec.sink_id,
                code_structure_hash="" # Emitters don't have user code
            )
        for tn_hash, tn_spec in topology.terminator_nodes.items():
            f_nodes[tn_hash] = TerminatorNode(
                name=tn_spec.name,
                code_structure_hash="" # Terminators don't have user code
            )

        # 2. Wire inputs (D -> F)
        all_f_nodes = {**topology.func_nodes, **topology.emitter_nodes, **topology.terminator_nodes}
        for fn_hash, fn_spec in all_f_nodes.items():
            dyn_f_node = f_nodes[fn_hash]
            for port_name, source_data_hash in fn_spec.inputs.items():
                dyn_f_node.add_input(Port(name=port_name, source=d_nodes[source_data_hash]))

        # 3. Register all dynamic nodes and channels (F -> D)
        for channel_spec in topology.channels:
            source_node = f_nodes.get(channel_spec.source_node_instance_hash)
            target_node = d_nodes.get(channel_spec.target_data_slot_hash)
            
            if source_node and target_node:
                # Backend must wire output ports correctly for this to work
                # For now, we assume a single 'result' output.
                source_node.add_output(Port(name=channel_spec.port_name, target=target_node))

                # Also register the explicit channel for routing
                channel = Channel(
                    source=source_node,
                    target=target_node,
                    output_name=channel_spec.port_name,
                    tag_filter=channel_spec.tag_filter
                )
                reactor.register_channel(channel)
            
        # Fallback registration for any nodes not covered by channels
        for node in list(d_nodes.values()) + list(f_nodes.values()):
            reactor.register_node(node)

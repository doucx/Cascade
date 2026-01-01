import asyncio
from contextlib import ExitStack
from typing import Any, Dict

# --- 核心 VM 和编译器组件 ---
from cascade.compiler import Frontend, Backend
from cascade.vm.reactor import Reactor
from cascade.vm.executors import PhysicsExecutor
from cascade.spec.topology import BipartiteGraph, ChannelKind
from cascade.spec.physics import FuncNode, DataNode, EmitterNode, Token, Port
from cascade.vm.reactor.model import Channel as ReactorChannel


# --- 运行时和规格 ---
from cascade.runtime.bus import MessageBus
from cascade.spec.protocols import StateBackend


class VMExecutionStrategy:
    """
    Orchestrates the new physics-based VM execution by acting as a
    macro-orchestrator for the compiler and the Reactor.
    """

    def __init__(
        self,
        bus: MessageBus,
        # Note: ResourceManager and ConstraintManager are now owned by the Reactor/VM,
        # so this strategy no longer needs to manage them directly.
    ):
        self.bus = bus
        self.frontend = Frontend()
        self.backend = Backend()

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        print("[VMStrategy] execute started.")
        # 1. 编译 (Compilation)
        compilation_result = self.frontend.compile(target)
        topology = self.backend.compile(compilation_result.ir)
        symbol_table = compilation_result.symbol_table
        print("[VMStrategy] Compilation finished.")

        # 2. 组装 (Assembly)
        reactor = Reactor(executor=None)  # Executor will be injected right after
        physics_executor = PhysicsExecutor(reactor=reactor, symbol_table=symbol_table)
        reactor.executor = physics_executor
        print("[VMStrategy] Reactor and Executor assembled.")

        # 3. 配置 (Configuration)
        loop = asyncio.get_running_loop()
        result_future = loop.create_future()
        termination_future = loop.create_future()

        def on_main_output(payload: Any):
            print(f"[VMStrategy] Sink 'main_output' called with: {payload}")
            if not result_future.done():
                result_future.set_result(payload)

        def on_termination_signal(payload: Any):
            print("[VMStrategy] Sink '__system_lifecycle_signal' called.")
            if not termination_future.done():
                termination_future.set_result(True)

        reactor.register_sink("main_output", on_main_output)
        reactor.register_sink("__system_lifecycle_signal", on_termination_signal)

        self._load_topology(reactor, topology)
        print("[VMStrategy] Topology loaded and reactor kickstarted.")

        # 4. 运行与等待 (Execution & Observation)
        print("[VMStrategy] Starting reactor.run() in background task...")
        run_task = asyncio.create_task(reactor.run())

        try:
            print("[VMStrategy] Awaiting futures...")
            await asyncio.wait(
                [result_future, termination_future],
                return_when=asyncio.ALL_COMPLETED,
            )
            print("[VMStrategy] Futures completed.")

            if result_future.exception():
                raise result_future.exception()
            if termination_future.exception():
                raise termination_future.exception()

            if not result_future.done():
                raise RuntimeError("Workflow terminated without producing a result.")

            return result_future.result()

        finally:
            # 5. 清理 (Teardown)
            print("[VMStrategy] Entering finally block for cleanup.")
            if not run_task.done():
                reactor.stop()
                # Yield control briefly to allow the reactor loop to process the stop signal
                await asyncio.sleep(0)
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    print("[VMStrategy] Reactor task successfully cancelled.")
                    pass  # Cancellation is the expected outcome here.

    def _load_topology(self, reactor: Reactor, topology: BipartiteGraph):
        """
        Translates the static BipartiteGraph spec into live, interconnected
        physics objects within the Reactor.
        """
        # Caches to map from spec hash to runtime object
        runtime_data_nodes: Dict[str, DataNode] = {}
        runtime_func_nodes: Dict[str, FuncNode] = {}

        # Pass 1: Instantiate all DataNodes and set initial constant values
        for spec_d_node in topology.data_nodes.values():
            d_node = DataNode(name=spec_d_node.current_data_slot_hash)
            runtime_data_nodes[spec_d_node.current_data_slot_hash] = d_node
            reactor.register_node(d_node)

            if spec_d_node.current_data_slot_hash in topology.initial_values:
                initial_val = topology.initial_values[
                    spec_d_node.current_data_slot_hash
                ]
                initial_token = Token(payload=initial_val)
                d_node.put(initial_token)

        # Pass 2: Instantiate all FuncNodes and wire their inputs
        for spec_f_node in topology.func_nodes.values():
            if spec_f_node.sink_id:
                f_node = EmitterNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                    sink_id=spec_f_node.sink_id,
                )
            else:
                f_node = FuncNode(
                    name=spec_f_node.current_node_instance_hash,
                    canonical_code_structure_hash=spec_f_node.canonical_code_structure_hash,
                    is_map=spec_f_node.is_map,
                )

            runtime_func_nodes[spec_f_node.current_node_instance_hash] = f_node

            for port_name, source_data_hash in spec_f_node.inputs.items():
                if source_data_hash in runtime_data_nodes:
                    source_d_node = runtime_data_nodes[source_data_hash]
                    port = Port(name=port_name, source=source_d_node)
                    f_node.add_input(port)

            reactor.register_node(f_node)

        # Pass 3: Instantiate all Channels to wire FuncNode outputs
        for spec_channel in topology.channels:
            source_f_node = runtime_func_nodes.get(
                spec_channel.source_node_instance_hash
            )
            target_d_node = runtime_data_nodes.get(spec_channel.target_data_slot_hash)

            if source_f_node and target_d_node:
                # Update the kind on the corresponding input port for dual-barrier check
                # Note: This assumes input port names match output port names for signals,
                # which is a convention we need to enforce or make more robust.
                # For now, we find the port connected to the target DataNode.
                for port in source_f_node.inputs.values():
                    # This logic is complex. A simpler way is to connect the port
                    # to the channel later. Let's rely on the ChannelDef for kind.
                    pass

                # This runtime channel connects an output port to a data node
                channel = ReactorChannel(
                    source=source_f_node,
                    target=target_d_node,
                    output_name=spec_channel.port_name,
                    tag_filter=spec_channel.tag_filter,
                    kind=spec_channel.kind,
                )
                reactor.register_channel(channel)

        # Pass 4: Kickstart the reactor by marking all function nodes as dirty.
        # This gives the reactor an initial set of nodes to check for readiness,
        # breaking the cold start deadlock.
        for f_node in runtime_func_nodes.values():
            reactor._dirty_func_nodes.add(f_node)

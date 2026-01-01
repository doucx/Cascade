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
        # 1. 编译 (Compilation)
        compilation_result = self.frontend.compile(target)
        topology = self.backend.compile(compilation_result.ir)
        symbol_table = compilation_result.symbol_table

        # 2. 组装 (Assembly)
        reactor = Reactor(executor=None)  # Executor will be injected right after
        physics_executor = PhysicsExecutor(reactor=reactor, symbol_table=symbol_table)
        reactor.executor = physics_executor

        # 3. 配置 (Configuration)
        loop = asyncio.get_running_loop()
        result_future = loop.create_future()
        termination_future = loop.create_future()

        def on_main_output(payload: Any):
            if not result_future.done():
                result_future.set_result(payload)

        def on_termination_signal(payload: Any):
            if not termination_future.done():
                termination_future.set_result(True)

        reactor.register_sink("main_output", on_main_output)
        reactor.register_sink("__system_lifecycle_signal", on_termination_signal)

        # This call will fail until the next phase is implemented
        self._load_topology(reactor, topology)

        # 4. 运行与等待 (Execution & Observation)
        run_task = asyncio.create_task(reactor.run())

        try:
            # Wait for both the result and the termination signal to ensure
            # the graph has fully completed its lifecycle.
            await asyncio.wait(
                [result_future, termination_future],
                return_when=asyncio.ALL_COMPLETED,
            )

            if result_future.exception():
                raise result_future.exception()
            if termination_future.exception():
                raise termination_future.exception()

            if not result_future.done():
                raise RuntimeError("Workflow terminated without producing a result.")

            return result_future.result()

        finally:
            # 5. 清理 (Teardown)
            if not run_task.done():
                reactor.stop()
                # Yield control briefly to allow the reactor loop to process the stop signal
                await asyncio.sleep(0)
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass  # Cancellation is the expected outcome here.

    def _load_topology(self, reactor: Reactor, topology: BipartiteGraph):
        """
        Translates the static BipartiteGraph spec into live, interconnected
        physics objects within the Reactor.
        This method will be implemented in the next phase.
        """
        # Placeholder for the topology loading logic.
        raise NotImplementedError(
            "VMExecutionStrategy._load_topology is not yet implemented."
        )
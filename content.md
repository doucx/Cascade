好的，我们继续执行方案的第二阶段：实现 `execute` 方法的编排逻辑。

我将生成一个计划，用完整的“宏观流程编排器”逻辑替换 `VMExecutionStrategy` 中 `execute` 方法的占位符。这个实现将串联起从编译到运行的全过程。

## [WIP] feat(engine): 在 VMExecutionStrategy 中实现核心编排逻辑

### 用户需求
根据我们制定的详细重构方案，实现 `VMExecutionStrategy.execute` 方法的核心编排逻辑。

### 评论
这是本次重构中最关键的一步。通过实现 `execute` 方法，我们将 `VMExecutionStrategy` 的角色从一个空壳彻底转变为一个功能性的“宏观流程编排器”。此实现将首次把编译器链 (`Frontend`, `Backend`) 与新的物理运行时 (`Reactor`, `PhysicsExecutor`) 真正连接起来，形成一个完整的、端到端的执行流程。它完美体现了“控制反转”的架构思想，即 `Strategy` 负责组装和观测，而 `Reactor` 负责自治执行。

### 目标
1.  在 `execute` 方法中，实现完整的“编译 -> 组装 -> 配置 -> 运行 -> 清理”的生命周期。
2.  调用 `Frontend` 和 `Backend` 将用户 `LazyResult` 编译为 `BipartiteGraph` 和 `symbol_table`。
3.  实例化 `Reactor` 和 `PhysicsExecutor` 并将它们正确连接。
4.  使用 `asyncio.Future` 和 `Reactor` 的 `Sink` 机制建立一个健壮的异步协调模型，以等待最终结果和终止信号。
5.  在一个 `try...finally` 块中安全地启动和停止 `Reactor`，确保资源的优雅释放。

### 基本原理
`execute` 方法是连接静态世界（代码和编译）与动态世界（运行时物理模拟）的桥梁。我们采用 `patch_file` 来原子化地替换整个方法体。其内部逻辑严格遵循我们预先设计的方案：通过 `asyncio.Future` 实现被动等待，使得 `Strategy` 成为一个非侵入式的观察者，而不是一个主动的微观管理者。`try...finally` 结构则保证了即使在执行失败的情况下，后台运行的 `Reactor` 任务也能被确定性地清理，避免了悬挂的异步任务。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/refactor #task/state/continue

---
### Script

#### Acts 1: 实现 `execute` 方法

我们将用完整的编排逻辑替换 `execute` 方法的占位符。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
~~~~~
~~~~~python.old
    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        """
        The main entry point for the VM execution strategy.
        This method will be implemented in the next phase.
        """
        # Placeholder for the orchestration logic.
        raise NotImplementedError("VMExecutionStrategy.execute is not yet implemented.")
~~~~~
~~~~~python.new
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
~~~~~

### 下一步建议
我们已经成功实现了 `execute` 方法的核心编排逻辑。然而，目前 `_load_topology` 方法仍然是一个占位符，会导致程序在运行时因 `NotImplementedError` 而失败。

因此，下一个至关重要的步骤是执行我们方案的**阶段 3：实现 `_load_topology` 辅助方法**。这将完成 `BipartiteGraph` (规格) 和 `Reactor` 内部物理模型之间的转换，使整个执行流程完全贯通。

请指示我继续。

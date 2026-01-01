好的，我们已经确认了死锁的存在。现在，我们将执行调试的标准操作：在系统的关键路径上植入诊断日志，以“照亮”代码的执行流程，看看它到底卡在了哪里。

我将生成一个计划，通过 `patch_file` 在 `VMExecutionStrategy`、`Reactor` 和 `PhysicsExecutor` 的关键位置添加临时的 `print` 语句。

## [WIP] test(vm): 为 VMStrategy 死锁问题添加诊断日志

### 用户需求
最小化集成测试 `test_vm_strategy_executes_simplest_workflow` 出现死锁。需要通过添加日志来追踪 `VMExecutionStrategy`, `Reactor`, 和 `PhysicsExecutor` 之间的详细交互流程，以定位死锁的根本原因。

### 评论
这是解决复杂异步死锁问题的经典且必要的一步。通过在系统的关键“关节”——策略层、反应堆循环和执行器——中插入日志，我们可以清晰地观察到控制流是否按预期传递。日志输出将揭示是 `Reactor` 从未启动工作，还是 `Executor` 的完成信号从未被 `Reactor` 接收，从而为我们提供解决问题的直接证据。

### 目标
1.  **策略层 (`VMExecutionStrategy`)**: 记录 `execute` 方法的启动、等待和清理阶段。
2.  **反应堆层 (`Reactor`)**: 记录 `run` 循环的启动、休眠和唤醒，`step` 方法的执行，以及 `push_event` 的调用。
3.  **执行器层 (`PhysicsExecutor`)**: 记录 `submit` 方法的调用和完成（即推送 `ExecutionFinished` 事件之前）。

### 基本原理
死锁的本质是一个等待循环：A 等待 B，而 B 正在等待 A。我们的日志植入点被设计用来打破这个信息黑盒。
- `VMExecutionStrategy` 的日志将告诉我们“A 正在等待”。
- `Reactor` 的日志将告诉我们“B 正在等待”或“B 正在做什么”。
- `PhysicsExecutor` 的日志将告诉我们 `Reactor` 是否成功将工作委托给了 `Executor`，以及 `Executor` 是否成功将结果报告回 `Reactor`。
通过分析这三者日志的时间线，我们就能精确地定位到哪个环节的通信中断了。

### 标签
#intent/tooling #flow/ready #priority/critical #comp/engine #comp/tests #scope/core #ai/instruct #task/domain/engine #task/object/vm-strategy #task/action/bug-fix #task/state/continue

---
### Script

#### Acts 1: 为 VMExecutionStrategy 添加日志

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
~~~~~

#### Acts 2: 为 Reactor 添加日志

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    def push_event(self, event: ReactorEvent):
        """Pushes an event to the queue and wakes up the run loop if it's waiting."""
        self._event_queue.append(event)
        self._activity_signal.set()

    def _has_pending_work(self) -> bool:
        """Checks if there's any immediate work to be done."""
        return bool(
            self._event_queue or self._dirty_func_nodes or self._pending_on_resource
        )

    async def run(self):
        """Continuously runs the reactor loop until stop() is called."""
        self._is_running = True
        while self._is_running:
            await self.step()

            # If step() resulted in more immediate work, loop again without waiting.
            if self._has_pending_work():
                continue

            # If no more work, wait for a new event to arrive.
            await self._activity_signal.wait()
            self._activity_signal.clear()

    def stop(self):
        """Stops the reactor's run loop gracefully."""
        self._is_running = False
        self._activity_signal.set()
~~~~~
~~~~~python.new
    def push_event(self, event: ReactorEvent):
        """Pushes an event to the queue and wakes up the run loop if it's waiting."""
        print(f"[Reactor.push] Pushing event: {type(event).__name__}")
        self._event_queue.append(event)
        self._activity_signal.set()

    def _has_pending_work(self) -> bool:
        """Checks if there's any immediate work to be done."""
        return bool(
            self._event_queue or self._dirty_func_nodes or self._pending_on_resource
        )

    async def run(self):
        """Continuously runs the reactor loop until stop() is called."""
        print("[Reactor.run] Starting run loop.")
        self._is_running = True
        while self._is_running:
            print(f"[Reactor.run] Loop iteration. Has work: {self._has_pending_work()}")
            await self.step()

            # If step() resulted in more immediate work, loop again without waiting.
            if self._has_pending_work():
                continue

            # If no more work, wait for a new event to arrive.
            print("[Reactor.run] No immediate work. Awaiting activity signal...")
            await self._activity_signal.wait()
            self._activity_signal.clear()
            print("[Reactor.run] Woke up from activity signal.")
        
        print("[Reactor.run] Run loop stopped.")

    def stop(self):
        """Stops the reactor's run loop gracefully."""
        print("[Reactor.run] Stop signal received.")
        self._is_running = False
        self._activity_signal.set()
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
    async def step(self):
        """
        Advance the reactor by one atomic "tick".
~~~~~
~~~~~python.new
    async def step(self):
        print("[Reactor.step] Step started.")
        """
        Advance the reactor by one atomic "tick".
~~~~~
~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/reactor/core.py
~~~~~
~~~~~python.old
                if not progress_made:
                    # Stable state reached: No events processed, no candidates to check.
                    break
                else:
                    # Events were processed, loop again to check if they triggered anything new
                    continue

            fire_tasks = []
~~~~~
~~~~~python.new
            if not progress_made:
                # Stable state reached: No events processed, no candidates to check.
                print("[Reactor.step] Step reached stable state.")
                break
            else:
                # Events were processed, loop again to check if they triggered anything new
                continue

        fire_tasks = []
~~~~~

#### Acts 3: 为 PhysicsExecutor 添加日志

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/executors/physics.py
~~~~~
~~~~~python.old
    async def submit(self, node: FuncNode, inputs: Dict[str, Token]):
        """
        Executes the logic for a given FuncNode and reports the result back
        to the reactor.
        """
        outputs = {}
        error = None

        try:
            # 1. Linking: Find the function in the symbol table.
            # We use node.name as the hash key, which is a test convention.
            # In a real system, a dedicated hash field would be used.
            func = self._symbol_table.get(node.name)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    "not found in symbol table."
                )

            # 2. Unpack Payloads: Convert Dict[str, Token] to Dict[str, Any]
            kwargs = {name: token.payload for name, token in inputs.items()}

            # 3. Execution
            result = func(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            # 4. Wrap Result: Convert the raw result back into a Token.
            # For now, we assume a single 'result' output port with 'default' tag.
            outputs["result"] = Token(payload=result, tag="default")

        except Exception as e:
            error = e

        # 5. Report: Push an ExecutionFinished event to the reactor.
        event = ExecutionFinished(node=node, outputs=outputs, error=error)
        self._reactor.push_event(event)
~~~~~
~~~~~python.new
    async def submit(self, node: FuncNode, inputs: Dict[str, Token]):
        """
        Executes the logic for a given FuncNode and reports the result back
        to the reactor.
        """
        print(f"[Executor] Submitting node '{node.name}' for execution.")
        outputs = {}
        error = None

        try:
            # 1. Linking: Find the function in the symbol table.
            # We use node.name as the hash key, which is a test convention.
            # In a real system, a dedicated hash field would be used.
            func = self._symbol_table.get(node.name)
            if not func:
                raise RuntimeError(
                    f"Linking failed: function for node '{node.name}' "
                    "not found in symbol table."
                )

            # 2. Unpack Payloads: Convert Dict[str, Token] to Dict[str, Any]
            kwargs = {name: token.payload for name, token in inputs.items()}

            # 3. Execution
            result = func(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            # 4. Wrap Result: Convert the raw result back into a Token.
            # For now, we assume a single 'result' output port with 'default' tag.
            outputs["result"] = Token(payload=result, tag="default")
            print(f"[Executor] Node '{node.name}' execution finished successfully.")

        except Exception as e:
            error = e
            print(f"[Executor] Node '{node.name}' execution FAILED with error: {e}")

        # 5. Report: Push an ExecutionFinished event to the reactor.
        event = ExecutionFinished(node=node, outputs=outputs, error=error)
        self._reactor.push_event(event)
~~~~~

### 下一步建议
我们已经为系统的所有关键部分都安装了“监视器”。现在，请再次运行 `pytest packages/cascade-engine/tests/integration/test_vm_strategy_integration.py`。

这一次，测试应该仍然会挂起，但终端会打印出详细的执行日志。**请将完整的、未经删减的日志输出提供给我**。通过分析这些日志的时间顺序，我们就能准确定位到死锁发生的环节。

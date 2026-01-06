## [WIP] fix: 修复 LocalComputeService 竞态条件并增强 Machine 日志

### 错误分析

用户报告的测试失败（`AssertionError`）实际上是由 `LocalComputeService` 和 `Machine` 之间的一个微小的**竞态条件**引起的。

1.  **真空期 (The Vacuum)**: 当 `LocalComputeService` 从 `inbound_queue` 中取出一个请求 (`get()`)，但还没有来得及启动处理协程 (`_process_request`) 时，存在一个极其短暂的时间窗口。
2.  **状态误判**: 在这个窗口期内，`inbound_queue` 是空的（请求已被取出），而 `_active_count` 也是 0（协程还未开始执行并增加计数）。
3.  **过早退出**: 如果 `Machine` 恰好在这个时刻检查 `is_idle()`，它会错误地认为系统已经处理完所有任务，从而过早终止运行，导致下游节点（如 Stainer 或最终输出节点）从未收到结果，最终测试断言失败。

**解决方案**:
我们将修改 `LocalComputeService` 的计数逻辑，采用**“预增加 (Pre-increment)”**策略：在从队列取出请求的那一刻立即增加 `_active_count`，确保存储在“空中”的任务被正确统计。

同时，响应用户的请求，我们将为 `Machine` 及其组件添加详细的结构化日志，以便清晰地观察状态流转。

### 用户需求

1.  解决测试失败的问题。
2.  插入日志以监视状态。

### 评论

这是一个非常经典的异步并发 bug，也是我们进行“黑盒集成测试”的价值所在——它在代码合并到主分支前暴露了这种时序依赖问题。修复这个问题将显著提高 `Machine` 在高并发场景下的稳定性。

### 目标

1.  修改 `LocalComputeService`，实现 active count 的预增加逻辑。
2.  增强 `Machine` 的日志，使其输出每次循环的决策依据（Reactor Fired Count, Queue Sizes, Idle State）。
3.  更新测试配置，启用日志输出。

### 基本原理

通过消除任务状态的“真空期”，我们确保 `Machine` 只有在真正的“全局静止”状态下才会退出。增强的日志则提供了必要的可观测性，让我们能确信系统是按预期工作的。

### 标签

#intent/fix #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/testing #task/object/machine-integration #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 LocalComputeService 的竞态条件

我们将修改 `run` 方法以在取出任务时立即增加计数，并修改 `_process_request` 以仅负责减少计数。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python.old
    async def run(self) -> None:
        self._running = True
        logger.info("LocalComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                # Create a non-blocking task for each request to allow concurrency
                asyncio.create_task(self._process_request(request))
        finally:
            self._pool.shutdown(wait=False)
            logger.info("LocalComputeService stopped.")

    def stop(self) -> None:
        self._running = False
        # To unblock the `run` loop, we can put a sentinel value,
        # but for now, we assume the managing task will be cancelled.

    async def _process_request(self, request: ComputeRequest) -> None:
        self._active_count += 1
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)

            # 3. Execute
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._pool, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            # Per v3.1 spec, exceptions are treated as values
            result = e

        # 4. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))
~~~~~
~~~~~python.new
    async def run(self) -> None:
        self._running = True
        logger.info("LocalComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                # Pre-increment active count to avoid race condition where
                # queue is empty but task hasn't started yet.
                self._active_count += 1
                # Create a non-blocking task for each request to allow concurrency
                asyncio.create_task(self._process_request(request))
        finally:
            self._pool.shutdown(wait=False)
            logger.info("LocalComputeService stopped.")

    def stop(self) -> None:
        self._running = False
        # To unblock the `run` loop, we can put a sentinel value,
        # but for now, we assume the managing task will be cancelled.

    async def _process_request(self, request: ComputeRequest) -> None:
        # Note: self._active_count is incremented in run() before calling this
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)

            # 3. Execute
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._pool, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            logger.exception(
                f"Computation failed for request on code {request.code_hash}"
            )
            # Per v3.1 spec, exceptions are treated as values
            result = e
        finally:
            self._active_count -= 1

        # 4. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))
~~~~~

#### Acts 2: 增强 Machine 日志

在 `Machine.run` 中添加 DEBUG 级别的状态日志。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/machine.py
~~~~~
~~~~~python.old
    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

        try:
            while True:
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Check for Quiescence
                # If the reactor did nothing, and there's no pending I/O...
                if fired_count == 0 and self.ingress_queue.empty():
                    # ...and the compute service has no active workers...
                    if self.compute_service.is_idle():
                        logger.info("Machine idle. Stopping.")
                        break

                    # If we are just waiting for Compute, yield to the event loop
                    # to give the Service a chance to work.
                    await asyncio.sleep(0.001)
                else:
                    # If we did work, yield briefly to allow I/O ingress processing
                    # but return quickly to sustain high throughput.
                    await asyncio.sleep(0)
~~~~~
~~~~~python.new
    async def run(self) -> None:
        logger.info("Machine started.")

        # Start the Compute Service
        service_task = asyncio.create_task(self.compute_service.run())

        try:
            while True:
                # 1. Drive the Physics Kernel (Synchronous Step)
                fired_count = self.reactor.step()

                # 2. Check for Quiescence
                ingress_empty = self.ingress_queue.empty()
                compute_idle = self.compute_service.is_idle()

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Machine Step: fired={fired_count}, "
                        f"ingress_empty={ingress_empty}, "
                        f"compute_idle={compute_idle} "
                        f"(inbound={self.compute_service.inbound_queue.qsize()}, "
                        f"active={self.compute_service._active_count})"
                    )

                # If the reactor did nothing, and there's no pending I/O...
                if fired_count == 0 and ingress_empty:
                    # ...and the compute service has no active workers...
                    if compute_idle:
                        logger.info("Machine idle. Stopping.")
                        break

                    # If we are just waiting for Compute, yield to the event loop
                    # to give the Service a chance to work.
                    await asyncio.sleep(0.001)
                else:
                    # If we did work, yield briefly to allow I/O ingress processing
                    # but return quickly to sustain high throughput.
                    await asyncio.sleep(0)
~~~~~

#### Acts 3: 更新测试以启用日志

更新 `test_machine_integration.py`，配置 logging 到 stderr。

~~~~~act
patch_file
tests/vm/integration/test_machine_integration.py
~~~~~
~~~~~python.old
    # Run! (Should exit automatically when idle)
    await machine.run()

    # --- 5. Verification ---
    
    assert len(captured_events) == 1
~~~~~
~~~~~python.new
    # Run! (Should exit automatically when idle)
    # Enable logging to see Machine internals during test
    import logging
    logging.basicConfig(level=logging.DEBUG)
    # Silence asyncio debug logs
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    await machine.run()

    # --- 5. Verification ---
    
    assert len(captured_events) == 1
~~~~~

### 下一步建议

现在修复了核心的竞态条件并添加了日志，请再次运行测试：
`pytest tests/vm/integration/test_machine_integration.py`

如果通过，我们就可以自信地进入白皮书更新阶段。

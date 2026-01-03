好的，我们现在开始执行重构计划的第三步：将 `NodeProcessor` 拆分为一个微管线。

这是一个纯粹的内部重构，旨在提高代码的可读性和模块化程度，使其逻辑结构与 v3.0 的 “Bleacher -> Worker -> Stainer” 架构对齐。外部接口和行为将保持不变。

我将生成一个计划来执行此操作。

## [WIP] refactor(engine): 将 NodeProcessor 拆分为微管线

### 用户需求
根据重构计划的第三步，需要将 `cascade-engine` 包中的 `NodeProcessor` 类的内部逻辑拆分为三个独立的辅助方法：`_execute_core`, `_handle_successful_outcome`, 和 `_handle_failed_outcome`。

### 评论
这是一个非常健康的重构步骤。它将一个庞大的、多职责的方法 (`_execute_internal`) 分解为多个单一职责的、逻辑清晰的单元。这不仅使代码更容易理解和维护，也为未来向 v3.0 的物理节点架构迁移奠定了坚实的逻辑基础。

### 目标
1.  创建一个新的私有方法 `_execute_core`，其唯一职责是调用 `self.executor.execute`。
2.  创建一个新的私有方法 `_handle_successful_outcome`，用于封装任务成功后的所有逻辑（发布事件、写入缓存）。
3.  创建一个新的私有方法 `_handle_failed_outcome`，用于封装任务失败后的所有逻辑（判断是否重试、发布事件）。
4.  重构现有的 `_execute_internal` 方法，使其作为协调器来调用这三个新的辅助方法，同时保留现有的缓存检查和 MapNode 处理逻辑。

### 基本原理
我们将 `_execute_internal` 方法中复杂的 `try...except` 重试循环体内的逻辑提取出来。
-   **Worker**: `_execute_core` 方法将代表纯粹的“工作”单元，它只关心执行业务逻辑。
-   **Stainer**: `_handle_successful_outcome` 和 `_handle_failed_outcome` 方法共同构成了“染色器”的角色，它们负责处理执行结果——无论是成功还是失败，并决定下一步的流程（返回结果或重试）。
-   **Coordinator**: `_execute_internal` 方法现在扮演一个更高级的协调者，负责编排这些微管线步骤。

这种结构分离了“做什么”（Worker）和“如何处理结果”（Stainer），是迈向更清晰、更可测试架构的关键一步。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/engine-graph-decoupling #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 `processor.py`

我们将修改 `NodeProcessor` 类，提取出三个新的辅助方法，并重写 `_execute_internal` 以使用它们。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python.old
    async def _execute_internal(
        self,
        node: Node,
        executable: Callable,
        inputs: Tuple[List[Any], Dict[str, Any]],
        cache_inputs: Dict[str, Any],
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
    ) -> Any:
        # 3. Use Resolved Arguments
        args, kwargs = inputs

        start_time = time.time()

        # 4. Cache Check
        if node.cache_policy:
            cached_value = await node.cache_policy.check(
                node.current_node_instance_hash, cache_inputs
            )
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.current_node_instance_hash,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(
                run_id=run_id,
                task_id=node.current_node_instance_hash,
                task_name=node.name,
            )
        )

        # 5. Handle Map Nodes
        from cascade.graph.model import MapNode

        if isinstance(node, MapNode):
            return await self._execute_map_node(
                node,
                executable,  # The factory is passed here
                kwargs,
                active_resources,
                run_id,
                params,
                state_backend,
                sub_graph_runner,
            )

        # 6. Retry Loop & Execution
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0
        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(node, executable, args, kwargs)
                duration = time.time() - start_time
                self.bus.publish(
                    TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.current_node_instance_hash,
                        task_name=node.name,
                        status="Succeeded",
                        duration=duration,
                        result_preview=None,
                    )
                )
                if node.cache_policy:
                    await node.cache_policy.save(
                        node.current_node_instance_hash, cache_inputs, result
                    )
                return result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id,
                            task_id=node.current_node_instance_hash,
                            task_name=node.name,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                        )
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
                else:
                    duration = time.time() - start_time
                    self.bus.publish(
                        TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.current_node_instance_hash,
                            task_name=node.name,
                            status="Failed",
                            duration=duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                    )
                    raise last_exception
        raise RuntimeError("Unexpected execution state")
~~~~~
~~~~~python.new
    async def _execute_internal(
        self,
        node: Node,
        executable: Callable,
        inputs: Tuple[List[Any], Dict[str, Any]],
        cache_inputs: Dict[str, Any],
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
    ) -> Any:
        args, kwargs = inputs
        start_time = time.time()

        # 4. Cache Check (Part of "Bleacher" logic)
        if node.cache_policy:
            cached_value = await node.cache_policy.check(
                node.current_node_instance_hash, cache_inputs
            )
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.current_node_instance_hash,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(
                run_id=run_id,
                task_id=node.current_node_instance_hash,
                task_name=node.name,
            )
        )

        # 5. Handle Map Nodes (special execution logic)
        from cascade.graph.model import MapNode

        if isinstance(node, MapNode):
            return await self._execute_map_node(
                node,
                executable,  # The factory is passed here
                kwargs,
                active_resources,
                run_id,
                params,
                state_backend,
                sub_graph_runner,
            )

        # 6. Retry Loop & Execution (Part of "Stainer" logic)
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0
        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                # "Worker" logic
                result = await self._execute_core(node, executable, args, kwargs)
                # "Stainer" success logic
                return await self._handle_successful_outcome(
                    node, run_id, cache_inputs, start_time, result
                )
            except Exception as e:
                last_exception = e
                # "Stainer" failure logic
                should_retry = await self._handle_failed_outcome(
                    e, node, run_id, attempt, max_attempts, delay, start_time
                )
                if should_retry:
                    await asyncio.sleep(delay)
                    delay *= backoff
                else:
                    raise last_exception
        raise RuntimeError("Unexpected execution state")

    async def _execute_core(
        self, node: Node, executable: Callable, args: List[Any], kwargs: Dict[str, Any]
    ) -> Any:
        """Purely executes the callable via the configured executor."""
        return await self.executor.execute(node, executable, args, kwargs)

    async def _handle_successful_outcome(
        self,
        node: Node,
        run_id: str,
        cache_inputs: Dict[str, Any],
        start_time: float,
        result: Any,
    ) -> Any:
        """Handles caching and event publishing for a successful execution."""
        duration = time.time() - start_time
        self.bus.publish(
            TaskExecutionFinished(
                run_id=run_id,
                task_id=node.current_node_instance_hash,
                task_name=node.name,
                status="Succeeded",
                duration=duration,
                result_preview=None,
            )
        )
        if node.cache_policy:
            await node.cache_policy.save(
                node.current_node_instance_hash, cache_inputs, result
            )
        return result

    async def _handle_failed_outcome(
        self,
        exception: Exception,
        node: Node,
        run_id: str,
        attempt: int,
        max_attempts: int,
        delay: float,
        start_time: float,
    ) -> bool:
        """
        Handles retry logic and event publishing for a failed execution.
        Returns True if a retry should be attempted, False otherwise.
        """
        if attempt < max_attempts:
            self.bus.publish(
                TaskRetrying(
                    run_id=run_id,
                    task_id=node.current_node_instance_hash,
                    task_name=node.name,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    delay=delay,
                    error=str(exception),
                )
            )
            return True
        else:
            duration = time.time() - start_time
            self.bus.publish(
                TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.current_node_instance_hash,
                    task_name=node.name,
                    status="Failed",
                    duration=duration,
                    error=f"{type(exception).__name__}: {exception}",
                )
            )
            return False
~~~~~

### 下一步建议
我们已经成功地将 `NodeProcessor` 的内部逻辑进行了分层。下一步，我们将继续按照重构计划进行，开始执行 **步骤 4：标准化 `Strategy` 接口**。这将进一步明确 `Engine` 和 `GraphExecutionStrategy` 之间的界限。

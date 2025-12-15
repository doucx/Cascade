简要回答
我们将实施《潜在改进点收集》中的建议，重构 `Engine` 以支持更复杂的流程，并增强可观测性。

## [WIP] refactor(runtime): Extract task execution logic and add TaskRetrying event

### 用户需求
实施《潜在改进点收集》文档中提出的两项针对 `quipu-runtime` (此处为 `cascade-runtime`) 的改进：
1.  **重构 Engine**: 将 `Engine.run` 中复杂的节点执行逻辑（缓存检查、重试循环、事件发布）提取为独立的私有方法 `_execute_node_with_policies`，以降低主循环复杂度，为阶段三的条件执行等特性做准备。
2.  **增强可观测性**: 引入 `TaskRetrying` 事件，以便在任务失败重试时发出明确的信号。

### 评论
这次重构是 Cascade 向更高级功能演进的必要步骤。将策略逻辑（Retry, Cache）与编排逻辑（Traversal, Resource Management）分离，符合单一职责原则，使得代码更易于维护和扩展。

### 目标
1.  在 `src/cascade/runtime/events.py` 中定义 `TaskRetrying` 事件。
2.  在 `src/cascade/runtime/engine.py` 中实现 `_execute_node_with_policies` 方法，并重构 `run` 方法以调用它。
3.  更新 `src/cascade/runtime/subscribers.py` 以支持 `TaskRetrying` 事件的日志输出。

### 基本原理
随着阶段三即将引入 `run_if` (条件执行) 和 `Router` (动态路由) 等特性，`Engine.run` 的主循环如果不进行重构，将变得难以管理。提取单一节点的执行逻辑是一个标准的重构手段。同时，增加重试事件填补了当前监控的盲区。

### 标签
#intent/refine #flow/draft #priority/medium
#comp/runtime #concept/executor #scope/core
#task/domain/runtime #task/object/engine #task/action/refactor
#task/state/begin

---

### Script

#### Acts 1: 定义 `TaskRetrying` 事件

我们在 `src/cascade/runtime/events.py` 中添加新的事件类型，用于描述任务重试的状态。

~~~~~act
patch_file
src/cascade/runtime/events.py
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""

    reason: str = "Unknown"  # "CacheHit", "ConditionFalse"


@dataclass(frozen=True)
class ResourceEvent(Event):
~~~~~
~~~~~python
@dataclass(frozen=True)
class TaskSkipped(TaskEvent):
    """Fired when a task is skipped due to caching or conditional logic."""

    reason: str = "Unknown"  # "CacheHit", "ConditionFalse"


@dataclass(frozen=True)
class TaskRetrying(TaskEvent):
    """Fired when a task fails but is about to be retried."""

    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None


@dataclass(frozen=True)
class ResourceEvent(Event):
~~~~~

#### Acts 2: 更新 `HumanReadableLogSubscriber`

为了验证新事件并提供更好的开发体验，我们在默认的日志订阅者中添加对 `TaskRetrying` 的支持。

~~~~~act
patch_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
)


class HumanReadableLogSubscriber:
~~~~~
~~~~~python
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
)


class HumanReadableLogSubscriber:
~~~~~

~~~~~act
patch_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)

    def _print(self, msg: str):
~~~~~
~~~~~python
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)
        bus.subscribe(TaskRetrying, self.on_task_retrying)

    def _print(self, msg: str):
~~~~~

~~~~~act
patch_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
    def on_task_skipped(self, event: TaskSkipped):
        self._print(f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})")
~~~~~
~~~~~python
    def on_task_skipped(self, event: TaskSkipped):
        self._print(f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})")

    def on_task_retrying(self, event: TaskRetrying):
        self._print(
            f"  ⚠️  Retrying task `{event.task_name}` "
            f"(Attempt {event.attempt}/{event.max_attempts}) "
            f"in {event.delay:.2f}s... Error: {event.error}"
        )
~~~~~

#### Acts 3: 重构 `Engine`

这是核心改动。我们将 `TaskRetrying` 导入 `engine.py`，并将 `run` 方法中的循环体提取到 `_execute_node_with_policies` 中。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    ResourceAcquired,
    ResourceReleased,
)
~~~~~
~~~~~python
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
)
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                results: Dict[str, Any] = {}
                for node in plan:
                    task_start_time = time.time()

                    # 0. Check Cache
                    if node.cache_policy:
                        # Construct inputs for cache check
                        # We need to resolve dependencies first to pass them to cache policy
                        # Similar logic to Executor, but just for inputs
                        inputs_for_cache = self._resolve_inputs(node, graph, results)
                        
                        cached_value = node.cache_policy.check(node.id, inputs_for_cache)
                        if cached_value is not None:
                            # Cache Hit!
                            results[node.id] = cached_value
                            self.bus.publish(
                                TaskSkipped(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="CacheHit"
                                )
                            )
                            continue

                    start_event = TaskExecutionStarted(
                        run_id=run_id, task_id=node.id, task_name=node.name
                    )
                    self.bus.publish(start_event)

                    # Determine retry policy
                    retry_policy = node.retry_policy
                    max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
                    delay = retry_policy.delay if retry_policy else 0.0
                    backoff = retry_policy.backoff if retry_policy else 1.0

                    attempt = 0
                    last_exception = None

                    while attempt < max_attempts:
                        attempt += 1
                        try:
                            result = await self.executor.execute(
                                node, graph, results, active_resources
                            )
                            results[node.id] = result

                            task_duration = time.time() - task_start_time
                            finish_event = TaskExecutionFinished(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                status="Succeeded",
                                duration=task_duration,
                                result_preview=repr(result)[:100],
                            )
                            self.bus.publish(finish_event)
                            
                            # Save to cache if policy exists
                            if node.cache_policy:
                                # Re-resolve inputs (they are already resolved, but kept in scope)
                                # Optimization: we could calculate inputs once before retry loop
                                inputs_for_save = self._resolve_inputs(node, graph, results)
                                node.cache_policy.save(node.id, inputs_for_save, result)

                            # Break the retry loop on success
                            last_exception = None
                            break

                        except Exception as e:
                            last_exception = e
                            # If we have retries left, wait and continue
                            if attempt < max_attempts:
                                # Optional: Publish a specific Retry event here in the future
                                await asyncio.sleep(delay)
                                delay *= backoff
                            else:
                                # Final failure
                                task_duration = time.time() - task_start_time
                                fail_event = TaskExecutionFinished(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    status="Failed",
                                    duration=task_duration,
                                    error=f"{type(e).__name__}: {e}",
                                )
                                self.bus.publish(fail_event)
                                raise last_exception

                run_duration = time.time() - start_time
~~~~~
~~~~~python
                results: Dict[str, Any] = {}
                for node in plan:
                    results[node.id] = await self._execute_node_with_policies(
                        node, graph, results, active_resources, run_id
                    )

                run_duration = time.time() - start_time
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                self.bus.publish(final_fail_event)
                raise

    def _resolve_inputs(self, node: Node, graph: Graph, upstream_results: Dict[str, Any]) -> Dict[str, Any]:
~~~~~
~~~~~python
                self.bus.publish(final_fail_event)
                raise

    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        task_start_time = time.time()

        # 0. Check Cache
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs(node, graph, upstream_results)
            cached_value = node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        start_event = TaskExecutionStarted(
            run_id=run_id, task_id=node.id, task_name=node.name
        )
        self.bus.publish(start_event)

        # Determine retry policy
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0

        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(
                    node, graph, upstream_results, active_resources
                )

                task_duration = time.time() - task_start_time
                finish_event = TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    status="Succeeded",
                    duration=task_duration,
                    result_preview=repr(result)[:100],
                )
                self.bus.publish(finish_event)

                # Save to cache if policy exists
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs(node, graph, upstream_results)
                    node.cache_policy.save(node.id, inputs_for_save, result)

                return result

            except Exception as e:
                last_exception = e
                # If we have retries left, wait and continue
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id,
                            task_id=node.id,
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
                    # Final failure
                    task_duration = time.time() - task_start_time
                    fail_event = TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Failed",
                        duration=task_duration,
                        error=f"{type(e).__name__}: {e}",
                    )
                    self.bus.publish(fail_event)
                    raise last_exception
        
        # Should not be reached if logic is correct
        raise RuntimeError("Unexpected execution state")

    def _resolve_inputs(self, node: Node, graph: Graph, upstream_results: Dict[str, Any]) -> Dict[str, Any]:
~~~~~

### 下一步建议
实施完成后，我们需要运行现有的测试套件以确保重构没有破坏任何功能。特别是 `test_retry.py` 应该会通过，并且如果我们更新测试来检查事件，应该能看到新的 `TaskRetrying` 事件。接下来就可以按照阶段三的计划，开始实施 `cs.dry_run` 工具。

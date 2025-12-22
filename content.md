# [WIP] refactor(engine): 提取 `NodeProcessor` 以解耦节点执行逻辑

### 用户需求
重构 `cascade.runtime.engine.Engine` 类，将其作为“上帝类”的职责进行拆分，以降低代码复杂度，提高可维护性和新手友好度。

### 评论
`Engine` 类目前集成了图构建、资源管理、调度循环和节点执行等所有逻辑，代码量大且逻辑嵌套深。提取**单节点执行逻辑**是重构的第一步，也是最关键的一步，因为它包含 retry, cache, constraint, resource injection 等最复杂的策略组合。

本次重构将引入 `NodeProcessor` 类，专门负责“如何执行一个节点”的逻辑，而 `Engine` 保留“如何调度整个图”的逻辑。

### 目标
1.  创建 `cascade.runtime.processor.NodeProcessor` 类。
2.  将 `Engine` 中的以下方法移至 `NodeProcessor`：
    *   `_execute_node_with_policies`
    *   `_execute_node_internal`
    *   `_execute_map_node`
    *   `_resolve_inputs_for_cache`
3.  将 `ArgumentResolver` 和 `ConstraintResolver` 的所有权转移给 `NodeProcessor`。
4.  更新 `Engine` 以委托 `NodeProcessor` 执行任务。

### 基本原理
通过单一职责原则 (SRP) 将关注点分离。
*   `Engine`: 负责宏观的生命周期、TCO 循环、Stage 调度和并发控制。
*   `NodeProcessor`: 负责微观的单任务执行策略（参数解析、重试、缓存、实际调用）。

对于 `map` 类型的节点，`NodeProcessor` 需要回调 `Engine` 的能力来执行子图。我们将通过在 `process` 方法中传递一个 `sub_graph_runner` 回调来实现这一点，从而避免循环依赖。

### 标签
#intent/refine #flow/ready #priority/high #comp/runtime #comp/engine #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 `NodeProcessor` 类

我们将创建一个新的文件 `packages/cascade-engine/src/cascade/runtime/processor.py`，并将节点执行相关的逻辑从 `Engine` 中提取出来。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
import time
import asyncio
from typing import Any, Dict, List, Callable, Awaitable

from cascade.graph.model import Node, Graph
from cascade.graph.build import build_graph
from cascade.spec.protocols import Executor, StateBackend, Solver
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    TaskBlocked,
)


class NodeProcessor:
    """
    Responsible for executing a single node within a workflow graph.
    Handles policies such as constraints, caching, retries, and argument resolution.
    """

    def __init__(
        self,
        executor: Executor,
        bus: MessageBus,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        solver: Solver,  # Needed for map nodes
    ):
        self.executor = executor
        self.bus = bus
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.solver = solver
        
        # Resolvers are owned by the processor
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        
        Args:
            sub_graph_runner: A callback to execute a sub-workflow (used for map nodes).
                              Signature: (target, params, parent_state_backend) -> result
        """
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        # 2. Acquire Resources
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_internal(
                node, graph, state_backend, active_resources, run_id, params, sub_graph_runner
            )
        finally:
            await self.resource_manager.release(requirements)

    async def _execute_internal(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node, graph, state_backend, active_resources, user_params=params
        )

        start_time = time.time()

        # 4. Cache Check
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs_for_cache(
                node, graph, state_backend
            )
            cached_value = await node.cache_policy.check(node.id, inputs_for_cache)
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

        self.bus.publish(
            TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
        )

        # 5. Handle Map Nodes
        if node.node_type == "map":
            return await self._execute_map_node(
                node, kwargs, active_resources, run_id, params, state_backend, sub_graph_runner
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
                result = await self.executor.execute(node, args, kwargs)
                duration = time.time() - start_time
                self.bus.publish(
                    TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Succeeded",
                        duration=duration,
                        result_preview=repr(result)[:100],
                    )
                )
                # Cache Save
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs_for_cache(
                        node, graph, state_backend
                    )
                    await node.cache_policy.save(node.id, inputs_for_save, result)
                return result
            except Exception as e:
                last_exception = e
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
                    duration = time.time() - start_time
                    self.bus.publish(
                        TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Failed",
                            duration=duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                    )
                    raise last_exception
        raise RuntimeError("Unexpected execution state")

    def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        inputs = {}
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if state_backend.has_result(edge.source.id):
                inputs[edge.arg_name] = state_backend.get_result(edge.source.id)
        return inputs

    async def _execute_map_node(
        self,
        node: Node,
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        parent_state_backend: StateBackend,
        sub_graph_runner: Callable,
    ) -> List[Any]:
        factory = node.mapping_factory
        if not kwargs:
            return []
        lengths = {k: len(v) for k, v in kwargs.items()}
        first_len = list(lengths.values())[0]
        if not all(length == first_len for length in lengths.values()):
            raise ValueError(f"Mapped inputs have mismatched lengths: {lengths}")

        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            sub_target = factory(**item_kwargs)
            if node.retry_policy:
                sub_target._retry_policy = node.retry_policy
            if node.cache_policy:
                sub_target._cache_policy = node.cache_policy
            if node.constraints:
                sub_target._constraints = node.constraints
            sub_targets.append(sub_target)

        # Execute sub-targets in parallel using the provided runner
        coros = [
            sub_graph_runner(target, params, parent_state_backend) 
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)
~~~~~

#### Acts 2: 更新 `Engine` 类

现在我们重构 `Engine` 类，移除已移动的逻辑，并连接 `NodeProcessor`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self._managed_subscribers = []
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

    def add_subscriber(self, subscriber: Any):
~~~~~
~~~~~python
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.processor import NodeProcessor


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

        # Delegate node execution logic to NodeProcessor
        self.node_processor = NodeProcessor(
            executor=self.executor,
            bus=self.bus,
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            solver=self.solver,
        )
        
        self._managed_subscribers = []
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

    def add_subscriber(self, subscriber: Any):
~~~~~

#### Acts 3: 更新 `_execute_graph` 以使用 `NodeProcessor` 并清理旧方法

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
                if executable_this_pass:
                    tasks_to_run = [
                        self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if flow_manager:
                            flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change or TTL expiration) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(
                f"Target task '{target.task.name}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)

    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            from cascade.runtime.events import TaskBlocked

            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, state_backend, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)

    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        args, kwargs = self.arg_resolver.resolve(
            node, graph, state_backend, active_resources, user_params=params
        )

        start_time = time.time()

        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs_for_cache(
                node, graph, state_backend
            )
            cached_value = await node.cache_policy.check(node.id, inputs_for_cache)
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

        self.bus.publish(
            TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
        )

        if node.node_type == "map":
            # ... (Map logic remains complex, needs careful refactoring if touched)
            # For now, we assume it can be called recursively with the state backend
            return await self._execute_map_node(
                node, args, kwargs, active_resources, run_id, params, state_backend
            )

        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0
        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(node, args, kwargs)
                duration = time.time() - start_time
                self.bus.publish(
                    TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Succeeded",
                        duration=duration,
                        result_preview=repr(result)[:100],
                    )
                )
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs_for_cache(
                        node, graph, state_backend
                    )
                    await node.cache_policy.save(node.id, inputs_for_save, result)
                return result
            except Exception as e:
                last_exception = e
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
                    duration = time.time() - start_time
                    self.bus.publish(
                        TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Failed",
                            duration=duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                    )
                    raise last_exception
        raise RuntimeError("Unexpected execution state")

    def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        inputs = {}
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if state_backend.has_result(edge.source.id):
                inputs[edge.arg_name] = state_backend.get_result(edge.source.id)
        return inputs

    async def _execute_map_node(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        parent_state_backend: StateBackend,
    ) -> List[Any]:
        factory = node.mapping_factory
        if not kwargs:
            return []
        lengths = {k: len(v) for k, v in kwargs.items()}
        first_len = list(lengths.values())[0]
        if not all(length == first_len for length in lengths.values()):
            raise ValueError(f"Mapped inputs have mismatched lengths: {lengths}")

        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            sub_target = factory(**item_kwargs)
            if node.retry_policy:
                sub_target._retry_policy = node.retry_policy
            if node.cache_policy:
                sub_target._cache_policy = node.cache_policy
            if node.constraints:
                sub_target._constraints = node.constraints
            sub_targets.append(sub_target)

        # Each sub-task is a full workflow run from the engine's perspective
        # but shares the parent's state backend to see results.
        async def run_sub_target(target):
            # For mapped tasks, we perform the full build/solve cycle for each item.
            # TCO optimization does not apply here.
            graph = build_graph(target)
            plan = self.solver.resolve(graph)
            return await self._execute_graph(
                target,
                params,
                active_resources,
                run_id,
                parent_state_backend,
                graph=graph,
                plan=plan,
            )

        coros = [run_sub_target(target) for target in sub_targets]
        return await asyncio.gather(*coros)

    def _scan_for_resources(self, graph: Graph) -> set[str]:
~~~~~
~~~~~python
                if executable_this_pass:
                    # Define a callback for map nodes to execute sub-workflows
                    async def sub_graph_runner(target, sub_params, parent_state):
                        sub_graph = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                        )
                        for node in executable_this_pass
                    ]

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        state_backend.put_result(node.id, res)
                        if flow_manager:
                            flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change or TTL expiration) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(
                f"Target task '{target.task.name}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)

    def _scan_for_resources(self, graph: Graph) -> set[str]:
~~~~~

### 下一步建议
我们已经成功地将最复杂的单节点执行逻辑（包括策略、重试、缓存等）提取到了 `NodeProcessor` 中。这显著减少了 `Engine` 的体积。

接下来的重构可以继续关注：
1.  **资源管理分离**: 将 `_resource_providers`、`_scan_for_resources` 和 `_setup_resources` 提取到一个 `ResourceContainer` 或 `DependencyInjector` 类中。
2.  **图构建分离**: 将 `StructuralHasher`、`build_graph` 和缓存逻辑提取到一个 `GraphLoader` 类中。
3.  **VM 逻辑**: `_run_vm` 可以进一步封装，或者 `Engine` 可以变身为一个抽象基类，分别有 `GraphEngine` 和 `VMEngine` 实现。

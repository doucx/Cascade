这是将“图遍历”逻辑从 `NodeProcessor` 中剥离的第一步重构。

通过此次变更，我们将把**参数解析 (Argument Resolution)**、**约束解析 (Constraint Resolution)** 和 **缓存键生成 (Cache Key Generation)** 的职责从执行层 (`NodeProcessor`) 上浮到调度层 (`GraphExecutionStrategy`)。

这使得 `NodeProcessor` 演变为一个纯粹的、无状态的（对于图结构而言）执行单元，它不再需要知道 `Graph` 或 `instance_map` 的存在，只需要接收准备好的数据并运行。

## [WIP] refactor(engine): 将图遍历与依赖解析逻辑从 NodeProcessor 上浮至 Strategy

### 用户需求
执行重构计划 "engine 与 graph 的预重构计划.md" 的第一步，解除 `NodeProcessor` 对 `Graph` 对象的依赖，使其成为纯粹的执行器。

### 评论
这是一个关键的架构解耦步骤。通过将“数据的查找”与“数据的处理”分离，我们为未来引入新的 IR、优化器或不同的执行后端打下了基础。这也大大简化了 `NodeProcessor` 的测试难度，因为不再需要构造复杂的 Mock Graph。

### 目标
1.  在 `ArgumentResolver` 中新增 `resolve_cache_inputs` 方法，迁移原 `NodeProcessor` 的缓存键生成逻辑。
2.  修改 `NodeProcessor.process` 签名，移除 `graph` 和 `instance_map`，改为接收预先解析好的 `inputs` (args/kwargs), `requirements` 和 `cache_inputs`。
3.  更新 `GraphExecutionStrategy`，在调用 Processor 前负责协调所有解析器的工作。

### 基本原理
**单一职责原则 (SRP)**：
*   **Strategy**: 负责图的遍历、依赖的查找和数据的准备。它拥有“上帝视角”。
*   **Processor**: 负责资源的获取、任务的执行和结果的汇报。它只关注“当下”。

这种分离确保了当图结构发生变化（如 v3.0 引入物理节点）时，我们只需要修改 Strategy 的解析逻辑，而无需改动 Processor 的执行逻辑。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 增强 ArgumentResolver 以支持缓存输入解析

我们将 `NodeProcessor` 中提取缓存输入的逻辑迁移到 `ArgumentResolver` 中，使其成为解析逻辑的一部分。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python.old
class ArgumentResolver:
    async def resolve(
        self,
        node: Node,
        graph: Graph,
~~~~~
~~~~~python.new
class ArgumentResolver:
    async def resolve_cache_inputs(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        # TODO: This needs to be smarter for caching.
        # It should probably include data from input_bindings too?
        # For now, keeping legacy behavior (edge results only).
        inputs = {}
        incoming_edges = [
            edge
            for edge in graph.edges
            if edge.target.current_node_instance_hash == node.current_node_instance_hash
        ]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if await state_backend.has_result(edge.source.current_node_instance_hash):
                inputs[edge.arg_name] = await state_backend.get_result(
                    edge.source.current_node_instance_hash
                )
        return inputs

    async def resolve(
        self,
        node: Node,
        graph: Graph,
~~~~~

#### Acts 2: 净化 NodeProcessor

我们移除 `process` 方法中的 `graph` 和 `instance_map` 参数，不再在内部调用解析器，而是直接使用传入的解析结果。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
import time
import asyncio
from typing import Any, Dict, List, Callable, Awaitable, Optional, TYPE_CHECKING, Tuple


from cascade.graph.model import Node

if TYPE_CHECKING:
    from cascade.graph.model import MapNode
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

        # Resolvers are owned by the processor, but now invoked by the Strategy
        self.arg_resolver = ArgumentResolver()
        # ConstraintResolver now needs the instance map to resolve dynamic values
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
        node: Node,
        inputs: Tuple[List[Any], Dict[str, Any]],
        requirements: Dict[str, Any],
        cache_inputs: Dict[str, Any],
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
    ) -> Any:
        # 1. Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.current_node_instance_hash,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        # 2. Acquire Resources
        if requirements:
            await self.resource_manager.acquire(requirements)
            try:
                return await self._execute_internal(
                    node,
                    inputs,
                    cache_inputs,
                    state_backend,
                    active_resources,
                    run_id,
                    params,
                    sub_graph_runner,
                )
            finally:
                await self.resource_manager.release(requirements)
        else:
            # FAST PATH: No resources required
            return await self._execute_internal(
                node,
                inputs,
                cache_inputs,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
            )

    async def _execute_internal(
        self,
        node: Node,
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
                result = await self.executor.execute(node, args, kwargs)
                duration = time.time() - start_time
                # Optimization: Only compute result_preview if necessary or make it cheap
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
                # Cache Save
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

    async def _execute_map_node(
        self,
        node: "MapNode",
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        parent_state_backend: StateBackend,
        sub_graph_runner: Callable,
    ) -> List[Any]:
        if not node.mapping_factory:
            return []  # Should not happen if graph is well-formed

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
            # Propagate policies
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

#### Acts 3: 更新 GraphExecutionStrategy

我们在 `Strategy` 中编排数据的准备工作，显式调用 Resolvers，并将结果注入 Processor。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.current_node_instance_hash
                            == target_node.current_node_instance_hash
                            else None
                        )
                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    graph,
                                    state_backend,
                                    active_resources,
                                    run_id,
                                    params,
                                    sub_graph_runner,
                                    instance_map,
                                    input_overrides=overrides,
                                ),
                            )
                        )

                    if len(tasks_to_run) == 1:
~~~~~
~~~~~python.new
                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.current_node_instance_hash
                            == target_node.current_node_instance_hash
                            else None
                        )

                        # Resolve everything in Strategy layer
                        requirements = (
                            await self.node_processor.constraint_resolver.resolve(
                                node,
                                graph,
                                state_backend,
                                self.constraint_manager,
                                instance_map,
                            )
                        )

                        inputs = await self.node_processor.arg_resolver.resolve(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            instance_map=instance_map,
                            user_params=params,
                            input_overrides=overrides,
                        )

                        cache_inputs = await self.node_processor.arg_resolver.resolve_cache_inputs(
                            node, graph, state_backend
                        )

                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    inputs,
                                    requirements,
                                    cache_inputs,
                                    state_backend,
                                    active_resources,
                                    run_id,
                                    params,
                                    sub_graph_runner,
                                ),
                            )
                        )

                    if len(tasks_to_run) == 1:
~~~~~

### 下一步建议
我们已经切断了 `NodeProcessor` 对 `Graph` 的直接依赖。下一步，我们将着手实现重构计划的步骤 2：**解耦 `Node` 对象与 Python Callable**。

这意味着 `Node` 将不再直接持有 `callable_obj`，而是通过 `TaskDef` 或 `Registry` 来进行动态查找。这将进一步纯化我们的数据结构，为序列化和分布式执行铺平道路。

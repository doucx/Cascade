好的，我们将执行重构计划的第四步：标准化 `Strategy` 接口。我们将引入 `ExecutionContext` 来封装执行所需的上下文信息，从而简化 `execute` 方法的签名，并使接口更加稳定和易于扩展。

## [WIP] refactor(engine): standardize ExecutionStrategy interface with ExecutionContext

### 用户需求
根据重构计划第四步，标准化 `ExecutionStrategy` 接口。
1.  引入 `ExecutionContext` 数据类，封装执行所需的运行时上下文（`run_id`, `state_backend`, `resources` 等）。
2.  更新 `ExecutionStrategy` 协议，使其 `execute` 方法接收 `ExecutionContext` 对象，而不是长参数列表。
3.  更新 `GraphExecutionStrategy` 和 `Engine` 以适配新的接口。

### 评论
引入“参数对象”模式（Parameter Object Pattern）是这一步的关键。通过将散乱的参数封装进 `ExecutionContext`，我们不仅清理了方法签名，还为未来在不破坏接口的前提下向执行上下文添加新属性（如 `trace_id`, `user_context` 等）留出了空间。这使得 `Engine` 与 `Strategy` 之间的契约更加稳固。

### 目标
1.  在 `cascade/runtime/strategies/base.py` 中定义 `ExecutionContext` 数据类。
2.  重构 `ExecutionStrategy` 协议。
3.  重构 `GraphExecutionStrategy` 的 `execute` 实现。
4.  重构 `Engine.run` 中的调用逻辑。

### 基本原理
-   **封装性**: 将执行上下文细节封装在一个对象中，减少了模块间传递参数的噪音。
-   **可扩展性**: 未来如果 Strategy 需要更多信息（例如 OpenTelemetry Context），只需在 `ExecutionContext` 中添加字段，而无需修改所有 Strategy 的 `execute` 签名。
-   **解耦**: `Engine` 不需要知道 `Strategy` 具体需要哪些参数，只需传递标准的 Context 对象。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #concept/executor #scope/core #ai/instruct #task/domain/architecture #task/object/strategy-interface #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 定义 `ExecutionContext` 并更新协议

我们将在 `base.py` 中引入 `ExecutionContext` 并更新 `ExecutionStrategy` 协议。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/base.py
~~~~~
~~~~~python
from typing import Protocol, Any, Dict
from dataclasses import dataclass, field
from contextlib import ExitStack
from cascade.spec.protocols import StateBackend


@dataclass
class ExecutionContext:
    """
    Encapsulates the runtime context required for a strategy to execute a workflow.
    """

    run_id: str
    state_backend: StateBackend
    run_stack: ExitStack
    active_resources: Dict[str, Any] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)


class ExecutionStrategy(Protocol):
    """
    Protocol defining a strategy for executing a workflow target.
    """

    async def execute(
        self,
        target: Any,
        context: ExecutionContext,
    ) -> Any: ...
~~~~~

#### Acts 2: 更新 `GraphExecutionStrategy`

我们将更新 `GraphExecutionStrategy` 以接受 `ExecutionContext`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
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
        current_target = target
        next_input_overrides = None
        local_context_cache = {}

        while True:
            with ExitStack() as step_stack:
                input_overrides = None
                await state_backend.clear()

                if current_target._uuid in local_context_cache:
                    (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    ) = local_context_cache[current_target._uuid]
                else:
                    graph, instance_map, executable_registry = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    current_graph_structure_hash = self.blueprint_hasher.compute_hash(
                        graph
                    )
                    if current_graph_structure_hash in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[
                            current_graph_structure_hash
                        ]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[current_graph_structure_hash] = (
                            indexed_plan
                        )

                    local_context_cache[current_target._uuid] = (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    )

                required_resources = self.resource_container.scan(
                    graph, executable_registry
                )
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                if next_input_overrides:
                    input_overrides = next_input_overrides
                    next_input_overrides = None

                graph_result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                    executable_registry,
                    root_input_overrides=input_overrides,
                )
~~~~~
~~~~~python.new
    async def execute(
        self,
        target: Any,
        context: "ExecutionContext",  # Use string forward ref or import if needed, assuming import logic handled
    ) -> Any:
        # Unpack context for convenience
        run_id = context.run_id
        state_backend = context.state_backend
        active_resources = context.active_resources
        params = context.params
        run_stack = context.run_stack

        current_target = target
        next_input_overrides = None
        local_context_cache = {}

        while True:
            with ExitStack() as step_stack:
                input_overrides = None
                await state_backend.clear()

                if current_target._uuid in local_context_cache:
                    (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    ) = local_context_cache[current_target._uuid]
                else:
                    graph, instance_map, executable_registry = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    current_graph_structure_hash = self.blueprint_hasher.compute_hash(
                        graph
                    )
                    if current_graph_structure_hash in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[
                            current_graph_structure_hash
                        ]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[current_graph_structure_hash] = (
                            indexed_plan
                        )

                    local_context_cache[current_target._uuid] = (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    )

                required_resources = self.resource_container.scan(
                    graph, executable_registry
                )
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                if next_input_overrides:
                    input_overrides = next_input_overrides
                    next_input_overrides = None

                graph_result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                    executable_registry,
                    root_input_overrides=input_overrides,
                )
~~~~~

我们需要确保 `GraphExecutionStrategy` 文件中导入了 `ExecutionContext`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
from cascade.graph.hashing import BlueprintHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.jump import Jump
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


class GraphExecutionResult:
~~~~~
~~~~~python.new
from cascade.graph.hashing import BlueprintHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.jump import Jump
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.strategies.base import ExecutionContext


class GraphExecutionResult:
~~~~~

#### Acts 3: 更新 `Engine`

最后，我们更新 `Engine.run` 方法以构建上下文并调用策略。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.strategies import GraphExecutionStrategy


class Engine:
~~~~~
~~~~~python.new
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.strategies import GraphExecutionStrategy
from cascade.runtime.strategies.base import ExecutionContext


class Engine:
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
                active_resources: Dict[str, Any] = {}

                final_result = await strategy.execute(
                    target=workflow_target,
                    run_id=run_id,
                    params=params or {},
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                )

            duration = time.time() - start_time
~~~~~
~~~~~python.new
                active_resources: Dict[str, Any] = {}

                context = ExecutionContext(
                    run_id=run_id,
                    state_backend=state_backend,
                    run_stack=run_stack,
                    active_resources=active_resources,
                    params=params or {},
                )

                final_result = await strategy.execute(target=workflow_target, context=context)

            duration = time.time() - start_time
~~~~~

### 下一步建议
这是本次重构计划的最后一步。完成此步骤并提交后，我们的整个“解耦 Engine 与 Graph”的重构目标就达成了。建议在提交后运行所有测试，确保没有引入回归错误。

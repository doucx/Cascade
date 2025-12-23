好的，我们开始实施。

这是完成 `Cascade 架构重构` 路线图第四步（`[COMMIT 4]`）的计划。我们将实现通用的图结构缓存，这不仅能修复当前性能测试中的循环检测错误，还能将 TCO 优化的能力从简单的单任务递归推广到任意复杂的、结构稳定的递归工作流。

## [WIP] refactor: 在 GraphExecutionStrategy 中实现通用结构缓存

### 错误分析

`heavy_complex_countdown` 基准测试失败的根本原因并非 Bug，而是架构演进过程中的一个必然阶段。

1.  **旧 TCO 机制失效**：旧的 TCO “快速通道”依赖 `_is_simple_task` 检查，仅能优化不含任何依赖的纯粹递归任务（如 `simple_countdown`）。`heavy_complex_countdown` 包含对 `noop()` 的依赖，因此无法进入此快速通道。
2.  **新求解器更精确**：在核心重构（结构-数据分离）之后，`Engine` 对每一个无法走快速通道的递归迭代，都会执行完整的图构建和求解。
3.  **循环暴露**：`heavy_complex_countdown(n-1, _dummy=dep_chain)` 的结构在图中形成了一个从自身到自身的依赖（通过 `noop` 链）。新的 `NativeSolver` 更加健壮，能精确地检测到这个拓扑循环并按设计抛出 `ValueError`。
4.  **缓存缺失**：错误的根源在于，我们还没有实现新架构配套的缓存机制。一个正确的缓存机制应该在第二次迭代时命中，**完全跳过 `solver.resolve()` 步骤**，从而根本性地避免循环检测问题。

### 用户需求

根据我们的分析，需要立即着手实现通用的图结构缓存机制，以完成 `GraphExecutionStrategy` 的重构，并修复因此而暴露的性能基准测试问题。

### 评论

这是整个“模板-实例分离”重构的收官之战。之前的破坏性变更为我们奠定了坚实的基础，现在是时候收获成果了。实现这个通用缓存，意味着 Cascade 的 TCO 能力将不再是一个“特例”，而是成为一个适用于所有结构稳定图的普适性“一等公民”，这完美地诠释了 Hashlife 模型的架构思想。

### 目标

1.  修改 `GraphExecutionStrategy`，移除旧的、基于 `_is_simple_task` 和 `_task_templates` 的特殊 TCO 缓存逻辑。
2.  引入一个新的缓存机制 `_plan_cache`，该缓存使用 `ShallowHasher` 生成的结构哈希作为 Key。
3.  `_plan_cache` 的 Value 将是一个元组，包含编译好的 `(Graph, ExecutionPlan, canonical_target_node)`。
4.  在 `execute` 循环中实现缓存的命中/未命中逻辑：
    *   **命中**：直接复用缓存的 `Graph` 和 `Plan`，仅通过 `build_graph` 提取新的 `data_tuple`，然后执行。
    *   **未命中**：执行完整的图构建和求解，然后将结果存入缓存。

### 基本原理

我们将用一个基于内容寻址（结构哈希）的通用缓存，来取代之前基于特定模式（简单任务）的缓存。`ShallowHasher` 能为任何 `LazyResult` 树生成一个稳定的、代表其拓扑结构的哈希值。我们将这个哈希值作为 Key，将被求解器“编译”完成的 `Graph` 模板和 `ExecutionPlan` 作为 Value 存入 `_plan_cache`。

在 TCO 循环的后续迭代中，即使 `LazyResult` 实例因参数变化而不同，但其拓扑结构不变，因此会产生相同的结构哈希，从而命中缓存。这将使 `Engine` 完全跳过昂贵的 `solver.resolve()` 步骤，不仅解决了循环检测问题，还实现了对任意复杂递归的 O(1) 零开销执行。

### 标签

#intent/refine #flow/ready #priority/high
#comp/engine #comp/graph #concept/state
#scope/core
#ai/instruct
#task/domain/engine #task/object/structural-cache #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 重构 `GraphExecutionStrategy`

我们将使用 `write_file` 一次性更新 `strategies.py` 文件。新的实现将彻底移除旧的 TCO 逻辑，并替换为通用的、基于结构哈希的计划缓存。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Protocol, Tuple, List

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.graph.hashing import ShallowHasher
from cascade.spec.protocols import Solver, StateBackend, ExecutionPlan
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine
from cascade.runtime.resource_manager import ResourceManager


class ExecutionStrategy(Protocol):
    """
    Protocol defining a strategy for executing a workflow target.
    """

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any: ...


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph and running a TCO loop.
    This is the standard execution mode for Cascade.
    """

    def __init__(
        self,
        solver: Solver,
        node_processor: NodeProcessor,
        resource_container: ResourceContainer,
        constraint_manager: ConstraintManager,
        bus: MessageBus,
        wakeup_event: asyncio.Event,
    ):
        self.solver = solver
        self.node_processor = node_processor
        self.resource_container = resource_container
        self.constraint_manager = constraint_manager
        self.bus = bus
        self.wakeup_event = wakeup_event
        # Universal structural cache
        self.hasher = ShallowHasher()
        self._plan_cache: Dict[str, Tuple[Graph, ExecutionPlan, Node]] = {}

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

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                struct_hash = self.hasher.hash(current_target)

                if struct_hash in self._plan_cache:
                    # CACHE HIT: Reuse plan, only extract new data
                    graph, plan, canonical_target_node = self._plan_cache[struct_hash]
                    _, data_tuple, instance_map = build_graph(current_target)
                    # Align instance map to point to the canonical node from the cached graph
                    instance_map[current_target._uuid] = canonical_target_node
                else:
                    # CACHE MISS: Build graph and resolve plan for the first time
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    canonical_target_node = instance_map[current_target._uuid]
                    # Store the compiled template and plan in the cache
                    self._plan_cache[struct_hash] = (graph, plan, canonical_target_node)

                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 3. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,
                    plan,
                    instance_map,
                )

            # 4. Check for Tail Call (LazyResult)
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        data_tuple: Tuple[Any, ...],
        plan: Any,
        instance_map: Dict[str, Node],
    ) -> Any:
        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(graph, target_node.id, instance_map)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    skip_reason = flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        state_backend.mark_skipped(node.id, skip_reason)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.id in blocked_nodes:
                            blocked_nodes.remove(node.id)
                    else:
                        deferred_this_pass.append(node)
                        if node.id not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.id)

                if executable_this_pass:
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph and data
                        sub_graph, sub_data, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            data_tuple=sub_data,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            data_tuple,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                            instance_map,
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
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        # Use the mapped canonical node ID to check for the final result
        if not state_backend.has_result(target_node.id):
            # For debugging, check if the instance was skipped
            if skip_reason := state_backend.get_skip_reason(target_node.id):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target_node.id)


class VMExecutionStrategy:
    """
    Executes tasks by compiling them into a Blueprint and running them on a Virtual Machine.
    """

    def __init__(
        self,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        wakeup_event: asyncio.Event,
    ):
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.wakeup_event = wakeup_event

    async def execute(
        self,
        target: Any,
        run_id: str,
        params: Dict[str, Any],
        state_backend: StateBackend,
        run_stack: ExitStack,
        active_resources: Dict[str, Any],
    ) -> Any:
        # 1. Compile in template mode
        builder = BlueprintBuilder()
        blueprint = builder.build(target, template=True)

        # 2. Extract Initial Arguments
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)

        # 3. Execute
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self.wakeup_event,
        )
        return await vm.execute(
            blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs
        )
~~~~~

### 下一步建议

我们已经完成了核心执行策略的重构。现在最关键的一步是验证我们的修改是否正确。

1.  **运行基准测试**：请重新运行 `python observatory/benchmarks/tco_performance.py`。我们期望 `[2] Running Heavy Un-optimized Path` 现在能够成功完成，并且其性能应该远高于之前的（如果能运行的话）JIT 模式，接近于 `simple_countdown` 的水平。
2.  **创建 COMMIT 计划**：一旦测试通过，我们就可以将这个逻辑上完整的工作单元提交到版本控制中。如果你同意，我将为你生成一个包含 `git add` 和 `git commit` 的 `[COMMIT]` 计划。

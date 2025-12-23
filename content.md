好的，我们现在开始执行 **1.3 阶段：适配 `GraphExecutionStrategy`（仅为正确性）**。

**1.3 阶段核心任务分析**

这一步的目标是简化执行引擎，使其完全适配我们在 1.1 和 1.2 中建立的“类 Git”图模型。为了确保“正确性锁定”，我们将：

1.  **彻底移除旧的缓存优化逻辑**: 移除 `_graph_cache` 和 `_task_templates`。这些优化是基于旧的不稳定哈希建立的，现在已不再适用且会增加复杂性。
2.  **强制执行“构建-求解-运行”流水线**: 每一轮 TCO 循环都完整地调用 `build_graph` 和 `solver.resolve`。
3.  **利用 `InstanceMap` 进行根节点定位**: 在 `_execute_graph` 中，始终通过 `instance_map` 将当前的 `target._uuid` 映射到规范化的 `Node` 结构上。
4.  **建立性能基准**: 这是一个逻辑上绝对正确但尚未优化的版本。它将作为我们进入第二阶段（性能飞跃）前的坚实底座。

我将生成一个计划来“净化”执行策略。

## [WIP] refactor(engine): Simplify GraphExecutionStrategy for correctness and Git-model alignment

### 用户需求
完成路线图 1.3 节。重构 `GraphExecutionStrategy` 以完全适配新的 Merkle 哈希图模型。移除所有旧的、不稳定的缓存逻辑，建立一个逻辑正确、结构清晰的执行基线。

### 评论
我们正在执行“先上锁，再加速”策略中的“上锁”环节。通过移除复杂的 JIT 快路径逻辑，我们将引擎回退到一个最纯粹的状态：每一轮迭代都从零构建图并求解计划。虽然这在短期内会降低性能（正如 `tco_performance.py` 所反映的），但它确保了系统对于任何复杂、深层递归图的处理都是逻辑严密的。

一旦这个基线稳定并通过所有测试，我们将在第二阶段利用新的、稳定的 `Node.id` 重新引入更强大的全局缓存。

### 目标
1.  **清理 `GraphExecutionStrategy` 状态**: 从构造函数中移除 `_graph_cache` 和 `_task_templates`。
2.  **简化 `execute` 循环**: 移除关于 `is_fast_path` 的所有判断逻辑。
3.  **标准化构建流程**: 确保每次迭代都获取最新的 `graph`, `data_tuple`, 和 `instance_map`。
4.  **验证正确性**: 确保此改动不破坏现有的 217 个测试及性能测试的运行能力。

### 基本原理
根据《路线图 v3.2》，1.3 阶段的任务是“暂时接受性能下降以换取逻辑上的绝对正确”。通过移除那些依赖旧 ID 模型的缓存分片，我们消除了系统中最后一块可能导致非预期行为的“黑盒”。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #concept/executor #scope/core
#ai/instruct
#task/domain/runtime #task/object/execution-strategy #task/action/refactor
#task/state/continue #task/status/active

---

### Script

#### Acts 1: Simplify `GraphExecutionStrategy`

我们将重写 `strategies.py`，移除所有缓存逻辑，并简化 TCO 执行循环。

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
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


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
    Standard execution mode for Cascade, aligned with the Git-like structural model.
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
        # Note: All caching logic removed in Phase 1.3 for correctness-first baseline.

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
                # 1. Build & Resolve
                # In Phase 1.3, we build and solve every time to ensure absolute correctness.
                graph, data_tuple, instance_map = build_graph(current_target)
                plan = self.solver.resolve(graph)

                # 2. Setup Resources
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
                # State Garbage Collection
                if hasattr(state_backend, "clear"):
                    state_backend.clear()
                # Yield control to event loop
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
        # Map the instance to its canonical structural node
        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(graph, target_node.id, instance_map)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    # Param nodes are virtual and handled by resolvers
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
                    # Recursive runner for map nodes
                    async def sub_graph_runner(sub_target, sub_params, parent_state):
                        sub_graph, sub_data, sub_instance_map = build_graph(sub_target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            sub_target,
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
                        flow_manager.register_result(node.id, res, state_backend)

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        # Check for final result on the structural node
        if not state_backend.has_result(target_node.id):
            if skip_reason := state_backend.get_skip_reason(target_node.id):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name if hasattr(target, "task") else "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target, 'task') else 'unknown'}' produced no result."
            )

        return state_backend.get_result(target_node.id)
~~~~~

### 下一步建议

我们已经完成了路线图第一阶段的所有代码工作。
1.  **最后一次“正确性”验证**: 运行 `pytest`。这 217+ 个测试必须全部绿灯。
2.  **建立性能基线**: 运行 `python observatory/benchmarks/tco_performance.py`。
    *   **预期**: 所有的 Countdown 任务都应成功完成，无任何错误。
    *   **重要观察**: 记录 `heavy_complex_countdown` 的执行时间。它现在会比之前慢（因为它正在进行真正的“全量 Merkle 构建 + 求解”），但这正是我们 2.1 节要优化的“靶点”。
3.  **结项提交**: 如果一切符合预期，我将生成一个针对 1.2 和 1.3 的 `[COMMIT]` 计划，标志着“管道建设阶段”的圆满结束。

请确认是否运行测试。

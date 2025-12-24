好的，我们开始执行。

这是实现性能突破的关键一步。我将生成一个计划，该计划将移除引擎中的保守检查，并启用为“重型路径”准备的动态参数修补机制。

## [WIP] feat(engine): 启用结构化 JIT 以优化 TCO 重型路径

### 用户需求
根据新的架构演进建议书，实施阶段一的核心改造：启用 JIT 缓存与动态参数修补。

### 评论
这次修改是整个性能优化战役的“决胜点”。通过移除 `_are_args_simple` 这个瓶颈，并正确地将动态参数“注入”到缓存的执行计划中，我们将能够释放 Cascade 引擎在复杂递归场景下的全部潜力。

### 目标
1.  移除 `GraphExecutionStrategy` 中阻止“重型路径”进入 JIT 快速通道的 `_are_args_simple` 检查。
2.  删除不再使用的 `_are_args_simple` 方法。
3.  在 JIT 快速通道中，捕获当前递归调用的动态参数 (`current_target.args` 和 `kwargs`)。
4.  将这些动态参数作为 `input_overrides` 传递给 `_execute_hot_node` 执行器，以实现动态修补。

### 基本原理
我们信任由静态分析 (`_tco_cycle_id`) 建立的“计算蓝图”的稳定性。`_are_args_simple` 是一个过于保守的卫兵，现在我们将其移除，允许所有结构相同的递归调用共享同一个缓存的执行计划。当一个新的递归调用（携带新的动态参数）进入快速通道时，我们将其参数打包成 `input_overrides`。`_execute_hot_node` 内部的 `ArgumentResolver` 已经具备处理这种覆盖的能力，它会高效地从状态后端解析这些新参数的值，并将其注入到缓存的计算图中执行。这套机制——“信任蓝图，修补数据”——是结构化 JIT 的核心。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/state #scope/core #ai/instruct #task/domain/performance #task/object/tco-heavy-path #task/action/optimization #task/state/continue

---

### Script

#### Acts 1: 重构 `GraphExecutionStrategy` 以启用 JIT 和动态修补

我们将使用 `write_file` 整体重写 `graph.py`，以确保结构性修改的原子性和正确性。新的实现将移除 `_are_args_simple` 检查及其定义，并在快速通道中实现动态参数的捕获与传递。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
import asyncio
import inspect
from contextlib import ExitStack
from typing import Any, Dict, List, Set

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked, StaticAnalysisWarning
from cascade.runtime.constraints.manager import ConstraintManager


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph and running a TCO loop.
    This is the standard execution mode for Cascade.

    Refactored for v3.2 architecture:
    - Strictly relies on build_graph returning (Graph, DataTuple, InstanceMap).
    - Uses InstanceMap to locate the target node within the structural graph.
    - Caching is intentionally disabled in this phase to ensure correctness.
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

        # Tracks warnings issued in this run to avoid duplicates
        self._issued_warnings: Set[str] = set()

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        # We store indices instead of Node objects to allow plan reuse across
        # different graph instances that share the same structure (template).
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Zero-Overhead TCO Cache
        # Maps tco_cycle_id to (Graph, IndexedPlan, root_node_id)
        # Used to bypass build_graph for structurally stable recursive calls
        self._cycle_cache: Dict[str, Any] = {}

        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        """
        Converts a Plan (List[List[Node]]) into an IndexedPlan (List[List[int]]).
        The index corresponds to the node's position in graph.nodes.
        """
        # Create a fast lookup for node indices
        id_to_idx = {node.structural_id: i for i, node in enumerate(graph.nodes)}
        indexed_plan = []
        for stage in plan:
            # Map each node in the stage to its index in the graph
            indexed_stage = [id_to_idx[node.structural_id] for node in stage]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        """
        Converts an IndexedPlan back into a Plan using the nodes from the current graph.
        """
        plan = []
        for stage_indices in indexed_plan:
            # Map indices back to Node objects from the current graph instance
            stage_nodes = [graph.nodes[idx] for idx in stage_indices]
            plan.append(stage_nodes)
        return plan

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
            # Check for Zero-Overhead TCO Fast Path
            # Use getattr safely as MappedLazyResult uses .factory instead of .task
            target_task = getattr(current_target, "task", None)
            cycle_id = (
                getattr(target_task, "_tco_cycle_id", None) if target_task else None
            )
            fast_path_data = None

            if cycle_id and cycle_id in self._cycle_cache:
                fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)
                else:
                    # SLOW PATH: Build Graph
                    # STATE GC (Asynchronous)
                    if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                        state_backend.clear
                    ):
                        await state_backend.clear()
                    # Yield control
                    await asyncio.sleep(0)

                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    # Post-build analysis checks
                    for node in graph.nodes:
                        if (
                            node.warns_dynamic_recursion
                            and node.name not in self._issued_warnings
                        ):
                            self.bus.publish(
                                StaticAnalysisWarning(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    warning_code="CS-W001",
                                    message=(
                                        f"Task '{node.name}' uses a dynamic recursion pattern (calling other "
                                        "tasks in its arguments) which disables TCO optimizations, "
                                        "leading to significant performance degradation."
                                    ),
                                )
                            )
                            self._issued_warnings.add(node.name)

                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.structural_id

                    # 2. Resolve Plan
                    if cache_key in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[cache_key]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[cache_key] = indexed_plan

                    # Cache for Future TCO Fast Path
                    # Only scan and cache if we haven't already indexed this cycle
                    if cycle_id and cycle_id not in self._cycle_cache:
                        # Pre-scan resources and store them in the cycle cache
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (
                            graph,
                            indexed_plan,
                            target_node.structural_id,
                            req_res,
                        )

                # 3. Setup Resources (mixed scope)
                if fast_path_data:
                    required_resources = fast_path_data[3]
                else:
                    required_resources = self.resource_container.scan(graph)

                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Execute Graph
                # CHECK FOR HOT-LOOP BYPASS
                # If it's a fast path and it's a simple single-node plan, bypass the orchestrator
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    # Prepare Input Overrides for dynamic patching
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)

                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    # Prepare overrides for the root node, even in the slow path
                    root_input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        root_input_overrides[str(i)] = arg
                    root_input_overrides.update(current_target.kwargs)

                    result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        root_input_overrides,
                    )

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            else:
                return result

    async def _execute_hot_node(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        A stripped-down version of NodeProcessor.process specifically for hot TCO loops.
        Bypasses event bus, flow manager, and multiple resolvers for maximum performance.
        """
        # 1. Resolve Arguments (Minimal path)
        # We reuse the node_processor's resolver but bypass the process() wrapper
        # Resolver is now ASYNC
        args, kwargs = await self.node_processor.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )

        # 2. Direct Execution (Skip NodeProcessor ceremony)
        result = await self.node_processor.executor.execute(node, args, kwargs)

        # 3. Minimal State Update (Async)
        await state_backend.put_result(node.structural_id, result)
        return result

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
        instance_map: Dict[str, Node],
        root_input_overrides: Dict[str, Any] = None,
    ) -> Any:
        # Locate the canonical node for the current target instance
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]

        flow_manager = FlowManager(graph, target_node.structural_id, instance_map)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    # ASYNC CHECK
                    skip_reason = await flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        await state_backend.mark_skipped(
                            node.structural_id, skip_reason
                        )
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.structural_id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.structural_id in blocked_nodes:
                            blocked_nodes.remove(node.structural_id)
                    else:
                        deferred_this_pass.append(node)
                        if node.structural_id not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.structural_id)

                if executable_this_pass:
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph
                        sub_graph, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )

                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.structural_id == target_node.structural_id
                            else None
                        )
                        tasks_to_run.append(
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
                            )
                        )

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        await state_backend.put_result(node.structural_id, res)
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        # Use the mapped canonical node ID to check for the final result
        if not await state_backend.has_result(target_node.structural_id):
            # For debugging, check if the instance was skipped
            if skip_reason := await state_backend.get_skip_reason(
                target_node.structural_id
            ):
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

        return await state_backend.get_result(target_node.structural_id)
~~~~~

### 下一步建议
我们已经完成了核心的引擎改造。现在必须进行验证。

1.  **性能验证**: 请立即重新运行 `observatory/benchmarks/tco_performance.py` 性能基准测试。**我们期望 `heavy_complex_countdown` 的性能（TPS）能从 ~1,400 跃升至与 `simple_countdown` (~100k) 相近的水平。**
2.  **正确性验证**: 在确认性能达标后，我们将进入路线图的**阶段二**：创建一个专门的回归测试来锁定这一行为，确保未来的重构不会意外地破坏这个来之不易的性能优化。

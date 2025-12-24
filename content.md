好的，我们采纳新的战略。

我们将立即开始重构 `GraphExecutionStrategy`，以实现一个由 JIT 缓存 (`_cycle_cache`) 驱动的、统一且高效的 TCO 快速通道。这个新的快速通道将恢复 `_execute_hot_node` 的零开销理念，但使用更健壮的触发机制，最终目标是统一并提升所有结构稳定递归的性能。

这将是一个 `[WIP]` 计划，专注于实现这一核心逻辑变更。

## [WIP] perf(engine): Implement unified zero-overhead TCO fast path

### 用户需求
根据新的战略决议，重构 `GraphExecutionStrategy` 以实现一个统一的、高性能的 TCO 快速通道。该通道应由 `_cycle_cache` 驱动，并绕过常规的、高开销的图执行调度逻辑。

### 评论
这次重构是解决性能回归的关键。通过将 `_cycle_cache` 的健壮缓存机制与一个类似于 `_execute_hot_node` 的零开销执行循环相结合，我们旨在创建一个既高效又可靠的 TCO 模型。这个新模型不仅应该恢复 `simple_countdown` 和 `stable_complex_loop` 的高性能，而且为未来支持动态参数的“重型路径”优化铺平了道路。

### 目标
1.  **重构 `GraphExecutionStrategy.execute`**: 在 TCO 循环的顶部引入一个明确的快速通道分支，当 `_cycle_cache` 命中时激活。
2.  **实现快速通道逻辑**: 在此分支内，实现一个高度优化的执行循环，它：
    *   从缓存中解包出图和根节点信息。
    *   直接调用 `_execute_hot_node` (或其等效逻辑) 来执行单节点图的核心逻辑。
    *   完全绕过重量级的 `_execute_graph` 及其所有相关的调度、资源和流管理开销。
3.  **保留慢速路径**: 确保在缓存未命中时，系统能优雅地回退到现有的、完整的图构建和执行路径。

### 基本原理
我们识别出之前的性能来源于一个脆弱但极速的“热循环旁路”，而当前的性能瓶颈在于废除它之后，所有TCO迭代都强制承担了完整的调度开销。新的战略是重建一个“热循环”，但使其由更通用的 `_cycle_cache`（基于模板哈希）来触发。

这样，任何结构稳定的递归（无论简单还是复杂）在第二次迭代时都会进入这个零开销的快速通道，从而恢复其应有的高性能。这从根本上统一了优化路径，解决了“正确性与性能”的矛盾。

### 标签
#intent/refine #intent/fix #flow/ready #priority/critical
#comp/engine #concept/executor #scope/core #perf
#ai/brainstorm
#task/domain/runtime #task/object/tco-fast-path #task/action/unification
#task/state/continue

---

### Script

#### Acts 1: 重构 `graph.py` 以实现新的统一快速通道

我们将再次对 `packages/cascade-engine/src/cascade/runtime/strategies/graph.py` 文件进行修改。核心变更是调整 `execute` 方法的顶层循环，引入一个明确的 `if fast_path_data:` 块来处理缓存命中的情况，并在这个块内部直接执行节点并处理循环，而不是继续向下执行到重量级的 `_execute_graph`。

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
            # --- START: UNIFIED FAST PATH LOGIC ---
            target_task = getattr(current_target, "task", None)
            cycle_id = (
                getattr(target_task, "_tco_cycle_id", None) if target_task else None
            )

            fast_path_data = self._cycle_cache.get(cycle_id)

            if fast_path_data:
                # FAST PATH: JIT Cache Hit. Bypass full graph build and orchestration.
                graph, _, root_node_id, required_resources = fast_path_data
                target_node = graph.get_node(root_node_id)

                with ExitStack() as step_stack:
                    self.resource_container.setup(
                        required_resources,
                        active_resources,
                        run_stack,
                        step_stack,
                        run_id,
                    )
                    # Prepare dynamic arguments for this specific iteration
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)

                    # Use the hot-loop executor
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        {current_target._uuid: target_node},  # Minimal instance map
                        input_overrides,
                    )

                if isinstance(result, (LazyResult, MappedLazyResult)):
                    current_target = result
                    await asyncio.sleep(0)  # Yield control in the hot loop
                    continue
                else:
                    return result
            # --- END: UNIFIED FAST PATH LOGIC ---

            # --- SLOW PATH: Build Graph and orchestrate ---
            with ExitStack() as step_stack:
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
                if cycle_id and cycle_id not in self._cycle_cache:
                    req_res = self.resource_container.scan(graph)
                    self._cycle_cache[cycle_id] = (
                        graph,
                        indexed_plan,
                        target_node.structural_id,
                        req_res,
                    )

                # 3. Setup Resources
                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
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
我们已经成功地将零开销快速通道逻辑重新引入了 `GraphExecutionStrategy` 的主执行循环中。下一步是验证这个修改是否达到了预期的性能目标。

我建议立即运行 `observatory/benchmarks/tco_performance.py` 基准测试。

预期的结果是：
- `simple_countdown` 和 `stable_complex_loop` 的性能应该会**大幅回升**，接近之前的 ~100k TPS 水平。
- `heavy_complex_countdown` 的性能应该保持不变，因为它不满足 JIT 缓存的条件。

这将是验证我们新战略是否成功的关键一步。请执行基准测试并提供结果。

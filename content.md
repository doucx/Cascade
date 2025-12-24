好的，我们开始执行“第一阶段：修复引擎内核”。

我将生成一个计划，该计划将系统性地修复 `cascade-engine` 内部因“StateBackend 异步化”重构而遗漏的所有 `await` 调用。这个计划严格限制在引擎核心代码，不涉及测试套件的修改。

## [WIP] fix(engine): 在运行时内核中为异步 StateBackend 补全 await

### 错误分析
在将 `StateBackend` 协议迁移到 `async def` 后，引擎内部的多个关键组件（`FlowManager`, `GraphExecutionStrategy` 等）未能相应地更新其调用方式。这导致了 `RuntimeWarning: coroutine ... was never awaited` 警告，并引发了严重的逻辑错误：
1.  **逻辑判断失效**: `if state_backend.has_result(...)` 这样的代码中，协程对象本身总是 `True`，导致 `if` 条件判断永远失败。
2.  **控制流破坏**: 同样，`if flow_manager.should_skip(...)` 的逻辑也被破坏，使得 `run_if` 和 `Router` 剪枝等核心功能完全失效。

这些是导致大规模测试失败的根本原因。

### 用户需求
执行“第一阶段”修复，即只修正 `cascade-engine` 内核代码，为所有对 `StateBackend` 及其相关异步方法的调用添加 `await` 关键字。

### 评论
这是一个精确的外科手术式修复。我们的目标是让引擎的内部逻辑与其依赖的异步协议（`StateBackend`）恢复一致。完成此步骤后，引擎内核将处于一个逻辑上正确的状态，为第二阶段修复测试套le套件奠定基础。

### 目标
1.  审查 `runtime/flow.py` 并为其所有 `state_backend` 调用添加 `await`。
2.  审查 `runtime/processor.py` 并为其所有 `state_backend` 和 `resolver` 调用添加 `await`。
3.  审查 `runtime/strategies/graph.py`，确保所有对 `flow_manager` 和 `state_backend` 的调用都已正确 `await`。

### 基本原理
通过全面审计并修复所有遗漏的 `await`，我们将完成“StateBackend 异步化”重构的后半部分工作。这将恢复引擎的控制流正确性，并消除所有相关的 `RuntimeWarning`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/state #scope/core #ai/instruct #task/domain/core #task/object/state-backend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 FlowManager

`FlowManager` 中的所有方法都依赖 `StateBackend`，因此它们自身也必须是异步的，并且所有内部调用都必须被 `await`。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, Edge, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(
        self, graph: Graph, target_node_id: str, instance_map: Dict[str, Node]
    ):
        self.graph = graph
        self.target_node_id = target_node_id
        self.instance_map = instance_map

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.structural_id].append(edge)
            self.downstream_demand[edge.source.structural_id] += 1

            if edge.router:
                selector_node = self._get_node_from_instance(edge.router.selector)
                if selector_node:
                    self.routers_by_selector[selector_node.structural_id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_node = self._get_node_from_instance(route_result)
                    if route_node:
                        self.route_source_map[edge.target.structural_id][
                            route_node.structural_id
                        ] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_id] += 1

    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        elif isinstance(instance, Param):
            # Find the node that represents this param
            for node in self.graph.nodes:
                if node.param_spec and node.param_spec.name == instance.name:
                    return node
        return None

    async def register_result(
        self, node_id: str, result: Any, state_backend: StateBackend
    ):
        """
        Notifies FlowManager of a task completion.
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                await self._process_router_decision(
                    edge_with_router, result, state_backend
                )

    async def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value

        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_node = self._get_node_from_instance(route_lazy_result)
                if not branch_root_node:
                    continue  # Should not happen in a well-formed graph
                branch_root_id = branch_root_node.structural_id
                # This branch is NOT selected.
                # We decrement its demand. If it drops to 0, it gets pruned.
                await self._decrement_demand_and_prune(branch_root_id, state_backend)

    async def _decrement_demand_and_prune(
        self, node_id: str, state_backend: StateBackend
    ):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned
        and recursively processes its upstreams.
        """
        # If already skipped/pruned, no need to do anything further
        if await state_backend.get_skip_reason(node_id):
            return

        self.downstream_demand[node_id] -= 1

        if self.downstream_demand[node_id] <= 0:
            await state_backend.mark_skipped(node_id, "Pruned")

            # Recursively reduce demand for inputs of the pruned node
            for edge in self.in_edges[node_id]:
                # Special case: If the edge is from a Router, do we prune the Router selector?
                # No, the selector might be used by other branches.
                # Standard dependency logic applies: reduce demand on source.
                await self._decrement_demand_and_prune(
                    edge.source.structural_id, state_backend
                )

    async def should_skip(
        self, node: Node, state_backend: StateBackend
    ) -> Optional[str]:
        """
        Determines if a node should be skipped based on the current state.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Check if already skipped (e.g., by router pruning)
        if reason := await state_backend.get_skip_reason(node.structural_id):
            return reason

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.structural_id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not await state_backend.has_result(edge.source.structural_id):
                    if await state_backend.get_skip_reason(edge.source.structural_id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"

                condition_result = await state_backend.get_result(
                    edge.source.structural_id
                )
                if not condition_result:
                    return "ConditionFalse"

            # New explicit check for sequence abortion
            elif edge.edge_type == EdgeType.SEQUENCE:
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Sequence"

        # 3. Upstream Skip Propagation
        active_route_key = None
        router_edge = next(
            (e for e in self.in_edges[node.structural_id] if e.router), None
        )
        if router_edge:
            selector_node = self._get_node_from_instance(router_edge.router.selector)
            if selector_node:
                selector_id = selector_node.structural_id
                if await state_backend.has_result(selector_id):
                    active_route_key = await state_backend.get_result(selector_id)

        for edge in self.in_edges[node.structural_id]:
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                if active_route_key is not None:
                    edge_key = self.route_source_map[node.structural_id].get(
                        edge.source.structural_id
                    )
                    if edge_key != active_route_key:
                        continue

                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Route"

            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    # Check for data penetration possibility (for pipelines)
                    can_penetrate = False
                    # Look for inputs to the skipped node (edge.source)
                    for upstream_edge in self.in_edges[edge.source.structural_id]:
                        # If the skipped node has a DATA input, and that input has a result...
                        if (
                            upstream_edge.edge_type == EdgeType.DATA
                            and await state_backend.has_result(
                                upstream_edge.source.structural_id
                            )
                        ):
                            can_penetrate = True
                            break

                    if not can_penetrate:
                        return "UpstreamSkipped_Data"
                    # If it can penetrate, we don't return a skip reason.
                    # We let the node proceed to execution, where ArgumentResolver will handle it.

            elif edge.edge_type == EdgeType.SEQUENCE:
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Sequence"

        return None
~~~~~

#### Acts 2: 修复 NodeProcessor

`_resolve_inputs_for_cache` 方法需要 `await` 对 `state_backend` 的调用。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
    async def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        # TODO: This needs to be smarter for caching.
        # It should probably include data from input_bindings too?
        # For now, keeping legacy behavior (edge results only).
        inputs = {}
        incoming_edges = [
            edge
            for edge in graph.edges
            if edge.target.structural_id == node.structural_id
        ]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if await state_backend.has_result(edge.source.structural_id):
                inputs[edge.arg_name] = await state_backend.get_result(
                    edge.source.structural_id
                )
        return inputs
~~~~~
~~~~~python
    async def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        # TODO: This needs to be smarter for caching.
        # It should probably include data from input_bindings too?
        # For now, keeping legacy behavior (edge results only).
        inputs = {}
        incoming_edges = [
            edge
            for edge in graph.edges
            if edge.target.structural_id == node.structural_id
        ]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if await state_backend.has_result(edge.source.structural_id):
                inputs[edge.arg_name] = await state_backend.get_result(
                    edge.source.structural_id
                )
        return inputs
~~~~~

#### Acts 3: 修复 GraphExecutionStrategy

这是最关键的修复。所有对 `flow_manager` 和 `state_backend` 的调用都必须被 `await`，尤其是在 `if` 条件判断中。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
import asyncio
import inspect
from contextlib import ExitStack
from typing import Any, Dict, List

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
from cascade.runtime.events import TaskSkipped, TaskBlocked
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
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)

                    # Prepare Input Overrides
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)
                else:
                    # SLOW PATH: Build Graph
                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )
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
                    result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        input_overrides,
                    )

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC (Asynchronous)
                if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                    state_backend.clear
                ):
                    await state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    def _are_args_simple(self, lazy_result: Any) -> bool:
        """
        Checks if the LazyResult arguments contain any nested LazyResults.
        """
        # Handle both LazyResult (args/kwargs) and MappedLazyResult (mapping_kwargs)
        args = getattr(lazy_result, "args", [])
        kwargs = getattr(lazy_result, "kwargs", {})
        if hasattr(lazy_result, "mapping_kwargs"):
            kwargs = lazy_result.mapping_kwargs

        for arg in args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for val in kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                return False
        return True

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
我们已经完成了对引擎内核的系统性修复。现在，`cascade-engine` 内部的逻辑与 `StateBackend` 的异步契约已经完全对齐。

然而，**测试套件仍然是失败的**，因为它们还没有被更新以适应这些异步变化（例如，将测试函数标记为 `async def` 并使用 `await` 调用 `engine.run`）。

下一步是执行“**第二阶段：修复测试套件**”，这将使我们的 CI 恢复绿灯，并最终完成这次重构。

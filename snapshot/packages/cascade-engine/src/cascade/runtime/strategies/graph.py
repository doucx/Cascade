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

        # JIT Compilation Cache for execution plans
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Zero-Overhead TCO Cache for full graph/plan structures
        self._cycle_cache: Dict[str, Any] = {}

        # Persistent registry for node object identity
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        """Converts a Plan (List[List[Node]]) into an IndexedPlan (List[List[int]])."""
        id_to_idx = {node.structural_id: i for i, node in enumerate(graph.nodes)}
        return [
            [id_to_idx[node.structural_id] for node in stage] for stage in plan
        ]

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        """Converts an IndexedPlan back into a Plan using nodes from the current graph."""
        return [[graph.nodes[idx] for idx in stage_indices] for stage_indices in indexed_plan]

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
            target_task = getattr(current_target, "task", None)
            cycle_id = getattr(target_task, "_tco_cycle_id", None) if target_task else None
            fast_path_data = self._cycle_cache.get(cycle_id) if cycle_id else None

            with ExitStack() as step_stack:
                if fast_path_data:
                    # FAST PATH: Reuse cached Graph & Plan
                    graph, indexed_plan, root_node_id, req_res = fast_path_data
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)

                    # Prepare Input Overrides for the root node of the recursion
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)

                    self.resource_container.setup(
                        req_res, active_resources, run_stack, step_stack, run_id
                    )

                    result = await self._execute_hot_plan(
                        plan,
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    # SLOW PATH: Build Graph from scratch
                    if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                        state_backend.clear
                    ):
                        await state_backend.clear()
                    await asyncio.sleep(0)

                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    # Post-build analysis and warnings
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
                                    message=f"Task '{node.name}' uses a dynamic recursion pattern.",
                                )
                            )
                            self._issued_warnings.add(node.name)

                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.structural_id

                    # Resolve Plan (with caching)
                    if cache_key in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[cache_key]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[cache_key] = indexed_plan

                    # Cache for future TCO cycles
                    if cycle_id and cycle_id not in self._cycle_cache:
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (
                            graph,
                            indexed_plan,
                            target_node.structural_id,
                            req_res,
                        )

                    # Setup resources
                    required_resources = self.resource_container.scan(graph)
                    self.resource_container.setup(
                        required_resources, active_resources, run_stack, step_stack, run_id
                    )

                    # Execute graph using the full orchestrator
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

            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
            else:
                return result

    async def _execute_hot_plan(
        self,
        plan: List[List[Node]],
        root_node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        root_input_overrides: Dict[str, Any],
    ) -> Any:
        """
        A highly optimized executor for pre-computed plans in TCO hot loops.
        It bypasses most of the standard orchestration overhead.
        """
        for stage in plan:
            tasks_to_run = []
            for node in stage:
                overrides = (
                    root_input_overrides
                    if node.structural_id == root_node.structural_id
                    else None
                )
                tasks_to_run.append(
                    self._execute_hot_node(
                        node, graph, state_backend, active_resources, params, instance_map, overrides
                    )
                )

            # Await all tasks in the stage concurrently
            if tasks_to_run:
                await asyncio.gather(*tasks_to_run)

        # The final result is the result of the root_node of the TCO cycle
        return await state_backend.get_result(root_node.structural_id)

    async def _execute_hot_node(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> None:
        """
        Processes a single node in a hot path, resolving its arguments and executing it.
        The result is stored in the state_backend.
        """
        args, kwargs = await self.node_processor.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )
        result = await self.node_processor.executor.execute(node, args, kwargs)
        await state_backend.put_result(node.structural_id, result)


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

                    skip_reason = await flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        await state_backend.mark_skipped(node.structural_id, skip_reason)
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
                    async def sub_graph_runner(target, sub_params, parent_state):
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

        if not await state_backend.has_result(target_node.structural_id):
            if skip_reason := await state_backend.get_skip_reason(target_node.structural_id):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )
            raise KeyError(f"Target task '{getattr(target.task, 'name', 'unknown')}' did not produce a result.")

        return await state_backend.get_result(target_node.structural_id)
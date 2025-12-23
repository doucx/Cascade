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
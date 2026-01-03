import asyncio
from contextlib import ExitStack
from typing import Any, Dict, List, Optional, Callable

from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
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
    def __init__(self, value: Any, source_node_id: str):
        self.value = value
        self.source_node_id = source_node_id


class GraphExecutionStrategy:
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
        self.blueprint_hasher = BlueprintHasher()

        self._template_plan_cache: Dict[str, List[List[int]]] = {}
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        id_to_idx = {
            node.current_node_instance_hash: i for i, node in enumerate(graph.nodes)
        }
        indexed_plan = []
        for stage in plan:
            indexed_stage = [
                id_to_idx[node.current_node_instance_hash] for node in stage
            ]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        plan = []
        for stage_indices in indexed_plan:
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

            result = graph_result.value

            if isinstance(result, Jump):
                source_node_id = graph_result.source_node_id
                jump_edge = next(
                    (
                        e
                        for e in graph.edges
                        if e.source.current_node_instance_hash == source_node_id
                        and e.edge_type == EdgeType.ITERATIVE_JUMP
                    ),
                    None,
                )

                if not jump_edge or not jump_edge.jump_selector:
                    raise RuntimeError(
                        f"Task returned a Jump signal but has no bound 'select_jump' (Edge not found for {source_node_id})."
                    )

                selector = jump_edge.jump_selector
                next_target = selector.routes.get(result.target_key)

                if next_target is None:
                    return result.data

                current_target = next_target

                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}
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
        plan: Any,
        instance_map: Dict[str, Node],
        executable_registry: Dict[str, Callable],
        root_input_overrides: Optional[Dict[str, Any]] = None,
    ) -> GraphExecutionResult:
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(
            graph, target_node.current_node_instance_hash, instance_map
        )
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    skip_reason = await flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        await state_backend.mark_skipped(
                            node.current_node_instance_hash, skip_reason
                        )
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.current_node_instance_hash,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.current_node_instance_hash in blocked_nodes:
                            blocked_nodes.remove(node.current_node_instance_hash)
                    else:
                        deferred_this_pass.append(node)
                        if node.current_node_instance_hash not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.current_node_instance_hash,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.current_node_instance_hash)

                if executable_this_pass:

                    async def sub_graph_runner(target, sub_params, parent_state):
                        (
                            sub_graph,
                            sub_instance_map,
                            sub_executable_registry,
                        ) = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        result_obj = await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                            executable_registry=sub_executable_registry,
                        )
                        return result_obj.value

                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.current_node_instance_hash
                            == target_node.current_node_instance_hash
                            else None
                        )

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

                        cache_inputs = (
                            await self.node_processor.arg_resolver.resolve_cache_inputs(
                                node, graph, state_backend
                            )
                        )

                        executable = executable_registry[node.current_node_instance_hash]

                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    executable,
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
                        node, coro = tasks_to_run[0]
                        res = await coro
                        await state_backend.put_result(
                            node.current_node_instance_hash, res
                        )
                        if flow_manager:
                            await flow_manager.register_result(
                                node.current_node_instance_hash, res, state_backend
                            )
                    else:
                        nodes_in_pass = [t[0] for t in tasks_to_run]
                        coros = [t[1] for t in tasks_to_run]
                        pass_results = await asyncio.gather(*coros)

                        for node, res in zip(nodes_in_pass, pass_results):
                            await state_backend.put_result(
                                node.current_node_instance_hash, res
                            )
                            if flow_manager:
                                await flow_manager.register_result(
                                    node.current_node_instance_hash, res, state_backend
                                )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not await state_backend.has_result(target_node.current_node_instance_hash):
            if skip_reason := await state_backend.get_skip_reason(
                target_node.current_node_instance_hash
            ):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return GraphExecutionResult(
                        value=None,
                        source_node_id=target_node.current_node_instance_hash,
                    )
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        final_value = await state_backend.get_result(
            target_node.current_node_instance_hash
        )
        return GraphExecutionResult(
            value=final_value, source_node_id=target_node.current_node_instance_hash
        )
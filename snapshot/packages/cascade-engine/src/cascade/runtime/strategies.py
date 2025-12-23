import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Protocol, Tuple, List

from cascade.graph.model import Graph
from cascade.graph.build import build_graph, extract_data
from cascade.graph.hashing import StructuralHasher
from cascade.spec.protocols import Solver, StateBackend
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
from cascade.graph.model import Node


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
        # Cache for structural hashing
        # Key: structural_hash, Value: (Graph, Plan, TargetNodeID)
        self._plan_cache: Dict[Any, Tuple[Graph, Any, str]] = {}
        self.hasher = StructuralHasher()

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task suitable for the Fast Path optimization.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False
        if lr._dependencies:
            return False
        
        # Shallow check for nested lazy objects in args/kwargs
        # We don't recurse deeply to keep this check O(1) in depth
        for arg in lr.args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for v in lr.kwargs.values():
             if isinstance(v, (LazyResult, MappedLazyResult)):
                return False
        
        return True

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
                graph, plan, data_tuple, instance_map = None, None, (), None
                target_node = None
                
                # 1. Structural Hashing & Caching
                
                # OPTIMIZATION: Check for simple recursion (Fast Path)
                # If it's a simple task, we use the Task object identity as the cache key.
                # This avoids tree traversal for hashing.
                is_fast_path = False
                cache_key = None
                
                if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                     is_fast_path = True
                     cache_key = id(current_target.task)
                else:
                     cache_key, _ = self.hasher.hash(current_target)

                if cache_key in self._plan_cache:
                    # CACHE HIT: Reuse Graph and Plan
                    graph, plan, target_node_id = self._plan_cache[cache_key]
                    
                    # Extract ONLY the data tuple using the optimized extractor
                    data_tuple = extract_data(current_target)
                    
                    # Resolve target node from cached graph
                    target_node = next((n for n in graph.nodes if n.id == target_node_id), None)
                    if not target_node:
                         raise RuntimeError(f"Cached target node {target_node_id} not found in graph")
                    
                    # In cached mode, we don't have a valid instance_map for the new LazyResults.
                    instance_map = {} 
                else:
                    # CACHE MISS: Full Build & Solve
                    graph, data_tuple, instance_map = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    target_node = instance_map[current_target._uuid]
                    self._plan_cache[cache_key] = (graph, plan, target_node.id)

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
                    target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,
                    plan,
                    instance_map,
                    target_node,
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
        target_node: Node,
    ) -> Any:
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
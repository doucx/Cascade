import asyncio
from contextlib import ExitStack
from typing import Any, Dict, Protocol, Tuple, List

from cascade.graph.model import Graph
from cascade.graph.build import build_graph
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
        # Cache for structural hashing (slow path)
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}
        # Cache for Zero-Overhead TCO (fast path), keyed by Task object
        self._task_templates: Dict[Any, Tuple[Graph, Any]] = {}

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
            return False

        # Explicit dependencies
        if lr._dependencies:
            return False

        def _has_lazy(obj):
            if isinstance(obj, (LazyResult, MappedLazyResult)):
                return True
            if isinstance(obj, (list, tuple)):
                return any(_has_lazy(x) for x in obj)
            if isinstance(obj, dict):
                return any(_has_lazy(v) for v in obj.values())
            return False

        # Check args and kwargs recursively
        for arg in lr.args:
            if _has_lazy(arg):
                return False

        for v in lr.kwargs.values():
            if _has_lazy(v):
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

        # Optimization state for TCO Fast Path
        last_executed_task = None
        last_tco_cycle_id = None

        while True:
            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                graph = None
                plan = None
                literals = None
                is_fast_path = False

                # --- 1. ZERO-OVERHEAD FAST PATH CHECK ---
                # Check if we are in a recognized TCO loop (A -> B -> ... -> A)
                # Conditions:
                # 1. Target is a LazyResult and "simple" (no complex deps).
                # 2. Target task has been statically analyzed as part of a TCO cycle.
                # 3. We have a compiled template for this task.
                # 4. (Optional but safe) The previous task was also part of a cycle (or we are starting one).
                
                if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                    task_obj = current_target.task
                    cycle_id = getattr(task_obj, "_tco_cycle_id", None)
                    
                    # If we have a cycle match or self-recursion match
                    if (cycle_id and cycle_id == last_tco_cycle_id) or (task_obj == last_executed_task):
                        if task_obj in self._task_templates:
                            is_fast_path = True
                            graph, plan = self._task_templates[task_obj]
                            # Update literals in O(1) without hashing
                            self._update_graph_literals(graph, current_target, {})
                
                if not is_fast_path:
                    # --- 2. SLOW PATH (Hashing & Cache) ---
                    # Get Graph and Plan, using Structural Hash Cache
                    hasher = StructuralHasher()
                    struct_hash, literals = hasher.hash(current_target)

                    if struct_hash in self._graph_cache:
                        # CACHE HIT: Reuse graph and plan
                        # Now supports complex graphs by injecting literals into all nodes
                        graph, plan = self._graph_cache[struct_hash]
                        self._inject_literals(graph, literals)
                    else:
                        # CACHE MISS: Build, solve, and cache
                        graph = build_graph(current_target)
                        plan = self.solver.resolve(graph)
                        self._graph_cache[struct_hash] = (graph, plan)
                        
                        # Populate Task Template Cache if this is a simple node
                        # This "warms up" the fast path for future iterations
                        if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                             self._task_templates[current_target.task] = (graph, plan)

                # Update state for next iteration
                if isinstance(current_target, LazyResult):
                    last_executed_task = current_target.task
                    last_tco_cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
                else:
                    last_executed_task = None
                    last_tco_cycle_id = None

                # 2. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
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
                    plan,
                )

            # Capture the task we just executed BEFORE updating current_target
            if isinstance(current_target, LazyResult):
                last_executed_task = current_target.task
            else:
                last_executed_task = None

            # 4. Check for Tail Call (LazyResult)
                if isinstance(current_target, LazyResult):
                    last_executed_task = current_target.task
                    last_tco_cycle_id = getattr(current_target.task, "_tco_cycle_id", None)
                else:
                    last_executed_task = None
                    last_tco_cycle_id = None

    def _update_graph_literals(self, graph: Graph, target: Any, literals: Dict[str, Any]):
        """Legacy helper for single-node fast path update."""
        if graph.nodes:
            target_node = graph.nodes[0]
            target_node.id = target._uuid
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    def _inject_literals(self, graph: Graph, literals: Dict[str, Any]):
        """
        Injects literal values from the StructuralHasher into the reused Graph.
        
        It uses `structure_path` stored on Nodes to map flattened literal keys 
        back to the specific Node and argument they belong to.
        """
        # Build an index for fast lookup: path -> Node
        # Optimization: This could be cached on the Graph object if needed.
        node_map = {node.structure_path: node for node in graph.nodes if node.structure_path}
        
        # Reset literal_inputs for all nodes to ensure no stale data
        # (Though in practice, we usually overwrite all fields if structure is identical)
        for node in graph.nodes:
            node.literal_inputs = {}
            # We must regenerate a new UUID for the node to represent this new execution instance
            # This is critical for StateBackend to distinguish results.
            # However, for TCO loops, we might reuse IDs? No, TCO usually implies new instances.
            # Wait, `literals` doesn't contain UUIDs. We need to assign new UUIDs.
            # BUT: StructuralHasher doesn't track UUIDs.
            # If we reuse the graph, we are reusing the Node objects.
            # We MUST update their IDs.
            from uuid import uuid4
            node.id = str(uuid4())

        for key, value in literals.items():
            # Key format: "root.args.0.kwargs.foo"
            # We need to find the longest prefix that matches a node's structure_path.
            
            # This matching logic can be optimized. For now, we iterate nodes.
            # A literal "root.args.0" belongs to node "root" at arg "0".
            # A literal "root.dependencies.0.args.1" belongs to node "root.dependencies.0" at arg "1".
            
            # Heuristic: split key by dots, find split point.
            # Since structure_path matches keys in literals exactly (except for the final leaf arg),
            # we can try to peel off the last segment.
            
            if "." in key:
                parent_path, arg_name = key.rsplit(".", 1)
            else:
                # Should not happen for valid paths starting with "root"
                parent_path = key
                arg_name = ""

            if parent_path in node_map:
                node = node_map[parent_path]
                node.literal_inputs[arg_name] = value
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
        graph: Graph,
        plan: Any,
    ) -> Any:
        flow_manager = FlowManager(graph, target._uuid)
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
                        sub_graph = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                        )

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
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

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                # A skip due to a sequence aborting is a valid, graceful termination.
                # The workflow succeeded but produced no final value.
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None

                # For all other reasons, failing to produce the target result is an error.
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )

            # If it wasn't skipped but still has no result, it's a generic failure.
            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)


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

import sys
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Union
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.hashing import StructuralHasher
from cascade.spec.model import Node, Graph
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.constraint import GlobalConstraint
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    ResourceAcquired,
    ResourceReleased,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.interfaces.protocols import Solver, Executor, StateBackend, Connector
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
from cascade.runtime.constraints import ConstraintManager
from cascade.runtime.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.adapters.state import InMemoryStateBackend
from cascade.graph.compiler import BlueprintBuilder
from cascade.runtime.vm import VirtualMachine


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend

        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Union[Callable, ResourceDefinition]] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self._managed_subscribers = []
        self._graph_cache: Dict[str, Tuple[Graph, Any]] = {}

    def add_subscriber(self, subscriber: Any):
        """
        Adds a subscriber whose lifecycle (e.g., shutdown) the engine should manage.
        """
        self._managed_subscribers.append(subscriber)

    def register(self, resource_def: ResourceDefinition):
        # We store the full ResourceDefinition to preserve metadata like scope.
        self._resource_providers[resource_def.name] = resource_def

    def _is_simple_task(self, lr: Any) -> bool:
        """
        Checks if the LazyResult is a simple, flat task (no nested dependencies).
        This allows for the Zero-Overhead TCO fast path.
        """
        if not isinstance(lr, LazyResult):
            return False
        if lr._condition or (lr._constraints and not lr._constraints.is_empty()):
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

    def get_resource_provider(self, name: str) -> Callable:
        provider = self._resource_providers[name]
        if isinstance(provider, ResourceDefinition):
            return provider.func
        return provider

    def override_resource_provider(self, name: str, new_provider: Any):
        # When overriding, we might lose metadata if a raw function is passed,
        # but that's acceptable for testing overrides.
        self._resource_providers[name] = new_provider

    async def run(
        self, target: Any, params: Optional[Dict[str, Any]] = None, use_vm: bool = False
    ) -> Any:
        # VM Fast Path
        if use_vm:
            return await self._run_vm(target)

        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine initial target name for logging
        if hasattr(target, "task"):
            target_name = getattr(target.task, "name", "unknown")
        elif hasattr(target, "factory"):
            target_name = f"map({getattr(target.factory, 'name', 'unknown')})"
        else:
            target_name = "unknown"

        # Initialize State Backend using the factory
        state_backend = self.state_backend_factory(run_id)

        try:
            # 1. Establish Infrastructure Connection FIRST
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            # 2. Publish Lifecycle Event
            self.bus.publish(
                RunStarted(
                    run_id=run_id, target_tasks=[target_name], params=params or {}
                )
            )

            # TCO Loop: We keep executing as long as the result is a LazyResult
            current_target = target

            # The global stack holds "run" scoped resources
            with ExitStack() as run_stack:
                # Register the engine's connector as a special internal resource
                if self.connector:
                    from cascade.spec.resource import resource

                    @resource(name="_internal_connector", scope="run")
                    def _connector_provider():
                        yield self.connector

                    self.register(_connector_provider)

                active_resources: Dict[str, Any] = {}

                while True:
                    # The step stack holds "task" (step) scoped resources
                    with ExitStack() as step_stack:
                        # 1. Get Graph and Plan, using Structural Hash Cache
                        hasher = StructuralHasher()
                        struct_hash, literals = hasher.hash(current_target)

                        graph = None
                        plan = None

                        if struct_hash in self._graph_cache:
                            # CACHE HIT: Reuse graph and plan
                            cached_graph, cached_plan = self._graph_cache[struct_hash]

                            # LIMITATION: Current _update_graph_literals only supports single-node graphs correctly.
                            # For complex graphs, we must rebuild to ensure all UUIDs are correct.
                            if len(cached_graph.nodes) > 1:
                                graph = build_graph(current_target)
                                plan = self.solver.resolve(graph)
                            else:
                                graph = cached_graph
                                plan = cached_plan
                                self._update_graph_literals(
                                    graph, current_target, literals
                                )
                        else:
                            # CACHE MISS: Build, solve, and cache
                            graph = build_graph(current_target)
                            plan = self.solver.resolve(graph)
                            self._graph_cache[struct_hash] = (graph, plan)

                        # 2. Setup Resources (mixed scope)
                        required_resources = self._scan_for_resources(graph)
                        self._setup_resources(
                            required_resources,
                            active_resources,
                            run_stack,
                            step_stack,
                            run_id,
                        )

                        # 3. Execute
                        result = await self._execute_graph(
                            current_target,
                            params or {},
                            active_resources,
                            run_id,
                            state_backend,
                            graph=graph,
                            plan=plan,
                        )

                    # 4. Check for Tail Call (LazyResult)
                    if isinstance(result, (LazyResult, MappedLazyResult)):
                        current_target = result

                        # STATE GC: Since we are moving to a new generation (new graph),
                        # the transient state of the previous generation is no longer needed.
                        # We clear it to prevent memory leaks in infinite recursion.
                        if hasattr(state_backend, "clear"):
                            state_backend.clear()

                        # CRITICAL: Yield control to the event loop between TCO iterations.
                        # This allows other tasks (like the experiment timeout) to run.
                        await asyncio.sleep(0)
                    else:
                        final_result = result
                        break

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
            raise
        finally:
            # Gracefully shut down any managed subscribers BEFORE disconnecting the connector
            for sub in self._managed_subscribers:
                if hasattr(sub, "shutdown"):
                    await sub.shutdown()

            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))

    async def _run_vm(self, target: Any) -> Any:
        """
        Executes the target using the AOT Blueprint/VM path.
        """
        # 1. Compile in template mode
        builder = BlueprintBuilder()
        blueprint = builder.build(target, template=True)

        # 2. Extract Initial Arguments
        # The BlueprintBuilder treats the root LazyResult's args/kwargs as the
        # inputs for the blueprint.
        initial_args = list(target.args)
        initial_kwargs = dict(target.kwargs)

        # 3. Execute
        vm = VirtualMachine(
            resource_manager=self.resource_manager,
            constraint_manager=self.constraint_manager,
            wakeup_event=self._wakeup_event,
        )
        return await vm.execute(
            blueprint, initial_args=initial_args, initial_kwargs=initial_kwargs
        )

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        """Callback to handle incoming constraint messages."""
        try:
            # An empty payload, which becomes {}, signifies a cleared retained message (a resume command)
            if payload == {}:
                # Reconstruct scope from topic, e.g., cascade/constraints/task/api_call -> task:api_call
                scope_parts = topic.split("/")[2:]
                scope = ":".join(scope_parts)
                if scope:
                    self.constraint_manager.remove_constraints_by_scope(scope)
            else:
                # Basic validation, could be improved with a schema library
                constraint = GlobalConstraint(
                    id=payload["id"],
                    scope=payload["scope"],
                    type=payload["type"],
                    params=payload["params"],
                    expires_at=payload.get("expires_at"),
                )
                self.constraint_manager.update_constraint(constraint)
        except Exception as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint update on topic '{topic}': {e}",
                file=sys.stderr,
            )
        finally:
            # After any change (add, remove, or error), wake up the engine loop
            # if it's waiting.
            self._wakeup_event.set()

    def _update_graph_literals(
        self, graph: Graph, target: Any, literals: Dict[str, Any]
    ):
        """Injects new literal values and UUID into a cached graph."""
        # A simple graph has a predictable structure we can update directly.
        # This assumes a single root node for the target.
        node_map = {node.id: node for node in graph.nodes}

        # This is a bit of a simplification. A full implementation would need to
        # traverse the target structure and map literals back to the graph nodes.
        # For now, let's assume the root node gets the new literals.
        # The most important part is updating the target's UUID.

        # Find the node corresponding to the target LazyResult
        # In a cached graph, the ID is stale, so we find it by name or type.
        # For now, we assume the last node is the target node.
        if graph.nodes:
            target_node = graph.nodes[-1]
            target_node.id = target._uuid
            # This is a simplification; a robust solution would traverse and update.
            # For firefly, the structure is so simple this may be sufficient.
            if hasattr(target, "args") and hasattr(target, "kwargs"):
                target_node.literal_inputs = {
                    str(i): v for i, v in enumerate(target.args)
                }
                target_node.literal_inputs.update(target.kwargs)

    async def _execute_graph(
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

        # Track blocked state locally to avoid spamming Blocked events every loop tick
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue  # Skip params, they don't execute

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
                        # Node is resolved (skipped), so not pending for next pass
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.id in blocked_nodes:
                            blocked_nodes.remove(node.id)
                    else:
                        deferred_this_pass.append(node)
                        if node.id not in blocked_nodes:
                            from cascade.runtime.events import TaskBlocked

                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",  # Detailed reason requires manager update
                                )
                            )
                            blocked_nodes.add(node.id)

                if executable_this_pass:
                    tasks_to_run = [
                        self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
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
                    # All remaining nodes are blocked by constraints. Wait for a wakeup
                    # signal (e.g., from a constraint change or TTL expiration) before retrying.
                    await self._wakeup_event.wait()
                    self._wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(
                f"Target task '{target.task.name}' did not produce a result."
            )

        return state_backend.get_result(target._uuid)

    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            from cascade.runtime.events import TaskBlocked

            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, state_backend, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)

    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        args, kwargs = self.arg_resolver.resolve(
            node, graph, state_backend, active_resources, user_params=params
        )

        start_time = time.time()

        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs_for_cache(
                node, graph, state_backend
            )
            cached_value = await node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
        )

        if node.node_type == "map":
            # ... (Map logic remains complex, needs careful refactoring if touched)
            # For now, we assume it can be called recursively with the state backend
            return await self._execute_map_node(
                node, args, kwargs, active_resources, run_id, params, state_backend
            )

        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0
        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(node, args, kwargs)
                duration = time.time() - start_time
                self.bus.publish(
                    TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Succeeded",
                        duration=duration,
                        result_preview=repr(result)[:100],
                    )
                )
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs_for_cache(
                        node, graph, state_backend
                    )
                    await node.cache_policy.save(node.id, inputs_for_save, result)
                return result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                        )
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
                else:
                    duration = time.time() - start_time
                    self.bus.publish(
                        TaskExecutionFinished(
                            run_id=run_id,
                            task_id=node.id,
                            task_name=node.name,
                            status="Failed",
                            duration=duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                    )
                    raise last_exception
        raise RuntimeError("Unexpected execution state")

    def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        inputs = {}
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if state_backend.has_result(edge.source.id):
                inputs[edge.arg_name] = state_backend.get_result(edge.source.id)
        return inputs

    async def _execute_map_node(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        parent_state_backend: StateBackend,
    ) -> List[Any]:
        factory = node.mapping_factory
        if not kwargs:
            return []
        lengths = {k: len(v) for k, v in kwargs.items()}
        first_len = list(lengths.values())[0]
        if not all(length == first_len for length in lengths.values()):
            raise ValueError(f"Mapped inputs have mismatched lengths: {lengths}")

        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            sub_target = factory(**item_kwargs)
            if node.retry_policy:
                sub_target._retry_policy = node.retry_policy
            if node.cache_policy:
                sub_target._cache_policy = node.cache_policy
            if node.constraints:
                sub_target._constraints = node.constraints
            sub_targets.append(sub_target)

        # Each sub-task is a full workflow run from the engine's perspective
        # but shares the parent's state backend to see results.
        async def run_sub_target(target):
            # For mapped tasks, we perform the full build/solve cycle for each item.
            # TCO optimization does not apply here.
            graph = build_graph(target)
            plan = self.solver.resolve(graph)
            return await self._execute_graph(
                target,
                params,
                active_resources,
                run_id,
                parent_state_backend,
                graph=graph,
                plan=plan,
            )

        coros = [run_sub_target(target) for target in sub_targets]
        return await asyncio.gather(*coros)

    def _scan_for_resources(self, graph: Graph) -> set[str]:
        required = set()
        for node in graph.nodes:
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)

            if node.signature:
                for param in node.signature.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
            elif node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
        return required

    def _setup_resources(
        self,
        required_names: set[str],
        active_resources: Dict[str, Any],
        run_stack: ExitStack,
        step_stack: ExitStack,
        run_id: str,
    ) -> None:
        """
        Initializes required resources that are not yet active.
        Decides whether to put them in run_stack or step_stack based on scope.
        Updates active_resources in-place.
        """

        def get_or_create(name: str):
            if name in active_resources:
                return active_resources[name]

            provider_entry = self._resource_providers.get(name)
            if not provider_entry:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Determine scope and func
            scope = "run"
            func = provider_entry
            if isinstance(provider_entry, ResourceDefinition):
                scope = provider_entry.scope
                func = provider_entry.func

            # Recursive dependency resolution
            sig = inspect.signature(func)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }

            # Instantiate
            gen = func(**deps)
            instance = next(gen)

            # Register in active dict
            active_resources[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register teardown in appropriate stack
            target_stack = step_stack if scope == "task" else run_stack

            def cleanup():
                self._teardown_resource(gen, run_id, name)
                # Important: remove from active_resources so it can be re-created if needed later
                active_resources.pop(name, None)

            target_stack.callback(cleanup)
            return instance

        for name in required_names:
            get_or_create(name)

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )

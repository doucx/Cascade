import sys
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Type
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.spec.resource import ResourceDefinition, Inject
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


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Solver,
        executor: Executor,
        bus: MessageBus,
        state_backend_cls: Type[StateBackend] = InMemoryStateBackend,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
        self.constraint_manager.register_handler(PauseConstraintHandler())
        self.constraint_manager.register_handler(ConcurrencyConstraintHandler())
        self.constraint_manager.register_handler(RateLimitConstraintHandler())

        self._wakeup_event = asyncio.Event()
        self.constraint_manager.set_wakeup_callback(self._wakeup_event.set)

        self._resource_providers: Dict[str, Callable] = {}

        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()
        self.flow_manager: Optional[FlowManager] = None

    def register(self, resource_def: ResourceDefinition):
        self._resource_providers[resource_def.name] = resource_def.func

    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def override_resource_provider(self, name: str, new_provider: Any):
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        # Robustly determine target name
        target_names = []
        if isinstance(target, (list, tuple)):
            for t in target:
                if hasattr(t, "task"):
                    target_names.append(getattr(t.task, "name", "unknown"))
                elif hasattr(t, "factory"):
                    target_names.append(f"map({getattr(t.factory, 'name', 'unknown')})")
                else:
                    target_names.append("unknown")
        elif hasattr(target, "task"):
            target_names.append(getattr(target.task, "name", "unknown"))
        elif hasattr(target, "factory"):
            target_names.append(f"map({getattr(target.factory, 'name', 'unknown')})")
        else:
            target_names.append("unknown")

        state_backend = self.state_backend_cls(run_id=run_id)

        try:
            if self.connector:
                await self.connector.connect()
                self.bus.publish(ConnectorConnected(run_id=run_id))
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            self.bus.publish(
                RunStarted(run_id=run_id, target_tasks=target_names, params=params or {})
            )

            with ExitStack() as stack:
                initial_graph = build_graph(target)
                required_resources = self._scan_for_resources(initial_graph)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id, state_backend
                )

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
            if self.connector:
                await self.connector.disconnect()
                self.bus.publish(ConnectorDisconnected(run_id=run_id))

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

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        state_backend: StateBackend,
    ) -> Any:
        graph = build_graph(target)
        self.flow_manager = FlowManager(graph, target._uuid)
        plan = self.solver.resolve(graph)

        for stage in plan:
            # Nodes to be processed in the current stage
            pending_nodes = {node.id: node for node in stage}
            # Tasks currently running in asyncio
            running_tasks: Dict[asyncio.Task, str] = {}
            # Wakeup task for constraint changes
            wakeup_task = asyncio.create_task(self._wakeup_event.wait())

            # Nodes to be processed in the current stage
            pending_nodes = {node.id: node for node in stage}
            # Tasks currently running in asyncio
            running_tasks: Dict[asyncio.Task, str] = {}
            # Wakeup task for constraint changes
            wakeup_task = asyncio.create_task(self._wakeup_event.wait())
            first_exception: Optional[Exception] = None

            while pending_nodes or running_tasks:
                # 1. Schedule new tasks if possible, but only if no failure has occurred
                if pending_nodes and not first_exception:
                    schedulable_nodes = []
                    deferred_nodes = {}
                    for node_id, node in pending_nodes.items():
                        if self.constraint_manager.check_permission(node):
                            schedulable_nodes.append(node)
                        else:
                            deferred_nodes[node_id] = node

                    for node in schedulable_nodes:
                        if node.node_type == "param":
                            del pending_nodes[node.id]
                            continue
                        
                        skip_reason = self.flow_manager.should_skip(node, state_backend)
                        if skip_reason:
                            state_backend.mark_skipped(node.id, skip_reason)
                            self.bus.publish(
                                TaskSkipped(run_id=run_id, task_id=node.id, task_name=node.name, reason=skip_reason)
                            )
                            del pending_nodes[node.id]
                            continue

                        # Pre-check resources to prevent premature scheduling
                        # This ensures tasks stay in 'pending' (and thus under control of Pause/Permission checks)
                        # until resources are actually available.
                        requirements = self.constraint_resolver.resolve(
                            node, graph, state_backend, self.constraint_manager
                        )
                        
                        if not self.resource_manager.can_acquire(requirements):
                            # Not enough resources yet. Keep it pending.
                            deferred_nodes[node.id] = node
                            continue

                        coro = self._execute_node_with_policies(
                            node, graph, state_backend, active_resources, run_id, params
                        )
                        task = asyncio.create_task(coro)
                        running_tasks[task] = node.id
                        del pending_nodes[node.id]

                    pending_nodes = deferred_nodes

                if not running_tasks and (not pending_nodes or first_exception):
                    break

                # 2. Wait for something to happen
                tasks_to_wait = list(running_tasks.keys()) + [wakeup_task]
                done, pending = await asyncio.wait(
                    tasks_to_wait, return_when=asyncio.FIRST_COMPLETED
                )

                # 3. Process completed tasks
                for task in done:
                    if task is wakeup_task:
                        self._wakeup_event.clear()
                        wakeup_task = asyncio.create_task(self._wakeup_event.wait())
                        self.constraint_manager.cleanup_expired_constraints()
                        for node_id, node in pending_nodes.items():
                             pending_nodes[node_id] = node
                        continue

                    node_id = running_tasks.pop(task)
                    try:
                        result = task.result()
                        state_backend.put_result(node_id, result)
                        if self.flow_manager:
                            self.flow_manager.register_result(
                                node_id, result, state_backend
                            )
                    except Exception as e:
                        if not first_exception:
                            first_exception = e
                        # Once an error occurs, cancel remaining running tasks in the stage
                        for t in running_tasks:
                            t.cancel()

            # Clean up the wakeup task if the stage finishes
            if not wakeup_task.done():
                wakeup_task.cancel()
                try:
                    await wakeup_task
                except asyncio.CancelledError:
                    pass
            
            if first_exception:
                raise first_exception

        if not state_backend.has_result(target._uuid):
            target_name = "unknown"
            if hasattr(target, "task"):
                target_name = getattr(target.task, "name", "unknown")
            elif hasattr(target, "factory"):
                target_name = f"map({getattr(target.factory, 'name', 'unknown')})"

            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target_name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(
                f"Target task '{target_name}' did not produce a result."
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
            cached_value = node.cache_policy.check(node.id, inputs_for_cache)
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
                    node.cache_policy.save(node.id, inputs_for_save, result)
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
        coros = [
            self._execute_graph(
                target, params, active_resources, run_id, parent_state_backend
            )
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)

    def _scan_for_resources(self, graph: Graph) -> set[str]:
        required = set()
        for node in graph.nodes:
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)
            if node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject):
                        required.add(param.default.resource_name)
        return required

    def _setup_resources(
        self, required_names: set[str], stack: ExitStack, run_id: str
    ) -> Dict[str, Any]:
        active: Dict[str, Any] = {}

        def get_or_create(name: str):
            if name in active:
                return active[name]
            provider = self._resource_providers.get(name)
            if not provider:
                raise NameError(f"Resource '{name}' is required but not registered.")
            sig = inspect.signature(provider)
            deps = {
                p_name: get_or_create(p.default.resource_name)
                for p_name, p in sig.parameters.items()
                if isinstance(p.default, Inject)
            }
            gen = provider(**deps)
            instance = next(gen)
            active[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))
            stack.callback(self._teardown_resource, gen, run_id, name)
            return instance

        for name in required_names:
            get_or_create(name)
        return active

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )

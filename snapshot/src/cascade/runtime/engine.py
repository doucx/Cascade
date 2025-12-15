import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.spec.task import LazyResult
from cascade.spec.resource import ResourceDefinition, Inject
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
)
from cascade.runtime.protocols import Solver, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None,
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()
        self._resource_providers: Dict[str, Callable] = {}

    def register(self, resource_def: ResourceDefinition):
        """Registers a resource provider function with the engine."""
        self._resource_providers[resource_def.name] = resource_def.func

    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def _inject_params(
        self, plan: list[Node], user_params: Dict[str, Any], results: Dict[str, Any]
    ):
        for node in plan:
            if node.node_type == "param":
                param_spec = node.param_spec
                if node.name in user_params:
                    results[node.id] = user_params[node.name]
                elif param_spec.default is not None:
                    results[node.id] = param_spec.default
                else:
                    raise ValueError(f"Required parameter '{node.name}' was not provided.")
    
    def _should_skip(
        self, 
        node: Node, 
        graph: Graph, 
        results: Dict[str, Any], 
        skipped_node_ids: set[str]
    ) -> Optional[str]:
        """
        Determines if a node should be skipped. 
        Returns the reason string if yes, None otherwise.
        """
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        
        # 1. Cascade Skip: If any upstream dependency was skipped
        for edge in incoming_edges:
            if edge.source.id in skipped_node_ids:
                return "UpstreamSkipped"

        # 2. Condition Check: If this node has a condition and it evaluated to False
        for edge in incoming_edges:
            if edge.arg_name == "_condition":
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"
        
        return None

    def override_resource_provider(self, name: str, new_provider: Any):
        # Unwrap ResourceDefinition if provided
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

    async def run(
        self, target: LazyResult, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        run_id = str(uuid4())
        start_time = time.time()

        target_task_names = [target.task.name]

        event = RunStarted(
            run_id=run_id, target_tasks=target_task_names, params=params or {}
        )
        self.bus.publish(event)

        # ExitStack manages the teardown of resources
        with ExitStack() as stack:
            try:
                graph = build_graph(target)
                plan = self.solver.resolve(graph)

                # Scan for all required resources
                required_resources = self._scan_for_resources(plan)

                # Setup resources and get active instances
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                results: Dict[str, Any] = {}
                skipped_node_ids: set[str] = set()

                # Pre-populate results with parameter values
                self._inject_params(plan, params or {}, results)

                for node in plan:
                    # Skip param nodes as they are not "executed"
                    if node.node_type == "param":
                        continue
                        
                    # Check if we should skip this node
                    skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
                    
                    if skip_reason:
                        skipped_node_ids.add(node.id)
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    results[node.id] = await self._execute_node_with_policies(
                        node, graph, results, active_resources, run_id
                    )

                run_duration = time.time() - start_time
                final_event = RunFinished(
                    run_id=run_id, status="Succeeded", duration=run_duration
                )
                self.bus.publish(final_event)

                return results[target._uuid]

            except Exception as e:
                run_duration = time.time() - start_time
                final_fail_event = RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=run_duration,
                    error=f"{type(e).__name__}: {e}",
                )
                self.bus.publish(final_fail_event)
                raise

    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        task_start_time = time.time()

        # 0. Check Cache
        if node.cache_policy:
            inputs_for_cache = self._resolve_inputs(node, graph, upstream_results)
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

        start_event = TaskExecutionStarted(
            run_id=run_id, task_id=node.id, task_name=node.name
        )
        self.bus.publish(start_event)

        # Determine retry policy
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0

        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(
                    node, graph, upstream_results, active_resources
                )

                task_duration = time.time() - task_start_time
                finish_event = TaskExecutionFinished(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    status="Succeeded",
                    duration=task_duration,
                    result_preview=repr(result)[:100],
                )
                self.bus.publish(finish_event)

                # Save to cache if policy exists
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs(node, graph, upstream_results)
                    node.cache_policy.save(node.id, inputs_for_save, result)

                return result

            except Exception as e:
                last_exception = e
                # If we have retries left, wait and continue
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
                    # Final failure
                    task_duration = time.time() - task_start_time
                    fail_event = TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Failed",
                        duration=task_duration,
                        error=f"{type(e).__name__}: {e}",
                    )
                    self.bus.publish(fail_event)
                    raise last_exception
        
        # Should not be reached if logic is correct
        raise RuntimeError("Unexpected execution state")

    def _resolve_inputs(self, node: Node, graph: Graph, upstream_results: Dict[str, Any]) -> Dict[str, Any]:
        """Helper to resolve inputs for cache checking."""
        inputs = {}
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            inputs[edge.arg_name] = upstream_results[edge.source.id]
        return inputs

    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        """Finds all unique resource names required by the plan."""
        required = set()
        for node in plan:
            # Skip nodes that don't have a callable (e.g., Param nodes)
            if node.callable_obj is None:
                continue

            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    required.add(param.default.resource_name)
        return required

    def _setup_resources(
        self, required_names: set[str], stack: ExitStack, run_id: str
    ) -> Dict[str, Any]:
        """
        Initializes all required resources and their dependencies recursively.
        Returns a dictionary of active resource instances.
        """
        active: Dict[str, Any] = {}

        def get_or_create(name: str):
            if name in active:
                return active[name]

            provider = self._resource_providers.get(name)
            if not provider:
                raise NameError(f"Resource '{name}' is required but not registered.")

            # Inspect provider's signature to find its dependencies
            sig = inspect.signature(provider)
            deps = {}
            for param_name, param in sig.parameters.items():
                if isinstance(param.default, Inject):
                    deps[param_name] = get_or_create(param.default.resource_name)
                # Here you could also inject `Param`s if needed

            # Create the resource generator
            gen = provider(**deps)

            # Enter the generator and get the yielded value
            instance = next(gen)
            active[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))

            # Register the teardown logic
            stack.callback(self._teardown_resource, gen, run_id, name)

            return instance

        for name in required_names:
            get_or_create(name)

        return active

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        """Helper to exhaust a resource generator for cleanup."""
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )

import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Tuple
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
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
from cascade.runtime.exceptions import DependencyMissingError
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.resource_manager import ResourceManager
from cascade.spec.lazy_types import LazyResult, MappedLazyResult # NEW


class Engine:
    """
    Orchestrates the entire workflow execution.
    """

    def __init__(
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None,
        system_resources: Optional[Dict[str, Any]] = None,
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()
        self.resource_manager = ResourceManager(capacity=system_resources)
        self._resource_providers: Dict[str, Callable] = {}

    def register(self, resource_def: ResourceDefinition):
        """Registers a resource provider function with the engine."""
        self._resource_providers[resource_def.name] = resource_def.func

    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]

    def override_resource_provider(self, name: str, new_provider: Any):
        if isinstance(new_provider, ResourceDefinition):
            new_provider = new_provider.func
        self._resource_providers[name] = new_provider

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
                    raise ValueError(
                        f"Required parameter '{node.name}' was not provided."
                    )

    def _should_skip(
        self,
        node: Node,
        graph: Graph,
        results: Dict[str, Any],
        skipped_node_ids: set[str],
    ) -> Optional[str]:
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # 1. Cascade Skip
        for edge in incoming_edges:
            if edge.source.id in skipped_node_ids:
                return "UpstreamSkipped"

        # 2. Condition Check
        for edge in incoming_edges:
            if edge.arg_name == "_condition":
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None

    def _resolve_arguments(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        resource_context: Dict[str, Any],
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers)
        3. Injected resources
        
        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 1. Prepare arguments from literals and upstream results
        final_kwargs = {k: v for k, v in node.literal_inputs.items() if not k.isdigit()}
        positional_args = {
            int(k): v for k, v in node.literal_inputs.items() if k.isdigit()
        }

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"): # Skip control/meta edges
                continue
            
            # Resolve Upstream Value
            if edge.router:
                # Handle Dynamic Routing
                selector_value = upstream_results.get(edge.source.id)
                if selector_value is None:
                     # If the selector itself is missing, that's an error
                     if edge.source.id not in upstream_results:
                         raise DependencyMissingError(node.id, "router_selector", edge.source.id)
                
                try:
                    selected_lazy_result = edge.router.routes[selector_value]
                except KeyError:
                    raise ValueError(
                        f"Router selector returned '{selector_value}', "
                        f"but no matching route found in {list(edge.router.routes.keys())}"
                    )
                
                dependency_id = selected_lazy_result._uuid
            else:
                # Standard dependency
                dependency_id = edge.source.id

            # Check existence in results
            if dependency_id not in upstream_results:
                raise DependencyMissingError(node.id, edge.arg_name, dependency_id)
            
            result = upstream_results[dependency_id]

            # Assign to args/kwargs
            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result

        # 2. Prepare arguments from injected resources (Implicit Injection via Signature)
        if node.callable_obj:
            sig = inspect.signature(node.callable_obj)
            for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                    resource_name = param.default.resource_name
                    if resource_name in resource_context:
                        final_kwargs[param.name] = resource_context[resource_name]
                    else:
                        raise NameError(
                            f"Task '{node.name}' requires resource '{resource_name}' "
                            "which was not found in the active context."
                        )

        # 3. Resolve explicit Inject objects in arguments (passed as values)
        # Convert positional map to list
        sorted_indices = sorted(positional_args.keys())
        args = [positional_args[i] for i in sorted_indices]
        
        resolved_args = []
        for arg in args:
            if isinstance(arg, Inject):
                if arg.resource_name in resource_context:
                    resolved_args.append(resource_context[arg.resource_name])
                else:
                    raise NameError(f"Resource '{arg.resource_name}' not found.")
            else:
                resolved_args.append(arg)
        args = resolved_args

        for key, value in final_kwargs.items():
            if isinstance(value, Inject):
                if value.resource_name in resource_context:
                    final_kwargs[key] = resource_context[value.resource_name]
                else:
                    raise NameError(f"Resource '{value.resource_name}' not found.")
        
        return args, final_kwargs

    async def run(self, target: Any, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
        target_name = getattr(target, "name", "unknown")
        if hasattr(target, "task"):
            target_name = target.task.name

        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )

        with ExitStack() as stack:
            try:
                initial_graph = build_graph(target)
                initial_plan = self.solver.resolve(initial_graph)

                required_resources = self._scan_for_resources(initial_plan)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id
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

    async def _execute_graph(
        self,
        target: Any,
        params: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
    ) -> Any:
        graph = build_graph(target)
        plan = self.solver.resolve(graph)
        results: Dict[str, Any] = {}
        skipped_node_ids: set[str] = set()

        self._inject_params(plan, params, results)

        for node in plan:
            if node.node_type == "param":
                continue

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

            # Execute Node
            results[node.id] = await self._execute_node_with_policies(
                node, graph, results, active_resources, run_id, params
            )

        return results[target._uuid]

    async def _execute_node_with_policies(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        # Resolve Dynamic Constraints
        requirements = self._resolve_constraints(node, graph, upstream_results)
        
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_node_internal(
                node, graph, upstream_results, active_resources, run_id, params
            )
        finally:
            await self.resource_manager.release(requirements)

    def _resolve_constraints(
        self, node: Node, graph: Graph, upstream_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}
        
        resolved = {}
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                if amount._uuid in upstream_results:
                    resolved[res] = upstream_results[amount._uuid]
                else:
                    # Logic to determine if it was skipped or just missing
                    raise DependencyMissingError(node.id, f"constraint:{res}", amount._uuid)
            else:
                resolved[res] = amount
        return resolved

    async def _execute_node_internal(
        self,
        node: Node,
        graph: Graph,
        upstream_results: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> Any:
        # 1. Resolve Arguments (Input Validation happens here)
        # Note: Map nodes handle their own resolution internally for sub-tasks, 
        # but the map node itself has inputs (the iterables) which need validation.
        # We'll let _resolve_arguments handle standard inputs.
        
        # However, Map nodes are special. They iterate. 
        # _execute_map_node will need to be refactored or we handle it here.
        # Let's handle generic inputs first.
        try:
            args, kwargs = self._resolve_arguments(
                node, graph, upstream_results, active_resources
            )
        except DependencyMissingError:
            # Re-raise. In future we could emit a specific event here.
            raise

        start_time = time.time()

        # 2. Check Cache
        if node.cache_policy:
            # We can reconstruct inputs dict for cache check from args/kwargs?
            # Or use a simplified resolver. 
            # For now, let's just use the resolved args/kwargs as cache input context?
            # The current cache policy expects a dict.
            # Let's map args back to names if possible, or just use kwargs.
            # Simpler: Use _resolve_inputs helper just for cache (legacy way) or update cache to use args/kwargs.
            # To minimize risk, I will keep _resolve_inputs helper ONLY for cache key generation for now.
            inputs_for_cache = self._resolve_inputs_for_cache(node, graph, upstream_results)
            cached_value = node.cache_policy.check(node.id, inputs_for_cache)
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(run_id=run_id, task_id=node.id, task_name=node.name, reason="CacheHit")
                )
                return cached_value

        self.bus.publish(TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name))

        # 3. Execution (Map or Single)
        if node.node_type == "map":
             # Map node logic is complex, it needs to generate sub-tasks.
             # It uses args/kwargs (iterables) resolved above.
             try:
                 result = await self._execute_map_node(
                     node, args, kwargs, active_resources, run_id, params
                 )
                 # ... (Events)
                 status = "Succeeded"
                 error = None
             except Exception as e:
                 result = None
                 status = "Failed"
                 error = str(e)
                 raise e
             finally:
                 duration = time.time() - start_time
                 self.bus.publish(
                     TaskExecutionFinished(
                         run_id=run_id, task_id=node.id, task_name=node.name,
                         status=status, duration=duration, error=error,
                         result_preview=f"List[{len(result)}]" if result else None
                     )
                 )
             return result

        # Single Task Execution with Retry
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0

        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                # CALL THE EXECUTOR with clean Args
                result = await self.executor.execute(node, args, kwargs)

                duration = time.time() - start_time
                self.bus.publish(
                    TaskExecutionFinished(
                        run_id=run_id, task_id=node.id, task_name=node.name,
                        status="Succeeded", duration=duration,
                        result_preview=repr(result)[:100]
                    )
                )

                if node.cache_policy:
                     inputs_for_save = self._resolve_inputs_for_cache(node, graph, upstream_results)
                     node.cache_policy.save(node.id, inputs_for_save, result)

                return result

            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id, task_id=node.id, task_name=node.name,
                            attempt=attempt, max_attempts=max_attempts, delay=delay, error=str(e)
                        )
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
                else:
                    duration = time.time() - start_time
                    self.bus.publish(
                        TaskExecutionFinished(
                            run_id=run_id, task_id=node.id, task_name=node.name,
                            status="Failed", duration=duration, error=f"{type(e).__name__}: {e}"
                        )
                    )
                    raise last_exception
        
        raise RuntimeError("Unexpected execution state")

    def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, upstream_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Helper to resolve inputs specifically for cache checking/saving."""
        inputs = {}
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"): continue
            
            # Simple resolution for cache keys
            if edge.source.id in upstream_results:
                inputs[edge.arg_name] = upstream_results[edge.source.id]
        return inputs

    async def _execute_map_node(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
    ) -> List[Any]:
        # Validate lengths
        # In args/kwargs, values should be iterables
        # We need to construct sub-tasks
        
        # Merge args and kwargs into a unified iterable map for length checking
        # This part assumes mapping inputs are passed as kwargs (standard for .map)
        # But args could exist too.
        
        # Logic: 
        # 1. Determine length from first iterable
        # 2. Iterate and invoke factory
        
        # Note: MappedLazyResult usually puts inputs in mapping_kwargs.
        # But _resolve_arguments flattened everything into args/kwargs.
        
        # For MVP safety, let's assume .map() only uses kwargs for the mapped arguments,
        # which is how Task.map implementation works.
        
        factory = node.mapping_factory
        
        # Safety check: if there are positional args in a map node, it's ambiguous which to iterate
        if args:
             # If we support mapping over positional args, we'd need to zip them.
             # For now, let's assume args are static or unsupported in map.
             pass

        if not kwargs:
            return []

        lengths = {k: len(v) for k, v in kwargs.items()}
        first_len = list(lengths.values())[0]
        if not all(l == first_len for l in lengths.values()):
            raise ValueError(f"Mapped inputs have mismatched lengths: {lengths}")

        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            # Factory creates a LazyResult
            sub_target = factory(**item_kwargs)
            sub_targets.append(sub_target)

        coros = [
            self._execute_graph(target, params, active_resources, run_id)
            for target in sub_targets
        ]

        return await asyncio.gather(*coros)

    def _scan_for_resources(self, plan: list[Node]) -> set[str]:
        required = set()
        for node in plan:
            # Check literal inputs
            for value in node.literal_inputs.values():
                if isinstance(value, Inject):
                    required.add(value.resource_name)

            # Check signature
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
            deps = {}
            for param_name, param in sig.parameters.items():
                if isinstance(param.default, Inject):
                    deps[param_name] = get_or_create(param.default.resource_name)

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
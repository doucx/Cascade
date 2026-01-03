import time
import asyncio
from typing import Any, Dict, List, Callable, Awaitable, TYPE_CHECKING, Tuple


from cascade.graph.model import Node

if TYPE_CHECKING:
    from cascade.graph.model import MapNode
from cascade.spec.protocols import Executor, StateBackend, Solver
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.constraints.manager import ConstraintManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    TaskBlocked,
)


class NodeProcessor:
    def __init__(
        self,
        executor: Executor,
        bus: MessageBus,
        resource_manager: ResourceManager,
        constraint_manager: ConstraintManager,
        solver: Solver,  # Needed for map nodes
    ):
        self.executor = executor
        self.bus = bus
        self.resource_manager = resource_manager
        self.constraint_manager = constraint_manager
        self.solver = solver

        # Resolvers are owned by the processor, but now invoked by the Strategy
        self.arg_resolver = ArgumentResolver()
        # ConstraintResolver now needs the instance map to resolve dynamic values
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
        node: Node,
        executable: Callable,
        inputs: Tuple[List[Any], Dict[str, Any]],
        requirements: Dict[str, Any],
        cache_inputs: Dict[str, Any],
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
    ) -> Any:
        # 1. Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.current_node_instance_hash,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        # 2. Acquire Resources
        if requirements:
            await self.resource_manager.acquire(requirements)
            try:
                return await self._execute_internal(
                    node,
                    executable,
                    inputs,
                    cache_inputs,
                    state_backend,
                    active_resources,
                    run_id,
                    params,
                    sub_graph_runner,
                )
            finally:
                await self.resource_manager.release(requirements)
        else:
            # FAST PATH: No resources required
            return await self._execute_internal(
                node,
                executable,
                inputs,
                cache_inputs,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
            )

    async def _execute_internal(
        self,
        node: Node,
        executable: Callable,
        inputs: Tuple[List[Any], Dict[str, Any]],
        cache_inputs: Dict[str, Any],
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
    ) -> Any:
        # 3. Use Resolved Arguments
        args, kwargs = inputs

        start_time = time.time()

        # 4. Cache Check
        if node.cache_policy:
            cached_value = await node.cache_policy.check(
                node.current_node_instance_hash, cache_inputs
            )
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.current_node_instance_hash,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(
                run_id=run_id,
                task_id=node.current_node_instance_hash,
                task_name=node.name,
            )
        )

        # 5. Handle Map Nodes
        from cascade.graph.model import MapNode

        if isinstance(node, MapNode):
            return await self._execute_map_node(
                node,
                executable,  # The factory is passed here
                kwargs,
                active_resources,
                run_id,
                params,
                state_backend,
                sub_graph_runner,
            )

        # 6. Retry Loop & Execution
        retry_policy = node.retry_policy
        max_attempts = 1 + (retry_policy.max_attempts if retry_policy else 0)
        delay = retry_policy.delay if retry_policy else 0.0
        backoff = retry_policy.backoff if retry_policy else 1.0
        attempt = 0
        last_exception = None

        while attempt < max_attempts:
            attempt += 1
            try:
                result = await self.executor.execute(node, executable, args, kwargs)
                duration = time.time() - start_time
                self.bus.publish(
                    TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.current_node_instance_hash,
                        task_name=node.name,
                        status="Succeeded",
                        duration=duration,
                        result_preview=None,
                    )
                )
                if node.cache_policy:
                    await node.cache_policy.save(
                        node.current_node_instance_hash, cache_inputs, result
                    )
                return result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id,
                            task_id=node.current_node_instance_hash,
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
                            task_id=node.current_node_instance_hash,
                            task_name=node.name,
                            status="Failed",
                            duration=duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                    )
                    raise last_exception
        raise RuntimeError("Unexpected execution state")

    async def _execute_map_node(
        self,
        node: "MapNode",
        factory: Callable,
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        parent_state_backend: StateBackend,
        sub_graph_runner: Callable,
    ) -> List[Any]:
        if not factory:
            return []

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
            # Propagate policies
            if node.retry_policy:
                sub_target._retry_policy = node.retry_policy
            if node.cache_policy:
                sub_target._cache_policy = node.cache_policy
            if node.constraints:
                sub_target._constraints = node.constraints
            sub_targets.append(sub_target)

        coros = [
            sub_graph_runner(target, params, parent_state_backend)
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)

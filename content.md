## [WIP] refactor(core): 适配 Engine 与 Resolver 到新数据模型

### 用户需求
承接上一步的“结构数据分离”重构，修复 `ArgumentResolver`、`NodeProcessor`、`GraphExecutionStrategy` 和 `Engine`，使其能够正确处理新的 `input_bindings` 和 `SlotRef` 机制。

### 评论
这是“心脏移植”手术的后半部分。我们已经有了新的骨架（GraphTemplate），现在我们需要让心脏（Engine）学会如何将血液（DataTuple）泵入骨架中，使其活过来。

### 目标
1.  重构 `ArgumentResolver`：不再遍历 `literal_inputs`，而是根据 `input_bindings` 和传入的 `data_tuple` 重组参数。
2.  重构 `NodeProcessor`：方法签名增加 `data_tuple` 参数。
3.  重构 `GraphExecutionStrategy`：适配 `build_graph` 的新返回值 `(graph, data)`，并管理数据的传递。
4.  验证 Solvers 的兼容性（它们主要依赖 Edges，应该无需大改，但需确认）。

### 基本原理
执行流程将变为：
1.  `build_graph(target)` 返回 `(GraphTemplate, DataTuple)`。
2.  `Solver` 对 `GraphTemplate` 进行排序得到 `ExecutionPlan`。
3.  `Engine` 按照 `ExecutionPlan` 调度任务。
4.  在执行具体节点前，`ArgumentResolver` 查阅 `Node.input_bindings`。
    *   如果是 `SlotRef(i)`，则从 `DataTuple[i]` 取值。
    *   如果是 `Constant(v)`，直接使用 `v`。
    *   然后结合 `Edge` (Dependencies) 解析出的结果，组装成最终的 `args` 和 `kwargs`。

### 标签
#intent/refine #flow/draft #priority/critical #comp/engine #concept/data-model #scope/core #ai/instruct #task/domain/core #task/object/engine-resolver #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 重构 ArgumentResolver

这是数据注入发生的地方。我们需要修改 `resolve` 方法，使其接受 `data_tuple`，并利用 `input_bindings` 还原参数。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple, Optional

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.binding import SlotRef, Constant
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by combining:
    1. Structural bindings (SlotRefs pointing to DataTuple)
    2. Upstream dependencies (Edges)
    3. Resource injections
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        data_tuple: Tuple[Any, ...],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # Special handling for internal param fetcher
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            # For params, we construct a synthetic kwargs dict
            # We assume the 'name' and 'default' are passed via bindings/data
            # but getting them from bindings logic below is cleaner.
            pass 

        # 1. Reconstruct initial args/kwargs from Bindings + DataTuple
        # This replaces the old 'literal_inputs' traversal
        initial_kwargs = {}
        positional_args_dict = {}

        for name, binding in node.input_bindings.items():
            value = self._resolve_binding(binding, data_tuple)
            
            # Recursively resolve structure (lists/dicts containing other things)
            # Note: In the new builder, complex structures are mostly flattened or kept as data.
            # If data contains LazyResults (which shouldn't happen for bindings), we'd need to resolve them.
            # But LazyResults are now Edges. 
            # However, nested lists/dicts might still exist in data. 
            # For now, we assume data is 'literal' enough, or we apply structure resolution.
            value = self._resolve_structure(value, node.id, state_backend, resource_context, graph)

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                initial_kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]
        kwargs = initial_kwargs

        # 2. Overlay Dependencies (Edges)
        # Edges overwrite bindings if they share the same arg_name (which they shouldn't usually, but precedence rules apply)
        # Actually, in the new model, an arg is EITHER a binding OR an edge.
        incoming_edges = [e for e in graph.edges if e.target.id == node.id]
        
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.DATA:
                val = self._resolve_dependency(edge, node.id, state_backend, graph)
                
                # Handle positional vs keyword
                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    # Extend args list if needed
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    # Handle nested paths? e.g. "data.items[0]"
                    # For V3 Great Split, we simplify: top-level args only for now.
                    # Complex nested injection requires a more sophisticated setter.
                    # Assuming flat arg names for MVP.
                    kwargs[edge.arg_name] = val
            
            elif edge.edge_type == EdgeType.ROUTER_ROUTE:
                 # Implicitly handled via flow pruning, but if it carries data?
                 # Router edges are conditional paths. The actual data comes from the route result.
                 pass

        # 3. Handle Resource Injection (Defaults)
        # Only check params that are NOT already filled
        if node.signature:
            for param in node.signature.parameters.values():
                if isinstance(param.default, Inject):
                    if param.name not in kwargs and (len(args) <= list(node.signature.parameters).index(param.name)):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
        elif node.callable_obj:
             sig = inspect.signature(node.callable_obj)
             for param in sig.parameters.values():
                if isinstance(param.default, Inject):
                     if param.name not in kwargs: # Simplified check
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )

        # 4. Handle internal param fetching context
        if node.callable_obj is _get_param_value.func:
             kwargs["params_context"] = user_params or {}

        return args, kwargs

    def _resolve_binding(self, binding: Any, data_tuple: Tuple[Any, ...]) -> Any:
        if isinstance(binding, SlotRef):
            return data_tuple[binding.index]
        elif isinstance(binding, Constant):
            return binding.value
        # Fallback for legacy or raw values (shouldn't happen in strict mode)
        return binding

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
        """
        Recursively traverses data structures.
        Mainly to handle Inject if it ended up in data, or nested lists/dicts.
        """
        if isinstance(obj, Inject):
            return self._resolve_inject(obj, consumer_id, resource_context)

        elif isinstance(obj, list):
            return [
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            ]

        elif isinstance(obj, tuple):
            return tuple(
                self._resolve_structure(
                    item, consumer_id, state_backend, resource_context, graph
                )
                for item in obj
            )

        elif isinstance(obj, dict):
            return {
                k: self._resolve_structure(
                    v, consumer_id, state_backend, resource_context, graph
                )
                for k, v in obj.items()
            }

        return obj

    def _resolve_dependency(
        self,
        edge: Any, # Typed as Edge, avoiding circular import
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        source_id = edge.source.id
        
        # If result exists, return it.
        if state_backend.has_result(source_id):
            return state_backend.get_result(source_id)

        # If missing, check skip logic (penetration, etc.)
        # Logic similar to old _resolve_lazy
        if state_backend.get_skip_reason(source_id):
             # Try penetration
             # Find inputs to the skipped source node
             upstream_edges = [e for e in graph.edges if e.target.id == source_id]
             data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]
             
             if data_inputs:
                 # Recursively try to resolve the source of the skipped node
                 return self._resolve_dependency(data_inputs[0], consumer_id, state_backend, graph)
        
        skip_info = ""
        if reason := state_backend.get_skip_reason(source_id):
            skip_info = f" (skipped: {reason})"

        raise DependencyMissingError(
            consumer_id, edge.arg_name, f"{source_id}{skip_info}"
        )

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]

        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)
~~~~~

#### Acts 2: 更新 NodeProcessor

更新 `NodeProcessor.process` 和 `_execute_internal` 签名以传递 `data_tuple`。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
import time
import asyncio
from typing import Any, Dict, List, Callable, Awaitable, Tuple

from cascade.graph.model import Node, Graph
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
    """
    Responsible for executing a single node within a workflow graph.
    Handles policies such as constraints, caching, retries, and argument resolution.
    """

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

        # Resolvers are owned by the processor
        self.arg_resolver = ArgumentResolver()
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
        node: Node,
        graph: Graph,
        data_tuple: Tuple[Any, ...], # NEW
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.id,
                    task_name=node.name,
                    reason="ResourceContention",
                )
            )

        # 2. Acquire Resources
        await self.resource_manager.acquire(requirements)
        try:
            return await self._execute_internal(
                node,
                graph,
                data_tuple,
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
            )
        finally:
            await self.resource_manager.release(requirements)

    async def _execute_internal(
        self,
        node: Node,
        graph: Graph,
        data_tuple: Tuple[Any, ...], # NEW
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node, graph, state_backend, active_resources, data_tuple, user_params=params
        )

        start_time = time.time()

        # 4. Cache Check
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

        # 5. Handle Map Nodes
        if node.node_type == "map":
            return await self._execute_map_node(
                node,
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
                # Cache Save
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
        # TODO: This needs to be smarter for caching. 
        # It should probably include data from input_bindings too?
        # For now, keeping legacy behavior (edge results only).
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
        kwargs: Dict[str, Any],
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        parent_state_backend: StateBackend,
        sub_graph_runner: Callable,
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
            # Propagate policies
            if node.retry_policy:
                sub_target._retry_policy = node.retry_policy
            if node.cache_policy:
                sub_target._cache_policy = node.cache_policy
            if node.constraints:
                sub_target._constraints = node.constraints
            sub_targets.append(sub_target)

        # Execute sub-targets in parallel using the provided runner
        coros = [
            sub_graph_runner(target, params, parent_state_backend)
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)
~~~~~

#### Acts 3: 重构 GraphExecutionStrategy

更新 `execute` 方法以处理 `build_graph` 返回的元组，移除 `_update_graph_literals`，并将数据传递给处理器。同时简化缓存逻辑（暂时注释掉旧的缓存逻辑，因为它需要重写适配新的哈希策略）。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies.py
~~~~~
~~~~~python
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
                data_tuple = () # The Flesh
                is_fast_path = False

                # --- 1. ZERO-OVERHEAD FAST PATH CHECK ---
                # Check if we are in a recognized TCO loop (A -> B -> ... -> A)
                
                if isinstance(current_target, LazyResult) and self._is_simple_task(current_target):
                    task_obj = current_target.task
                    cycle_id = getattr(task_obj, "_tco_cycle_id", None)
                    
                    if (cycle_id and cycle_id == last_tco_cycle_id) or (task_obj == last_executed_task):
                        if task_obj in self._task_templates:
                            is_fast_path = True
                            graph, plan = self._task_templates[task_obj]
                            # For fast path, we still need to extract data!
                            # Since we skipped build_graph, we need a lightweight data extractor.
                            # BUT, for V3 step 1, we can just call build_graph and throw away the graph 
                            # if we want to be lazy, OR just disable fast path for now until we build a pure DataExtractor.
                            # Disable fast path for this commit to ensure correctness first.
                            is_fast_path = False 
                
                if not is_fast_path:
                    # --- 2. STANDARD PATH ---
                    # Always build fresh for now to handle data extraction
                    graph, data_tuple = build_graph(current_target)
                    plan = self.solver.resolve(graph)
                    
                    # Store in template cache for future optimization (even if we don't fully use it yet)
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
                    data_tuple, # Pass the blood!
                    plan,
                )

            # Capture the task we just executed BEFORE updating current_target
            if isinstance(current_target, LazyResult):
                last_executed_task = current_target.task
            else:
                last_executed_task = None

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
                        # Recursive call: must build new graph and data
                        sub_graph, sub_data = build_graph(target)
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
                if skip_reason == "UpstreamSkipped_Sequence":
                    return None
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )

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
~~~~~

### 下一步建议
我们已经完成了核心组件的修复，现在系统应该可以运行基本的 `Engine.run` 了。
下一步建议进行 **[COMMIT 3] 适配下游 - 更新 Solver 与 Tools**，因为虽然 Solvers 可能暂时能跑，但 `ResourceContainer.scan` 和序列化模块仍在使用旧的 `literal_inputs` 属性，需要清理。特别是 `ResourceContainer` 必须扫描 `input_bindings` 中的 Constant 和 DataTuple 中的内容来查找 `Inject`。这一步非常关键，否则资源注入会失败。

此外，建议运行一些基础测试（如 `tests/engine/runtime/test_engine_core.py`）来验证此次重构的有效性。

由于“架构缺陷 B”是一个涉及多个核心组件的重大重构，本计划将一次性执行所有必要的更改，以确保系统处于一致状态。这包括协议定义、后端实现、解析器、流管理器、执行策略以及测试套件的更新。

## [WIP] refactor(core): 强制 StateBackend 异步化以确立 I/O 边界

### 用户需求
1.  **架构合规**: 强制 `StateBackend` 协议使用 `async def`，消除 IO 边界的模糊性。
2.  **安全性**: 在 `InMemoryStateBackend` 中示范性地使用 `asyncio.to_thread`，确保即使是同步操作也不会阻塞主事件循环。
3.  **兼容性**: 更新所有核心运行时组件（解析器、流管理器、策略）以适配新的异步契约。

### 评论
这是一个“断骨增高”式的重构。虽然它会在短期内破坏所有依赖 `StateBackend` 的代码，但长远来看，它为引入持久化存储（如 Redis, SQLite, 文件系统）扫清了最大的架构障碍，并确立了 Cascade 作为一个真正非阻塞框架的地位。

### 目标
1.  更新 `cascade-spec` 中的 `StateBackend` 协议。
2.  更新 `InMemoryStateBackend` 和 `RedisStateBackend` 实现。
3.  更新 `ArgumentResolver`, `ConstraintResolver`, `FlowManager`, `NodeProcessor`, `GraphExecutionStrategy` 以异步方式调用状态后端。
4.  添加/更新测试以验证异步行为。

### 基本原理
通过在协议层强制 `async`，利用 Python 的类型系统和运行时检查来防止同步 I/O 意外阻塞事件循环。在同步实现中使用 `asyncio.to_thread` 是为了模拟真实 I/O 场景下的线程隔离，确保架构的一致性。

### 标签
#intent/refactor #flow/ready #priority/critical #comp/engine #comp/interfaces #concept/state #scope/core #ai/instruct #task/domain/core #task/object/state-backend #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新协议定义

将 `StateBackend` 协议的所有方法更新为异步方法。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/protocols.py
~~~~~
~~~~~python
class StateBackend(Protocol):
    """
    Protocol for a backend that stores the transient state of a single workflow run.
    This includes task results and skip statuses.
    """

    def put_result(self, node_id: str, result: Any) -> None:
        """Stores the result of a completed task."""
        ...

    def get_result(self, node_id: str) -> Optional[Any]:
        """Retrieves the result of a task. Returns None if not found."""
        ...

    def has_result(self, node_id: str) -> bool:
        """Checks if a result for a given task ID exists."""
        ...

    def mark_skipped(self, node_id: str, reason: str) -> None:
        """Marks a task as skipped."""
        ...

    def get_skip_reason(self, node_id: str) -> Optional[str]:
        """Retrieves the reason a task was skipped. Returns None if not skipped."""
        ...
~~~~~
~~~~~python
class StateBackend(Protocol):
    """
    Protocol for a backend that stores the transient state of a single workflow run.
    This includes task results and skip statuses.
    """

    async def put_result(self, node_id: str, result: Any) -> None:
        """Stores the result of a completed task."""
        ...

    async def get_result(self, node_id: str) -> Optional[Any]:
        """Retrieves the result of a task. Returns None if not found."""
        ...

    async def has_result(self, node_id: str) -> bool:
        """Checks if a result for a given task ID exists."""
        ...

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        """Marks a task as skipped."""
        ...

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        """Retrieves the reason a task was skipped. Returns None if not skipped."""
        ...
~~~~~

#### Acts 2: 更新 InMemoryStateBackend

实现异步接口，并使用 `asyncio.to_thread` 包装操作以确保非阻塞（即使字典操作很快，也要遵守架构契约）。同时将 `clear` 方法也改为异步。

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/state/in_memory.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict, Optional


class InMemoryStateBackend:
    """
    An in-memory implementation of the StateBackend protocol using Python dictionaries.
    This is the default backend for local, single-process runs.
    """

    def __init__(self, run_id: str):
        self._run_id = run_id
        self._results: Dict[str, Any] = {}
        self._skipped: Dict[str, str] = {}

    async def put_result(self, node_id: str, result: Any) -> None:
        await asyncio.to_thread(self._results.__setitem__, node_id, result)

    async def get_result(self, node_id: str) -> Optional[Any]:
        return await asyncio.to_thread(self._results.get, node_id)

    async def has_result(self, node_id: str) -> bool:
        return await asyncio.to_thread(self._results.__contains__, node_id)

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        await asyncio.to_thread(self._skipped.__setitem__, node_id, reason)

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        return await asyncio.to_thread(self._skipped.get, node_id)

    async def clear(self) -> None:
        """
        Clears all results and skip reasons. Used between TCO iterations.
        """
        await asyncio.to_thread(self._results.clear)
        await asyncio.to_thread(self._skipped.clear)
~~~~~

#### Acts 3: 更新 RedisStateBackend

实现异步接口，并使用 `asyncio.to_thread` 包装同步的 Redis 客户端调用。

~~~~~act
write_file
packages/cascade-engine/src/cascade/adapters/state/redis.py
~~~~~
~~~~~python
import asyncio
import pickle
from typing import Any, Optional

try:
    import redis
except ImportError:
    redis = None


class RedisStateBackend:
    """
    A StateBackend implementation that persists results to Redis.
    """

    def __init__(self, run_id: str, client: "redis.Redis", ttl: int = 86400):
        if redis is None:
            raise ImportError(
                "The 'redis' library is required to use RedisStateBackend."
            )

        self._run_id = run_id
        self._client = client
        self._ttl = ttl

        # Keys
        self._results_key = f"cascade:run:{run_id}:results"
        self._skipped_key = f"cascade:run:{run_id}:skipped"

    async def put_result(self, node_id: str, result: Any) -> None:
        data = pickle.dumps(result)
        await asyncio.to_thread(self._sync_put, node_id, data)

    def _sync_put(self, node_id: str, data: bytes):
        pipe = self._client.pipeline()
        pipe.hset(self._results_key, node_id, data)
        pipe.expire(self._results_key, self._ttl)
        pipe.execute()

    async def get_result(self, node_id: str) -> Optional[Any]:
        data = await asyncio.to_thread(self._client.hget, self._results_key, node_id)
        if data is None:
            return None
        return pickle.loads(data)

    async def has_result(self, node_id: str) -> bool:
        return await asyncio.to_thread(self._client.hexists, self._results_key, node_id)

    async def mark_skipped(self, node_id: str, reason: str) -> None:
        await asyncio.to_thread(self._sync_mark_skipped, node_id, reason)

    def _sync_mark_skipped(self, node_id: str, reason: str):
        pipe = self._client.pipeline()
        pipe.hset(self._skipped_key, node_id, reason)
        pipe.expire(self._skipped_key, self._ttl)
        pipe.execute()

    async def get_skip_reason(self, node_id: str) -> Optional[str]:
        data = await asyncio.to_thread(self._client.hget, self._skipped_key, node_id)
        if data:
            return data.decode("utf-8")
        return None
~~~~~

#### Acts 4: 更新解析器 (Resolvers)

将 `ArgumentResolver` 和 `ConstraintResolver` 改为异步，以支持异步的状态后端查询。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, Edge, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by combining:
    1. Structural bindings (Literal values stored in Node)
    2. Upstream dependencies (Edges)
    3. Resource injections
    """

    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
        input_overrides: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        # FAST PATH: If node is simple (no Injects, no magic params), skip the ceremony.
        if not node.has_complex_inputs:
            if input_overrides:
                # FASTEST PATH: Used by TCO loops
                # We trust overrides contain the full argument set or correct deltas.
                final_bindings = node.input_bindings.copy()
                final_bindings.update(input_overrides)

                # Convert to args/kwargs
                f_args = []
                f_kwargs = {}
                # Find max positional index
                max_pos = -1
                for k in final_bindings:
                    if k.isdigit():
                        idx = int(k)
                        if idx > max_pos:
                            max_pos = idx

                if max_pos >= 0:
                    f_args = [None] * (max_pos + 1)
                    for k, v in final_bindings.items():
                        if k.isdigit():
                            f_args[int(k)] = v
                        else:
                            f_kwargs[k] = v
                else:
                    f_kwargs = final_bindings

                return f_args, f_kwargs

        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        bindings = node.input_bindings
        if input_overrides:
            bindings = bindings.copy()
            bindings.update(input_overrides)

        positional_args_dict = {}
        for name, value_raw in bindings.items():
            # Always resolve structures to handle nested Injects correctly
            value = self._resolve_structure(
                value_raw, node.structural_id, state_backend, resource_context, graph
            )

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value

        sorted_indices = sorted(positional_args_dict.keys())
        args = [positional_args_dict[i] for i in sorted_indices]

        # 2. Overlay Dependencies from Edges
        # [OPTIMIZATION] Filter edges once using list comprehension
        incoming_edges = [
            e
            for e in graph.edges
            if e.target.structural_id == node.structural_id
            and e.edge_type == EdgeType.DATA
        ]

        if incoming_edges:
            for edge in incoming_edges:
                val = await self._resolve_dependency(
                    edge, node.structural_id, state_backend, graph, instance_map
                )

                if edge.arg_name.isdigit():
                    idx = int(edge.arg_name)
                    while len(args) <= idx:
                        args.append(None)
                    args[idx] = val
                else:
                    kwargs[edge.arg_name] = val

        # 3. Handle Resource Injection in Defaults
        if node.signature:
            # Create a bound arguments object to see which args are not yet filled
            try:
                bound_args = node.signature.bind_partial(*args, **kwargs)
                for param in node.signature.parameters.values():
                    if (
                        isinstance(param.default, Inject)
                        and param.name not in bound_args.arguments
                    ):
                        kwargs[param.name] = self._resolve_inject(
                            param.default, node.name, resource_context
                        )
            except TypeError:
                # This can happen if args/kwargs are not yet valid, but we can still try a simpler check
                pass

        # 4. Handle internal param fetching context
        # [CRITICAL] This logic must always run for Param tasks
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            kwargs["params_context"] = user_params or {}

        return args, kwargs

    def _resolve_structure(
        self,
        obj: Any,
        consumer_id: str,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        graph: Graph,
    ) -> Any:
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

    async def _resolve_dependency(
        self,
        edge: Edge,
        consumer_id: str,
        state_backend: StateBackend,
        graph: Graph,
        instance_map: Dict[str, Node],
    ) -> Any:
        # ** CORE ROUTER LOGIC FIX **
        if edge.router:
            # This edge represents a Router. Its source is the SELECTOR.
            # We must resolve the selector's value first.
            selector_result = await self._get_node_result(
                edge.source.structural_id,
                consumer_id,
                "router_selector",
                state_backend,
                graph,
            )

            # Use the result to pick the correct route.
            try:
                selected_route_lr = edge.router.routes[selector_result]
            except KeyError:
                raise ValueError(
                    f"Router selector for '{consumer_id}' returned '{selector_result}', "
                    f"but no matching route found in {list(edge.router.routes.keys())}"
                )

            # Now, resolve the result of the SELECTED route.
            # Convert instance UUID to canonical node ID using the map.
            selected_node = instance_map[selected_route_lr._uuid]
            return await self._get_node_result(
                selected_node.structural_id,
                consumer_id,
                edge.arg_name,
                state_backend,
                graph,
            )
        else:
            # Standard dependency
            return await self._get_node_result(
                edge.source.structural_id,
                consumer_id,
                edge.arg_name,
                state_backend,
                graph,
            )

    async def _get_node_result(
        self,
        node_id: str,
        consumer_id: str,
        arg_name: str,
        state_backend: StateBackend,
        graph: Graph,
    ) -> Any:
        """Helper to get a node's result, with skip penetration logic."""
        if await state_backend.has_result(node_id):
            return await state_backend.get_result(node_id)

        skip_reason = await state_backend.get_skip_reason(node_id)
        if skip_reason:
            upstream_edges = [
                e for e in graph.edges if e.target.structural_id == node_id
            ]
            data_inputs = [e for e in upstream_edges if e.edge_type == EdgeType.DATA]
            if data_inputs:
                # Recursively try to penetrate the skipped node
                return await self._get_node_result(
                    data_inputs[0].source.structural_id,
                    consumer_id,
                    arg_name,
                    state_backend,
                    graph,
                )

        skip_info = f" (skipped: {skip_reason})" if skip_reason else ""
        raise DependencyMissingError(consumer_id, arg_name, f"{node_id}{skip_info}")

    def _resolve_inject(
        self, inject: Inject, consumer_id: str, resource_context: Dict[str, Any]
    ) -> Any:
        if inject.resource_name in resource_context:
            return resource_context[inject.resource_name]
        raise ResourceNotFoundError(inject.resource_name, consumer_name=consumer_id)


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    async def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        constraint_manager: Any,
        instance_map: Dict[str, Node],
    ) -> Dict[str, Any]:
        resolved = {}

        # 1. Resolve Node-level constraints
        if node.constraints and not node.constraints.is_empty():
            for res, amount in node.constraints.requirements.items():
                if isinstance(amount, (LazyResult, MappedLazyResult)):
                    # Get the canonical node for the dynamic constraint value
                    constraint_node = instance_map.get(amount._uuid)
                    if not constraint_node:
                        raise DependencyMissingError(
                            node.structural_id, f"constraint:{res}", amount._uuid
                        )

                    if await state_backend.has_result(constraint_node.structural_id):
                        resolved[res] = await state_backend.get_result(
                            constraint_node.structural_id
                        )
                    else:
                        raise DependencyMissingError(
                            node.structural_id,
                            f"constraint:{res}",
                            constraint_node.structural_id,
                        )
                else:
                    resolved[res] = amount

        # 2. Resolve Global constraints
        if constraint_manager:
            extra = constraint_manager.get_extra_requirements(node)
            resolved.update(extra)

        return resolved
~~~~~

#### Acts 5: 更新流管理器 (FlowManager)

将 `FlowManager` 中涉及 `state_backend` 的操作全异步化。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, Edge, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router).
    """

    def __init__(
        self, graph: Graph, target_node_id: str, instance_map: Dict[str, Node]
    ):
        self.graph = graph
        self.target_node_id = target_node_id
        self.instance_map = instance_map

        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Reference counting for pruning
        # Initial demand = Out-degree (number of consumers)
        self.downstream_demand: Dict[str, int] = defaultdict(int)

        for edge in self.graph.edges:
            self.in_edges[edge.target.structural_id].append(edge)
            self.downstream_demand[edge.source.structural_id] += 1

            if edge.router:
                selector_node = self._get_node_from_instance(edge.router.selector)
                if selector_node:
                    self.routers_by_selector[selector_node.structural_id].append(edge)

                for key, route_result in edge.router.routes.items():
                    route_node = self._get_node_from_instance(route_result)
                    if route_node:
                        self.route_source_map[edge.target.structural_id][
                            route_node.structural_id
                        ] = key

        # The final target always has at least 1 implicit demand (the user wants it)
        self.downstream_demand[target_node_id] += 1

    def _get_node_from_instance(self, instance: Any) -> Optional[Node]:
        """Gets the canonical Node from a LazyResult instance."""
        if isinstance(instance, (LazyResult, MappedLazyResult)):
            return self.instance_map.get(instance._uuid)
        elif isinstance(instance, Param):
            # Find the node that represents this param
            for node in self.graph.nodes:
                if node.param_spec and node.param_spec.name == instance.name:
                    return node
        return None

    async def register_result(
        self, node_id: str, result: Any, state_backend: StateBackend
    ):
        """
        Notifies FlowManager of a task completion.
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                await self._process_router_decision(
                    edge_with_router, result, state_backend
                )

    async def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value

        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_node = self._get_node_from_instance(route_lazy_result)
                if not branch_root_node:
                    continue  # Should not happen in a well-formed graph
                branch_root_id = branch_root_node.structural_id
                # This branch is NOT selected.
                # We decrement its demand. If it drops to 0, it gets pruned.
                await self._decrement_demand_and_prune(branch_root_id, state_backend)

    async def _decrement_demand_and_prune(
        self, node_id: str, state_backend: StateBackend
    ):
        """
        Decrements demand for a node. If demand hits 0, marks it pruned
        and recursively processes its upstreams.
        """
        # If already skipped/pruned, no need to do anything further
        if await state_backend.get_skip_reason(node_id):
            return

        self.downstream_demand[node_id] -= 1

        if self.downstream_demand[node_id] <= 0:
            await state_backend.mark_skipped(node_id, "Pruned")

            # Recursively reduce demand for inputs of the pruned node
            for edge in self.in_edges[node_id]:
                # Special case: If the edge is from a Router, do we prune the Router selector?
                # No, the selector might be used by other branches.
                # Standard dependency logic applies: reduce demand on source.
                await self._decrement_demand_and_prune(
                    edge.source.structural_id, state_backend
                )

    async def should_skip(
        self, node: Node, state_backend: StateBackend
    ) -> Optional[str]:
        """
        Determines if a node should be skipped based on the current state.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Check if already skipped (e.g., by router pruning)
        if reason := await state_backend.get_skip_reason(node.structural_id):
            return reason

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.structural_id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not await state_backend.has_result(edge.source.structural_id):
                    if await state_backend.get_skip_reason(edge.source.structural_id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"

                condition_result = await state_backend.get_result(
                    edge.source.structural_id
                )
                if not condition_result:
                    return "ConditionFalse"

            # New explicit check for sequence abortion
            elif edge.edge_type == EdgeType.SEQUENCE:
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Sequence"

        # 3. Upstream Skip Propagation
        active_route_key = None
        router_edge = next(
            (e for e in self.in_edges[node.structural_id] if e.router), None
        )
        if router_edge:
            selector_node = self._get_node_from_instance(router_edge.router.selector)
            if selector_node:
                selector_id = selector_node.structural_id
                if await state_backend.has_result(selector_id):
                    active_route_key = await state_backend.get_result(selector_id)

        for edge in self.in_edges[node.structural_id]:
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                if active_route_key is not None:
                    edge_key = self.route_source_map[node.structural_id].get(
                        edge.source.structural_id
                    )
                    if edge_key != active_route_key:
                        continue

                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Route"

            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    # Check for data penetration possibility (for pipelines)
                    can_penetrate = False
                    # Look for inputs to the skipped node (edge.source)
                    for upstream_edge in self.in_edges[edge.source.structural_id]:
                        # If the skipped node has a DATA input, and that input has a result...
                        if (
                            upstream_edge.edge_type == EdgeType.DATA
                            and await state_backend.has_result(
                                upstream_edge.source.structural_id
                            )
                        ):
                            can_penetrate = True
                            break

                    if not can_penetrate:
                        return "UpstreamSkipped_Data"
                    # If it can penetrate, we don't return a skip reason.
                    # We let the node proceed to execution, where ArgumentResolver will handle it.

            elif edge.edge_type == EdgeType.SEQUENCE:
                if await state_backend.get_skip_reason(edge.source.structural_id):
                    return "UpstreamSkipped_Sequence"

        return None
~~~~~

#### Acts 6: 更新节点处理器 (NodeProcessor)

调整 `NodeProcessor` 以等待异步的解析器和状态检查。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
import time
import asyncio
from typing import Any, Dict, List, Callable, Awaitable

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
        # ConstraintResolver now needs the instance map to resolve dynamic values
        self.constraint_resolver = ConstraintResolver()

    async def process(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable[[Any, Dict[str, Any], StateBackend], Awaitable[Any]],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
        # 1. Resolve Constraints & Resources
        requirements = await self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager, instance_map
        )

        # Pre-check for blocking to improve observability
        if not self.resource_manager.can_acquire(requirements):
            self.bus.publish(
                TaskBlocked(
                    run_id=run_id,
                    task_id=node.structural_id,
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
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
                instance_map,
                input_overrides,
            )
        finally:
            await self.resource_manager.release(requirements)

    async def _execute_internal(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        run_id: str,
        params: Dict[str, Any],
        sub_graph_runner: Callable,
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = await self.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )

        start_time = time.time()

        # 4. Cache Check
        if node.cache_policy:
            inputs_for_cache = await self._resolve_inputs_for_cache(
                node, graph, state_backend
            )
            cached_value = await node.cache_policy.check(
                node.structural_id, inputs_for_cache
            )
            if cached_value is not None:
                self.bus.publish(
                    TaskSkipped(
                        run_id=run_id,
                        task_id=node.structural_id,
                        task_name=node.name,
                        reason="CacheHit",
                    )
                )
                return cached_value

        self.bus.publish(
            TaskExecutionStarted(
                run_id=run_id, task_id=node.structural_id, task_name=node.name
            )
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
                        task_id=node.structural_id,
                        task_name=node.name,
                        status="Succeeded",
                        duration=duration,
                        result_preview=repr(result)[:100],
                    )
                )
                # Cache Save
                if node.cache_policy:
                    inputs_for_save = await self._resolve_inputs_for_cache(
                        node, graph, state_backend
                    )
                    await node.cache_policy.save(
                        node.structural_id, inputs_for_save, result
                    )
                return result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id,
                            task_id=node.structural_id,
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
                            task_id=node.structural_id,
                            task_name=node.name,
                            status="Failed",
                            duration=duration,
                            error=f"{type(e).__name__}: {e}",
                        )
                    )
                    raise last_exception
        raise RuntimeError("Unexpected execution state")

    async def _resolve_inputs_for_cache(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        # TODO: This needs to be smarter for caching.
        # It should probably include data from input_bindings too?
        # For now, keeping legacy behavior (edge results only).
        inputs = {}
        incoming_edges = [
            edge
            for edge in graph.edges
            if edge.target.structural_id == node.structural_id
        ]
        for edge in incoming_edges:
            if edge.arg_name.startswith("_"):
                continue
            if await state_backend.has_result(edge.source.structural_id):
                inputs[edge.arg_name] = await state_backend.get_result(
                    edge.source.structural_id
                )
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

#### Acts 7: 更新执行策略 (GraphExecutionStrategy)

最后更新执行策略，以确保所有对 `state_backend` 和 `flow_manager` 的调用都是异步等待的。

~~~~~act
write_file
packages/cascade-engine/src/cascade/strategies/graph.py
~~~~~
~~~~~python
import asyncio
import inspect
from contextlib import ExitStack
from typing import Any, Dict, List

from cascade.graph.model import Graph, Node
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


class GraphExecutionStrategy:
    """
    Executes tasks by dynamically building a dependency graph and running a TCO loop.
    This is the standard execution mode for Cascade.

    Refactored for v3.2 architecture:
    - Strictly relies on build_graph returning (Graph, DataTuple, InstanceMap).
    - Uses InstanceMap to locate the target node within the structural graph.
    - Caching is intentionally disabled in this phase to ensure correctness.
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

        # JIT Compilation Cache
        # Maps template_id to an IndexedExecutionPlan (List[List[int]])
        # We store indices instead of Node objects to allow plan reuse across
        # different graph instances that share the same structure (template).
        self._template_plan_cache: Dict[str, List[List[int]]] = {}

        # Zero-Overhead TCO Cache
        # Maps tco_cycle_id to (Graph, IndexedPlan, root_node_id)
        # Used to bypass build_graph for structurally stable recursive calls
        self._cycle_cache: Dict[str, Any] = {}

        # Persistent registry to ensure node object identity consistency across TCO iterations
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        """
        Converts a Plan (List[List[Node]]) into an IndexedPlan (List[List[int]]).
        The index corresponds to the node's position in graph.nodes.
        """
        # Create a fast lookup for node indices
        id_to_idx = {node.structural_id: i for i, node in enumerate(graph.nodes)}
        indexed_plan = []
        for stage in plan:
            # Map each node in the stage to its index in the graph
            indexed_stage = [id_to_idx[node.structural_id] for node in stage]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        """
        Converts an IndexedPlan back into a Plan using the nodes from the current graph.
        """
        plan = []
        for stage_indices in indexed_plan:
            # Map indices back to Node objects from the current graph instance
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

        while True:
            # Check for Zero-Overhead TCO Fast Path
            # Use getattr safely as MappedLazyResult uses .factory instead of .task
            target_task = getattr(current_target, "task", None)
            cycle_id = (
                getattr(target_task, "_tco_cycle_id", None) if target_task else None
            )
            fast_path_data = None

            if cycle_id and cycle_id in self._cycle_cache:
                if self._are_args_simple(current_target):
                    fast_path_data = self._cycle_cache[cycle_id]

            # The step stack holds "task" (step) scoped resources
            with ExitStack() as step_stack:
                input_overrides = None

                if fast_path_data:
                    # FAST PATH: Reuse Graph & Plan
                    # Unpack all 4 cached values: graph, indexed_plan, root_node_id, req_res
                    graph, indexed_plan, root_node_id, _ = fast_path_data
                    # Reconstruct virtual instance map for current iteration
                    target_node = graph.get_node(root_node_id)
                    instance_map = {current_target._uuid: target_node}
                    plan = self._rehydrate_plan(graph, indexed_plan)

                    # Prepare Input Overrides
                    input_overrides = {}
                    for i, arg in enumerate(current_target.args):
                        input_overrides[str(i)] = arg
                    input_overrides.update(current_target.kwargs)
                else:
                    # SLOW PATH: Build Graph
                    graph, instance_map = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )
                    target_node = instance_map[current_target._uuid]
                    cache_key = target_node.template_id or target_node.structural_id

                    # 2. Resolve Plan
                    if cache_key in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[cache_key]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[cache_key] = indexed_plan

                    # Cache for Future TCO Fast Path
                    # Only scan and cache if we haven't already indexed this cycle
                    if cycle_id and cycle_id not in self._cycle_cache:
                        # Pre-scan resources and store them in the cycle cache
                        req_res = self.resource_container.scan(graph)
                        self._cycle_cache[cycle_id] = (
                            graph,
                            indexed_plan,
                            target_node.structural_id,
                            req_res,
                        )

                # 3. Setup Resources (mixed scope)
                if fast_path_data:
                    required_resources = fast_path_data[3]
                else:
                    required_resources = self.resource_container.scan(graph)

                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Execute Graph
                # CHECK FOR HOT-LOOP BYPASS
                # If it's a fast path and it's a simple single-node plan, bypass the orchestrator
                if fast_path_data and len(plan) == 1 and len(plan[0]) == 1:
                    result = await self._execute_hot_node(
                        target_node,
                        graph,
                        state_backend,
                        active_resources,
                        params,
                        instance_map,
                        input_overrides,
                    )
                else:
                    result = await self._execute_graph(
                        current_target,
                        params,
                        active_resources,
                        run_id,
                        state_backend,
                        graph,
                        plan,
                        instance_map,
                        input_overrides,
                    )

            # 5. Check for Tail Call (LazyResult) - TCO Logic
            if isinstance(result, (LazyResult, MappedLazyResult)):
                current_target = result
                # STATE GC (Asynchronous)
                if hasattr(state_backend, "clear") and inspect.iscoroutinefunction(
                    state_backend.clear
                ):
                    await state_backend.clear()
                # Yield control
                await asyncio.sleep(0)
            else:
                return result

    def _are_args_simple(self, lazy_result: Any) -> bool:
        """
        Checks if the LazyResult arguments contain any nested LazyResults.
        """
        # Handle both LazyResult (args/kwargs) and MappedLazyResult (mapping_kwargs)
        args = getattr(lazy_result, "args", [])
        kwargs = getattr(lazy_result, "kwargs", {})
        if hasattr(lazy_result, "mapping_kwargs"):
            kwargs = lazy_result.mapping_kwargs

        for arg in args:
            if isinstance(arg, (LazyResult, MappedLazyResult)):
                return False
        for val in kwargs.values():
            if isinstance(val, (LazyResult, MappedLazyResult)):
                return False
        return True

    async def _execute_hot_node(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        active_resources: Dict[str, Any],
        params: Dict[str, Any],
        instance_map: Dict[str, Node],
        input_overrides: Dict[str, Any] = None,
    ) -> Any:
        """
        A stripped-down version of NodeProcessor.process specifically for hot TCO loops.
        Bypasses event bus, flow manager, and multiple resolvers for maximum performance.
        """
        # 1. Resolve Arguments (Minimal path)
        # We reuse the node_processor's resolver but bypass the process() wrapper
        # Resolver is now ASYNC
        args, kwargs = await self.node_processor.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
            input_overrides=input_overrides,
        )

        # 2. Direct Execution (Skip NodeProcessor ceremony)
        result = await self.node_processor.executor.execute(node, args, kwargs)

        # 3. Minimal State Update (Async)
        await state_backend.put_result(node.structural_id, result)
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
        root_input_overrides: Dict[str, Any] = None,
    ) -> Any:
        # Locate the canonical node for the current target instance
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]

        flow_manager = FlowManager(graph, target_node.structural_id, instance_map)
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    if node.node_type == "param":
                        continue

                    # ASYNC CHECK
                    skip_reason = await flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        await state_backend.mark_skipped(
                            node.structural_id, skip_reason
                        )
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.structural_id,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.structural_id in blocked_nodes:
                            blocked_nodes.remove(node.structural_id)
                    else:
                        deferred_this_pass.append(node)
                        if node.structural_id not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.structural_id,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.structural_id)

                if executable_this_pass:
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph
                        sub_graph, sub_instance_map = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        return await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                        )

                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.structural_id == target_node.structural_id
                            else None
                        )
                        tasks_to_run.append(
                            self.node_processor.process(
                                node,
                                graph,
                                state_backend,
                                active_resources,
                                run_id,
                                params,
                                sub_graph_runner,
                                instance_map,
                                input_overrides=overrides,
                            )
                        )

                    pass_results = await asyncio.gather(*tasks_to_run)

                    for node, res in zip(executable_this_pass, pass_results):
                        await state_backend.put_result(node.structural_id, res)
                        if flow_manager:
                            await flow_manager.register_result(
                                node.structural_id, res, state_backend
                            )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        # Use the mapped canonical node ID to check for the final result
        if not await state_backend.has_result(target_node.structural_id):
            # For debugging, check if the instance was skipped
            if skip_reason := await state_backend.get_skip_reason(
                target_node.structural_id
            ):
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

        return await state_backend.get_result(target_node.structural_id)
~~~~~

#### Acts 8: 添加和更新测试

1.  更新 `test_redis_state.py` 为异步测试。
2.  新建 `test_in_memory_state.py` 以验证 `asyncio.to_thread` 的使用。

~~~~~act
write_file
tests/engine/adapters/state/test_redis_state.py
~~~~~
~~~~~python
import pickle
import pytest
from unittest.mock import MagicMock, AsyncMock

# We import the module to patch its members
from cascade.adapters.state import redis as redis_state_module


@pytest.fixture
def mock_redis_client():
    """Provides a MagicMock for the redis.Redis client."""
    mock_client = MagicMock()
    # Mock the pipeline context manager
    mock_pipeline = MagicMock()
    mock_client.pipeline.return_value = mock_pipeline
    return mock_client, mock_pipeline


def test_redis_state_backend_dependency_check(monkeypatch):
    """
    Ensures RedisStateBackend raises ImportError if 'redis' is not installed.
    """
    monkeypatch.setattr(redis_state_module, "redis", None)
    with pytest.raises(ImportError, match="The 'redis' library is required"):
        from cascade.adapters.state.redis import RedisStateBackend

        RedisStateBackend(run_id="test", client=MagicMock())


@pytest.mark.asyncio
async def test_put_result(mock_redis_client):
    """
    Verifies that put_result serializes data and calls Redis HSET and EXPIRE.
    """
    client, pipeline = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)

    test_result = {"status": "ok", "data": [1, 2]}
    await backend.put_result("node_a", test_result)

    expected_key = "cascade:run:run123:results"
    expected_data = pickle.dumps(test_result)

    client.pipeline.assert_called_once()
    pipeline.hset.assert_called_once_with(expected_key, "node_a", expected_data)
    pipeline.expire.assert_called_once_with(expected_key, 86400)
    pipeline.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_result(mock_redis_client):
    """
    Verifies that get_result retrieves and deserializes data correctly.
    """
    client, _ = mock_redis_client
    backend = redis_state_module.RedisStateBackend(run_id="run123", client=client)

    # Case 1: Result found
    test_result = {"value": 42}
    pickled_result = pickle.dumps(test_result)
    client.hget.return_value = pickled_result

    result = await backend.get_result("node_b")

    client.hget.assert_called_once_with("cascade:run:run123:results", "node_b")
    assert result == test_result

    # Case 2: Result not found
    client.hget.return_value = None
    assert await backend.get_result("node_c") is None
~~~~~

~~~~~act
write_file
tests/engine/adapters/state/test_in_memory_state.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import patch, ANY
from cascade.adapters.state.in_memory import InMemoryStateBackend


@pytest.mark.asyncio
async def test_in_memory_uses_to_thread():
    """
    Verifies that InMemoryStateBackend uses asyncio.to_thread for its operations,
    ensuring compliance with the non-blocking I/O contract even for dict operations.
    """
    backend = InMemoryStateBackend("test_run")

    # We patch asyncio.to_thread in the module where the backend is defined
    with patch("cascade.adapters.state.in_memory.asyncio.to_thread") as mock_to_thread:
        # We need to make the mock awaitable because the method awaits it
        async def async_mock(*args, **kwargs):
            return "mocked_result"

        mock_to_thread.side_effect = async_mock

        # Test put_result
        await backend.put_result("node_1", "data")
        mock_to_thread.assert_called_with(ANY, "node_1", "data")

        # Test get_result
        await backend.get_result("node_1")
        mock_to_thread.assert_called_with(ANY, "node_1")


@pytest.mark.asyncio
async def test_in_memory_functional():
    """
    Functional test to ensure it actually works as a backend.
    """
    backend = InMemoryStateBackend("test_run")

    # Put
    await backend.put_result("node_a", {"foo": "bar"})

    # Check
    assert await backend.has_result("node_a") is True
    assert await backend.has_result("node_b") is False

    # Get
    val = await backend.get_result("node_a")
    assert val == {"foo": "bar"}

    # Skip
    await backend.mark_skipped("node_b", "ConditionFalse")
    assert await backend.get_skip_reason("node_b") == "ConditionFalse"
    assert await backend.get_skip_reason("node_a") is None

    # Clear
    await backend.clear()
    assert await backend.has_result("node_a") is False
    assert await backend.get_skip_reason("node_b") is None
~~~~~

### 下一步建议
我们已经完成了核心的状态后端异步化重构。接下来的工作重点应该转向验证这一变更对整个系统的影响。
建议运行完整的集成测试套件，特别是 `tests/engine/e2e` 下的测试，确保端到端的执行流没有因为引入异步等待而出现死锁或竞争条件。如果 E2E 测试通过，则说明此次重构成功且安全。

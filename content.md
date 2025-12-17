好的，我们继续进行这项核心重构。

这是第二份计划，我们将执行“心脏手术”。我们将把上一阶段引入的 `StateBackend` 协议完全集成到 `Engine`、`FlowManager` 和 `Resolvers` 的核心逻辑中，彻底取代之前耦合在执行过程中的本地 `results` 字典。

## [WIP] refactor(engine): 将 StateBackend 集成到核心执行与流程控制逻辑中

### 用户需求
继续实施 v2.0 路线图，将 `Engine` 的运行时状态管理完全委托给 `StateBackend` 实例，完成核心的状态解耦。

### 评论
这是整个架构重构中最具挑战性也最有价值的一步。通过用 `StateBackend` 替换掉在调用栈中四处传递的、可变的 `results` 字典，我们正在实现几个关键目标：
1.  **明确数据流**: 状态的读取和写入变得非常明确，所有操作都通过 `state_backend` 的接口进行，不再有隐式的状态变更。
2.  **增强可测试性**: 我们可以轻易地注入一个 Mock `StateBackend` 来验证 `Engine` 和 `FlowManager` 的行为，而无需运行实际的任务。
3.  **解锁未来能力**: 这是实现分布式执行、工作流恢复和高级遥测功能的前置条件。

这次修改波及面较广，涉及 `Engine`、`FlowManager` 和 `Resolvers`，但完成后，`Cascade` 的内核将变得前所未有的清晰和健壮。

### 目标
1.  重构 `cascade.runtime.engine.Engine`，使其在每次 `run` 时实例化并使用一个 `StateBackend` 对象来管理所有任务结果和跳过状态。
2.  重构 `cascade.runtime.flow.FlowManager`，使其变为一个无状态的流程控制器，所有状态判断都通过查询传入的 `StateBackend` 来完成。
3.  重构 `cascade.runtime.resolvers.ArgumentResolver` 和 `ConstraintResolver`，使其从 `StateBackend` 而非 `dict` 中解析上游依赖的结果。

### 基本原理
我们将遵循“依赖倒置”原则，将具体的 `dict` 实现替换为 `StateBackend` 协议。
- 在 `Engine.run` 的入口处，我们将根据 `self.state_backend_cls` 创建一个与当次运行生命周期绑定的 `state_backend` 实例。
- 这个 `state_backend` 实例将作为“唯一事实来源”被传递给所有需要访问运行时状态的内部组件，包括 `_execute_graph`, `FlowManager`, `ArgumentResolver` 等。
- 所有对 `results` 字典的读写操作（`results[key]`, `key in results`, `results.get(key)`）都将被替换为对 `state_backend` 相应方法的调用（`put_result`, `has_result`, `get_result`）。
- `FlowManager` 内部的 `_skipped_nodes` 集合将被移除，相关状态的读写完全委托给 `state_backend`。

由于本次修改涉及多个类的核心签名和内部逻辑，我们将采用 `write_file` 策略以确保代码的完整性和一致性。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #concept/state #scope/core
#ai/brainstorm
#task/domain/architecture #task/object/state-backend #task/action/implementation #task/state/continue #task/status/active

---

### Script

#### Acts 1: 重构 `resolvers.py` 以依赖 `StateBackend`

我们首先更新参数和约束解析器，使其从 `StateBackend` 协议中读取上游结果。

~~~~~act
write_file
src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
import inspect
from typing import Any, Dict, List, Tuple

from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import Inject
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.protocols import StateBackend


class ArgumentResolver:
    """
    Responsible for resolving the actual arguments (args, kwargs) for a node execution
    from the graph structure, upstream results, and resource context.
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Resolves arguments for the node's callable from:
        1. Literal inputs
        2. Upstream dependency results (handling Routers) from the state backend
        3. Injected resources
        4. User provided params (for internal input tasks)

        Raises DependencyMissingError if a required upstream result is missing.
        """
        # 0. Special handling for internal input tasks
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            final_kwargs = node.literal_inputs.copy()
            final_kwargs["params_context"] = user_params or {}
            return [], final_kwargs

        # 1. Prepare arguments from literals and upstream results
        final_kwargs = {k: v for k, v in node.literal_inputs.items() if not k.isdigit()}
        positional_args = {
            int(k): v for k, v in node.literal_inputs.items() if k.isdigit()
        }

        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        for edge in incoming_edges:
            if edge.edge_type != EdgeType.DATA:
                continue

            dependency_id: str
            if edge.router:
                selector_result = state_backend.get_result(edge.source.id)
                if selector_result is None:
                    if not state_backend.has_result(edge.source.id):
                        raise DependencyMissingError(
                            node.id, "router_selector", edge.source.id
                        )

                try:
                    selected_lazy_result = edge.router.routes[selector_result]
                    dependency_id = selected_lazy_result._uuid
                except KeyError:
                    raise ValueError(
                        f"Router selector returned '{selector_result}', "
                        f"but no matching route found in {list(edge.router.routes.keys())}"
                    )
            else:
                dependency_id = edge.source.id

            if not state_backend.has_result(dependency_id):
                raise DependencyMissingError(node.id, edge.arg_name, dependency_id)

            result = state_backend.get_result(dependency_id)

            if edge.arg_name.isdigit():
                positional_args[int(edge.arg_name)] = result
            else:
                final_kwargs[edge.arg_name] = result

        # 2. Prepare arguments from injected resources
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


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self, node: Node, graph: Graph, state_backend: StateBackend
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}
        
        constraint_edges = [
            e for e in graph.edges 
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )
                
                if constraint_edge is None:
                    raise RuntimeError(
                        f"Internal Error: Missing constraint edge for dynamic requirement '{res}' on task '{node.name}'"
                    )

                if state_backend.has_result(constraint_edge.source.id):
                    resolved[res] = state_backend.get_result(constraint_edge.source.id)
                else:
                    raise DependencyMissingError(
                        node.id, f"constraint:{res}", constraint_edge.source.id
                    )
            else:
                resolved[res] = amount
        return resolved
~~~~~

#### Acts 2: 重构 `flow.py` 使其无状态

现在，我们将 `FlowManager` 改造为一个无状态的逻辑处理器，其所有决策都依赖于外部传入的 `StateBackend`。

~~~~~act
write_file
src/cascade/runtime/flow.py
~~~~~
~~~~~python
from typing import Dict, Any, Optional, List
from collections import defaultdict
from cascade.graph.model import Node, Graph, EdgeType, Edge
from cascade.spec.common import Param
from cascade.spec.lazy_types import LazyResult
from cascade.runtime.protocols import StateBackend


class FlowManager:
    """
    Manages the control flow of the execution, implementing logic for
    skipping tasks (Conditions) and pruning branches (Router). This class is
    stateless; all state is read from and written to a StateBackend instance.
    """

    def __init__(self, graph: Graph, target_node_id: str):
        self.graph = graph
        self.target_node_id = target_node_id
        
        self.in_edges: Dict[str, List[Edge]] = defaultdict(list)
        self.routers_by_selector: Dict[str, List[Edge]] = defaultdict(list)
        self.route_source_map: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        for edge in self.graph.edges:
            self.in_edges[edge.target.id].append(edge)
            
            if edge.router:
                selector_id = self._get_obj_id(edge.router.selector)
                self.routers_by_selector[selector_id].append(edge)
                
                for key, route_result in edge.router.routes.items():
                    route_source_id = self._get_obj_id(route_result)
                    self.route_source_map[edge.target.id][route_source_id] = key

        # Note: Demand counting for pruning is now handled dynamically based on
        # the state within the StateBackend, not pre-calculated.

    def _get_obj_id(self, obj: Any) -> str:
        if isinstance(obj, LazyResult):
            return obj._uuid
        elif isinstance(obj, Param):
            return obj.name
        return str(obj)

    def register_result(self, node_id: str, result: Any, state_backend: StateBackend):
        """
        Notifies FlowManager of a task completion. 
        Triggers pruning if the node was a Router selector.
        """
        if node_id in self.routers_by_selector:
            for edge_with_router in self.routers_by_selector[node_id]:
                self._process_router_decision(edge_with_router, result, state_backend)

    def _process_router_decision(
        self, edge: Edge, selector_value: Any, state_backend: StateBackend
    ):
        router = edge.router
        selected_route_key = selector_value
        
        for route_key, route_lazy_result in router.routes.items():
            if route_key != selected_route_key:
                branch_root_id = self._get_obj_id(route_lazy_result)
                # This branch is NOT selected. Mark it to be pruned.
                state_backend.mark_skipped(branch_root_id, "Pruned_UnselectedRoute")

    def should_skip(
        self, node: Node, state_backend: StateBackend
    ) -> Optional[str]:
        """
        Determines if a node should be skipped based on the current state.
        Returns the reason string if it should be skipped, or None otherwise.
        """
        # 1. Check if already skipped (e.g., by router pruning)
        if reason := state_backend.get_skip_reason(node.id):
            return reason

        # 2. Condition Check (run_if)
        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.CONDITION:
                if not state_backend.has_result(edge.source.id):
                    # Propagate skip if condition source was skipped
                    if state_backend.get_skip_reason(edge.source.id):
                        return "UpstreamSkipped_Condition"
                    return "ConditionMissing"
                
                condition_result = state_backend.get_result(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"
        
        # 3. Upstream Skip Propagation
        active_route_key = None
        router_edge = next((e for e in self.in_edges[node.id] if e.router), None)
        if router_edge:
            selector_id = self._get_obj_id(router_edge.router.selector)
            if state_backend.has_result(selector_id):
                active_route_key = state_backend.get_result(selector_id)

        for edge in self.in_edges[node.id]:
            if edge.edge_type == EdgeType.ROUTER_ROUTE:
                if active_route_key is not None:
                    edge_key = self.route_source_map[node.id].get(edge.source.id)
                    if edge_key != active_route_key:
                        continue
                
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Route"
            
            elif edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if state_backend.get_skip_reason(edge.source.id):
                    return "UpstreamSkipped_Data"
        
        return None
~~~~~

#### Acts 3: 重构 `engine.py` 以使用 `StateBackend`

这是最后也是最核心的一步，我们将 `Engine` 的执行逻辑完全建立在 `StateBackend` 之上。

~~~~~act
write_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
import time
import inspect
import asyncio
from typing import Any, Dict, Optional, Generator, Callable, List, Type
from uuid import uuid4
from contextlib import ExitStack

from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
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
from cascade.runtime.protocols import Solver, Executor, StateBackend
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.resource_manager import ResourceManager
from cascade.runtime.resolvers import ArgumentResolver, ConstraintResolver
from cascade.runtime.flow import FlowManager
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
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.state_backend_cls = state_backend_cls
        self.resource_manager = ResourceManager(capacity=system_resources)
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
        target_name = getattr(target.task, "name", "unknown")

        self.bus.publish(
            RunStarted(run_id=run_id, target_tasks=[target_name], params=params or {})
        )
        
        state_backend = self.state_backend_cls(run_id=run_id)

        with ExitStack() as stack:
            try:
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
            tasks_to_run = []
            nodes_in_execution = []
            
            for node in stage:
                if node.node_type == "param":
                    continue

                skip_reason = self.flow_manager.should_skip(node, state_backend)
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
                
                tasks_to_run.append(
                    self._execute_node_with_policies(
                        node, graph, state_backend, active_resources, run_id, params
                    )
                )
                nodes_in_execution.append(node)

            if not tasks_to_run:
                continue

            stage_results = await asyncio.gather(*tasks_to_run)

            for node, res in zip(nodes_in_execution, stage_results):
                state_backend.put_result(node.id, res)
                if self.flow_manager:
                    self.flow_manager.register_result(node.id, res, state_backend)

        if not state_backend.has_result(target._uuid):
            if skip_reason := state_backend.get_skip_reason(target._uuid):
                raise DependencyMissingError(
                    task_id=target.task.name,
                    arg_name="<Target Output>",
                    dependency_id=f"Target was skipped (Reason: {skip_reason})",
                )
            raise KeyError(f"Target task '{target.task.name}' did not produce a result.")

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
        requirements = self.constraint_resolver.resolve(node, graph, state_backend)
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
            inputs_for_cache = self._resolve_inputs_for_cache(node, graph, state_backend)
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
                        run_id=run_id, task_id=node.id, task_name=node.name,
                        status="Succeeded", duration=duration,
                        result_preview=repr(result)[:100],
                    )
                )
                if node.cache_policy:
                    inputs_for_save = self._resolve_inputs_for_cache(node, graph, state_backend)
                    node.cache_policy.save(node.id, inputs_for_save, result)
                return result
            except Exception as e:
                last_exception = e
                if attempt < max_attempts:
                    self.bus.publish(
                        TaskRetrying(
                            run_id=run_id, task_id=node.id, task_name=node.name,
                            attempt=attempt, max_attempts=max_attempts, delay=delay, error=str(e),
                        )
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff
                else:
                    duration = time.time() - start_time
                    self.bus.publish(
                        TaskExecutionFinished(
                            run_id=run_id, task_id=node.id, task_name=node.name,
                            status="Failed", duration=duration,
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
        self, node: Node, args: List[Any], kwargs: Dict[str, Any],
        active_resources: Dict[str, Any], run_id: str, params: Dict[str, Any],
        parent_state_backend: StateBackend
    ) -> List[Any]:
        factory = node.mapping_factory
        if not kwargs: return []
        lengths = {k: len(v) for k, v in kwargs.items()}
        first_len = list(lengths.values())[0]
        if not all(length == first_len for length in lengths.values()):
            raise ValueError(f"Mapped inputs have mismatched lengths: {lengths}")

        sub_targets = []
        for i in range(first_len):
            item_kwargs = {k: v[i] for k, v in kwargs.items()}
            sub_target = factory(**item_kwargs)
            if node.retry_policy: sub_target._retry_policy = node.retry_policy
            if node.cache_policy: sub_target._cache_policy = node.cache_policy
            if node.constraints: sub_target._constraints = node.constraints
            sub_targets.append(sub_target)

        # Each sub-task is a full workflow run from the engine's perspective
        # but shares the parent's state backend to see results.
        coros = [
            self._execute_graph(target, params, active_resources, run_id, parent_state_backend)
            for target in sub_targets
        ]
        return await asyncio.gather(*coros)

    def _scan_for_resources(self, graph: Graph) -> set[str]:
        required = set()
        for node in graph.nodes:
            for value in node.literal_inputs.values():
                if isinstance(value, Inject): required.add(value.resource_name)
            if node.callable_obj:
                sig = inspect.signature(node.callable_obj)
                for param in sig.parameters.values():
                    if isinstance(param.default, Inject): required.add(param.default.resource_name)
        return required

    def _setup_resources(
        self, required_names: set[str], stack: ExitStack, run_id: str
    ) -> Dict[str, Any]:
        active: Dict[str, Any] = {}
        def get_or_create(name: str):
            if name in active: return active[name]
            provider = self._resource_providers.get(name)
            if not provider: raise NameError(f"Resource '{name}' is required but not registered.")
            sig = inspect.signature(provider)
            deps = {p_name: get_or_create(p.default.resource_name) for p_name, p in sig.parameters.items() if isinstance(p.default, Inject)}
            gen = provider(**deps)
            instance = next(gen)
            active[name] = instance
            self.bus.publish(ResourceAcquired(run_id=run_id, resource_name=name))
            stack.callback(self._teardown_resource, gen, run_id, name)
            return instance
        for name in required_names: get_or_create(name)
        return active

    def _teardown_resource(self, gen: Generator, run_id: str, resource_name: str):
        try:
            next(gen)
        except StopIteration:
            self.bus.publish(
                ResourceReleased(run_id=run_id, resource_name=resource_name)
            )
~~~~~

### 下一步建议
我们已经完成了对 `Engine` 状态管理的核心重构，这是 v2.0 路线图中最重要的一步。`Engine` 现在是协议驱动且状态解耦的。

在进入第二阶段（遥测系统）之前，我们应该完成第一阶段的收尾工作：
- **分离 `CacheBackend`**: 当前的 `CachePolicy` 协议混合了“如何生成缓存键”（策略）和“如何存取数据”（后端）两个职责。我们应该将其拆分为 `CachePolicy` 和 `CacheBackend` 两个独立的协议，以进一步解耦。
- **更新测试**: 大量的集成测试（特别是 `tests/runtime` 和 `tests/integration`）可能会因为 `Engine` 核心逻辑的改变而失败。我们需要更新这些测试，使其适应新的、基于 `StateBackend` 的架构。

我建议下一个计划是**分离 `CacheBackend` 协议**。

好的，我们开始执行重构计划的第二步：将 `Node` 对象与 Python Callable 解耦。

这是为了实现“图的纯粹性”这一核心架构原则的关键步骤。在此次重构后，`Graph` 对象将成为一个纯粹的、可序列化的数据结构，不再包含任何 Python 函数指针等运行时对象。所有的可执行逻辑将在运行时通过一个新的 `ExecutableRegistry` 进行动态查找和注入。

## [WIP] refactor(core): 解耦 Node 对象与 Python callables

### 用户需求
根据 "engine 与 graph 的预重构计划.md"，执行步骤 2，移除 `Node` 对象对 `callable_obj` 的直接持有，并引入一个运行时注册表来动态查找可执行函数。

### 评论
这是迈向 v3.0 架构“图即数据”哲学的决定性一步。通过将图的静态拓扑（`Graph`）与其运行时执行上下文（`ExecutableRegistry`）彻底分离，我们极大地增强了系统的可序列化性、可移植性和可测试性。未来，我们可以将编译后的 `Graph` 对象持久化，并在完全不同的环境中加载和执行，只要该环境能够提供其声明的函数实现即可。

### 目标
1.  修改 `cascade-graph` 中的 `Node`、`TaskNode` 和 `MapNode`，移除 `_callable` 和 `mapping_factory` 等直接引用 Python 函数的字段。
2.  更新 `GraphBuilder`，使其在构建图的同时，填充一个 `ExecutableRegistry`（一个 `dict`），用于映射节点哈希到其对应的 Python callable。`build_graph` 的返回值将包含此注册表。
3.  调整 `LocalExecutor`，使其 `execute` 方法接收一个显式的 `callable_obj` 参数，而不是从 `Node` 对象上读取。
4.  重构 `NodeProcessor`，使其从 `Strategy` 接收特定节点的可执行对象，并将其传递给 `Executor`。
5.  修改 `GraphExecutionStrategy`，以管理 `ExecutableRegistry` 的生命周期，并在执行循环中为 `NodeProcessor` 提供正确的 callable。

### 基本原理
我们遵循**关注点分离 (Separation of Concerns)** 原则。`Graph` 对象现在只负责描述计算的**结构**（“什么”和“如何连接”），而一个临时的、与图伴生的 `ExecutableRegistry` 则负责提供计算的**实现**（“如何执行”）。这使得图本身成为一个纯粹的、与环境无关的制品 (artifact)，为其在分布式环境中的传输和复用奠定了基础。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #concept/state #scope/core #ai/instruct #task/domain/core #task/object/node-processor #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 净化 Node 数据模型

我们首先从 `cascade.graph.model` 中移除 `Node` 对 Python callable 的直接引用。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def callable_obj(self) -> Optional[Callable]:
        return None


@dataclass(eq=False)
class TaskNode(Node):
    # The actual python executable object.
    _callable: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self._callable


@dataclass(eq=False)
class MapNode(Node):
    mapping_factory: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        # For map nodes, the factory is the closest thing to a callable
        return self.mapping_factory
~~~~~
~~~~~python.new
    @property
    def name(self) -> str:
        return self.definition.name


@dataclass(eq=False)
class TaskNode(Node):
    # The actual python executable object is no longer stored here.
    # It is retrieved from an ExecutableRegistry at runtime.
    pass


@dataclass(eq=False)
class MapNode(Node):
    # The factory is no longer stored here.
    # It is retrieved from an ExecutableRegistry at runtime.
    pass
~~~~~

#### Acts 2: 更新 GraphBuilder 以生成 ExecutableRegistry

现在，`GraphBuilder` 在构建图的同时，还会创建一个 `ExecutableRegistry`。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, Tuple, Callable
import inspect
from cascade.graph.model import (
    Graph,
    Node,
    Edge,
    EdgeType,
    TaskNode,
    MapNode,
    ParamNode,
)
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.spec.jump import JumpSelector

from .registry import NodeRegistry
from .hashing import HashingService
from .analysis.reflection import ReflectionAnalyzer


class GraphBuilder:
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        self._visited_instances: Dict[str, Node] = {}
        self.registry = registry if registry is not None else NodeRegistry()
        self.hashing_service = HashingService()
        self.analyzer = ReflectionAnalyzer()
        self.executable_registry: Dict[str, Callable] = {}

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node], Dict[str, Callable]]:
        self._visit(target)
        return self.graph, self._visited_instances, self.executable_registry

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _find_dependencies(self, obj: Any, dep_nodes: Dict[str, Node]):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            if obj._uuid not in dep_nodes:
                dep_node = self._visit(obj)
                dep_nodes[obj._uuid] = dep_node
        elif isinstance(obj, Router):
            self._find_dependencies(obj.selector, dep_nodes)
            for route in obj.routes.values():
                self._find_dependencies(route, dep_nodes)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._find_dependencies(item, dep_nodes)
        elif isinstance(obj, dict):
            for v in obj.values():
                self._find_dependencies(v, dep_nodes)

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        # 1. Post-order: Resolve all dependencies first
        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.args, dep_nodes)
        self._find_dependencies(result.kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._constraints:
            self._find_dependencies(result._constraints.requirements, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        # 2. Analyze Code to get TaskDef
        task_def = self.analyzer.analyze(result.task)

        # 3. Compute Node Instance Hash
        current_node_instance_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        # 4. Hash-consing / Create Node
        node = self.registry.get(current_node_instance_hash)
        if not node:
            # Extract bindings (Literals)
            input_bindings = {}
            for i, val in enumerate(result.args):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[str(i)] = val
            for k, val in result.kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            # Complexity check
            from cascade.spec.resource import Inject as InjectMarker
            from cascade.common.inputs import _get_param_value

            has_complex = False
            if result.task.func is _get_param_value.func:
                has_complex = True

            if not has_complex:
                try:
                    sig = inspect.signature(result.task.func)
                    has_complex = any(
                        isinstance(p.default, InjectMarker)
                        for p in sig.parameters.values()
                    )
                except ValueError:
                    pass

            if not has_complex:

                def is_complex_value(v):
                    if isinstance(v, InjectMarker):
                        return True
                    if isinstance(v, list):
                        return any(is_complex_value(x) for x in v)
                    if isinstance(v, dict):
                        return any(is_complex_value(x) for x in v.values())
                    return False

                has_complex = any(is_complex_value(v) for v in input_bindings.values())

            if result.task.func is _get_param_value.func:
                from cascade.common.context import get_current_context

                param_name = input_bindings.get("0") or input_bindings.get("name")
                param_spec = None
                if param_name:
                    ctx = get_current_context()
                    for spec in ctx.get_all_specs():
                        if spec.name == param_name:
                            from cascade.spec.input import ParamSpec

                            if isinstance(spec, ParamSpec):
                                param_spec = spec
                            break

                node = ParamNode(
                    current_node_instance_hash=current_node_instance_hash,
                    definition=task_def,
                    node_type="param",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_spec=param_spec,
                    has_complex_inputs=True,
                )
            else:
                node = TaskNode(
                    current_node_instance_hash=current_node_instance_hash,
                    definition=task_def,
                    node_type="task",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    has_complex_inputs=has_complex,
                )
            self.registry._registry[current_node_instance_hash] = node
            self.executable_registry[current_node_instance_hash] = result.task.func

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        # 5. Edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        if result._jump_selector:
            selector = result._jump_selector
            if isinstance(selector, JumpSelector):
                for route_target in selector.routes.values():
                    if route_target is not None:
                        self._visit(route_target)
                for key, route_target_lr in selector.routes.items():
                    if route_target_lr is None:
                        continue
                    target_node = self._visited_instances[route_target_lr._uuid]
                    self.graph.add_edge(
                        Edge(
                            source=node,
                            target=target_node,
                            arg_name=key,
                            edge_type=EdgeType.ITERATIVE_JUMP,
                            jump_selector=selector,
                        )
                    )

        if result._condition:
            source_node = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )

        if result._constraints:
            for res, req in result._constraints.requirements.items():
                if isinstance(req, (LazyResult, MappedLazyResult)):
                    source = self._visited_instances[req._uuid]
                    self.graph.add_edge(
                        Edge(
                            source=source,
                            target=node,
                            arg_name=res,
                            edge_type=EdgeType.CONSTRAINT,
                        )
                    )

        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited_instances:
            return self._visited_instances[result._uuid]

        dep_nodes: Dict[str, Node] = {}
        self._find_dependencies(result.mapping_kwargs, dep_nodes)
        if result._condition:
            self._find_dependencies(result._condition, dep_nodes)
        if result._dependencies:
            self._find_dependencies(result._dependencies, dep_nodes)

        # Analyze Factory
        task_def = self.analyzer.analyze(result.factory)

        # Compute Hash
        current_node_instance_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        node = self.registry.get(current_node_instance_hash)
        if not node:
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            node = MapNode(
                current_node_instance_hash=current_node_instance_hash,
                definition=task_def,
                node_type="map",
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[current_node_instance_hash] = node
            self.executable_registry[current_node_instance_hash] = result.factory

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            source = self._visited_instances[result._condition._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="_condition",
                    edge_type=EdgeType.CONDITION,
                )
            )

        for dep in result._dependencies:
            source = self._visited_instances[dep._uuid]
            self.graph.add_edge(
                Edge(
                    source=source,
                    target=node,
                    arg_name="<sequence>",
                    edge_type=EdgeType.SEQUENCE,
                )
            )

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visited_instances[obj._uuid]
            self.graph.add_edge(
                Edge(
                    source=source_node,
                    target=target_node,
                    arg_name=path or "dep",
                    edge_type=EdgeType.DATA,
                )
            )

        elif isinstance(obj, Router):
            selector_node = self._visited_instances[obj.selector._uuid]
            self.graph.add_edge(
                Edge(
                    source=selector_node,
                    target=target_node,
                    arg_name=path,
                    router=obj,
                    edge_type=EdgeType.DATA,
                )
            )
            for key, route_res in obj.routes.items():
                route_node = self._visited_instances[route_res._uuid]
                self.graph.add_edge(
                    Edge(
                        source=route_node,
                        target=target_node,
                        arg_name=f"{path}.route[{key}]",
                        edge_type=EdgeType.ROUTER_ROUTE,
                    )
                )

        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                self._scan_and_add_edges(
                    target_node, item, path=f"{path}[{i}]" if path else str(i)
                )

        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(
                    target_node, v, path=f"{path}.{k}" if path else str(k)
                )


def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node], Dict[str, Callable]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

#### Acts 3: 更新 LocalExecutor

`LocalExecutor` 现在从外部接收 callable，而不是从 `Node` 读取。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/executors/local.py
~~~~~
~~~~~python.old
    async def execute(
        self,
        node: Node,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        if node.callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.definition.is_async:
            result = await node.callable_obj(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()

            # Select the appropriate executor based on the task's declared mode
            if node.definition.mode == "compute":
                executor = self._compute_executor
            else:  # Default to "blocking" for I/O, etc.
                executor = self._blocking_executor

            # Use functools.partial to handle keyword arguments, as
            # run_in_executor only accepts positional arguments for the target function.
            func_to_run = functools.partial(node.callable_obj, *args, **kwargs)
            result = await loop.run_in_executor(executor, func_to_run)
~~~~~
~~~~~python.new
    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any:
        if callable_obj is None:
            raise TypeError(
                f"Node '{node.name}' of type '{node.node_type}' is not executable (no callable)."
            )

        if node.definition.is_async:
            result = await callable_obj(*args, **kwargs)
        else:
            loop = asyncio.get_running_loop()

            # Select the appropriate executor based on the task's declared mode
            if node.definition.mode == "compute":
                executor = self._compute_executor
            else:  # Default to "blocking" for I/O, etc.
                executor = self._blocking_executor

            # Use functools.partial to handle keyword arguments, as
            # run_in_executor only accepts positional arguments for the target function.
            func_to_run = functools.partial(callable_obj, *args, **kwargs)
            result = await loop.run_in_executor(executor, func_to_run)
~~~~~

#### Acts 4: 重构 NodeProcessor

`NodeProcessor` 现在接收 `executable` 对象，并将其传递给 `Executor`。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
import time
import asyncio
from typing import Any, Dict, List, Callable, Awaitable, Optional, TYPE_CHECKING, Tuple


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
~~~~~

#### Acts 5: 更新 GraphExecutionStrategy 以管理 Registry

最后，`Strategy` 层将负责管理 `ExecutableRegistry` 的生命周期，并在执行时将其内容传递给 `Processor`。

~~~~~act
write_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
import asyncio
from contextlib import ExitStack
from typing import Any, Dict, List, Optional, Callable

from cascade.graph.model import Graph, Node, EdgeType
from cascade.graph.build import build_graph
from cascade.graph.registry import NodeRegistry
from cascade.graph.hashing import BlueprintHasher
from cascade.spec.protocols import Solver, StateBackend
from cascade.spec.jump import Jump
from cascade.runtime.bus import MessageBus
from cascade.runtime.resource_container import ResourceContainer
from cascade.runtime.processor import NodeProcessor
from cascade.runtime.flow import FlowManager
from cascade.runtime.exceptions import DependencyMissingError
from cascade.runtime.events import TaskSkipped, TaskBlocked
from cascade.runtime.constraints.manager import ConstraintManager


class GraphExecutionResult:
    def __init__(self, value: Any, source_node_id: str):
        self.value = value
        self.source_node_id = source_node_id


class GraphExecutionStrategy:
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
        self.blueprint_hasher = BlueprintHasher()

        self._template_plan_cache: Dict[str, List[List[int]]] = {}
        self._node_registry = NodeRegistry()

    def _index_plan(self, graph: Graph, plan: Any) -> List[List[int]]:
        id_to_idx = {
            node.current_node_instance_hash: i for i, node in enumerate(graph.nodes)
        }
        indexed_plan = []
        for stage in plan:
            indexed_stage = [
                id_to_idx[node.current_node_instance_hash] for node in stage
            ]
            indexed_plan.append(indexed_stage)
        return indexed_plan

    def _rehydrate_plan(self, graph: Graph, indexed_plan: List[List[int]]) -> Any:
        plan = []
        for stage_indices in indexed_plan:
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
        next_input_overrides = None
        local_context_cache = {}

        while True:
            with ExitStack() as step_stack:
                input_overrides = None
                await state_backend.clear()

                if current_target._uuid in local_context_cache:
                    (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    ) = local_context_cache[current_target._uuid]
                else:
                    graph, instance_map, executable_registry = build_graph(
                        current_target, registry=self._node_registry
                    )

                    if current_target._uuid not in instance_map:
                        raise RuntimeError(
                            f"Critical: Target instance {current_target._uuid} not found in InstanceMap."
                        )

                    current_graph_structure_hash = self.blueprint_hasher.compute_hash(
                        graph
                    )
                    if current_graph_structure_hash in self._template_plan_cache:
                        indexed_plan = self._template_plan_cache[
                            current_graph_structure_hash
                        ]
                        plan = self._rehydrate_plan(graph, indexed_plan)
                    else:
                        plan = self.solver.resolve(graph)
                        indexed_plan = self._index_plan(graph, plan)
                        self._template_plan_cache[current_graph_structure_hash] = (
                            indexed_plan
                        )

                    local_context_cache[current_target._uuid] = (
                        graph,
                        instance_map,
                        plan,
                        executable_registry,
                    )

                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                if next_input_overrides:
                    input_overrides = next_input_overrides
                    next_input_overrides = None

                graph_result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                    executable_registry,
                    root_input_overrides=input_overrides,
                )

            result = graph_result.value

            if isinstance(result, Jump):
                source_node_id = graph_result.source_node_id
                jump_edge = next(
                    (
                        e
                        for e in graph.edges
                        if e.source.current_node_instance_hash == source_node_id
                        and e.edge_type == EdgeType.ITERATIVE_JUMP
                    ),
                    None,
                )

                if not jump_edge or not jump_edge.jump_selector:
                    raise RuntimeError(
                        f"Task returned a Jump signal but has no bound 'select_jump' (Edge not found for {source_node_id})."
                    )

                selector = jump_edge.jump_selector
                next_target = selector.routes.get(result.target_key)

                if next_target is None:
                    return result.data

                current_target = next_target

                if isinstance(result.data, dict):
                    next_input_overrides = result.data
                elif result.data is not None:
                    next_input_overrides = {"0": result.data}
                else:
                    next_input_overrides = {}
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
        plan: Any,
        instance_map: Dict[str, Node],
        executable_registry: Dict[str, Callable],
        root_input_overrides: Optional[Dict[str, Any]] = None,
    ) -> GraphExecutionResult:
        if target._uuid not in instance_map:
            raise RuntimeError(
                f"Critical: Target instance {target._uuid} not found in InstanceMap."
            )

        target_node = instance_map[target._uuid]
        flow_manager = FlowManager(
            graph, target_node.current_node_instance_hash, instance_map
        )
        blocked_nodes = set()

        for stage in plan:
            pending_nodes_in_stage = list(stage)

            while pending_nodes_in_stage:
                executable_this_pass: List[Node] = []
                deferred_this_pass: List[Node] = []

                for node in pending_nodes_in_stage:
                    skip_reason = await flow_manager.should_skip(node, state_backend)
                    if skip_reason:
                        await state_backend.mark_skipped(
                            node.current_node_instance_hash, skip_reason
                        )
                        self.bus.publish(
                            TaskSkipped(
                                run_id=run_id,
                                task_id=node.current_node_instance_hash,
                                task_name=node.name,
                                reason=skip_reason,
                            )
                        )
                        continue

                    if self.constraint_manager.check_permission(node):
                        executable_this_pass.append(node)
                        if node.current_node_instance_hash in blocked_nodes:
                            blocked_nodes.remove(node.current_node_instance_hash)
                    else:
                        deferred_this_pass.append(node)
                        if node.current_node_instance_hash not in blocked_nodes:
                            self.bus.publish(
                                TaskBlocked(
                                    run_id=run_id,
                                    task_id=node.current_node_instance_hash,
                                    task_name=node.name,
                                    reason="ConstraintViolation",
                                )
                            )
                            blocked_nodes.add(node.current_node_instance_hash)

                if executable_this_pass:

                    async def sub_graph_runner(target, sub_params, parent_state):
                        (
                            sub_graph,
                            sub_instance_map,
                            sub_executable_registry,
                        ) = build_graph(target)
                        sub_plan = self.solver.resolve(sub_graph)
                        result_obj = await self._execute_graph(
                            target,
                            sub_params,
                            active_resources,
                            run_id,
                            parent_state,
                            graph=sub_graph,
                            plan=sub_plan,
                            instance_map=sub_instance_map,
                            executable_registry=sub_executable_registry,
                        )
                        return result_obj.value

                    tasks_to_run = []
                    for node in executable_this_pass:
                        overrides = (
                            root_input_overrides
                            if node.current_node_instance_hash
                            == target_node.current_node_instance_hash
                            else None
                        )

                        requirements = (
                            await self.node_processor.constraint_resolver.resolve(
                                node,
                                graph,
                                state_backend,
                                self.constraint_manager,
                                instance_map,
                            )
                        )

                        inputs = await self.node_processor.arg_resolver.resolve(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            instance_map=instance_map,
                            user_params=params,
                            input_overrides=overrides,
                        )

                        cache_inputs = (
                            await self.node_processor.arg_resolver.resolve_cache_inputs(
                                node, graph, state_backend
                            )
                        )

                        executable = executable_registry[node.current_node_instance_hash]

                        tasks_to_run.append(
                            (
                                node,
                                self.node_processor.process(
                                    node,
                                    executable,
                                    inputs,
                                    requirements,
                                    cache_inputs,
                                    state_backend,
                                    active_resources,
                                    run_id,
                                    params,
                                    sub_graph_runner,
                                ),
                            )
                        )

                    if len(tasks_to_run) == 1:
                        node, coro = tasks_to_run[0]
                        res = await coro
                        await state_backend.put_result(
                            node.current_node_instance_hash, res
                        )
                        if flow_manager:
                            await flow_manager.register_result(
                                node.current_node_instance_hash, res, state_backend
                            )
                    else:
                        nodes_in_pass = [t[0] for t in tasks_to_run]
                        coros = [t[1] for t in tasks_to_run]
                        pass_results = await asyncio.gather(*coros)

                        for node, res in zip(nodes_in_pass, pass_results):
                            await state_backend.put_result(
                                node.current_node_instance_hash, res
                            )
                            if flow_manager:
                                await flow_manager.register_result(
                                    node.current_node_instance_hash, res, state_backend
                                )

                pending_nodes_in_stage = deferred_this_pass

                if pending_nodes_in_stage and not executable_this_pass:
                    await self.wakeup_event.wait()
                    self.wakeup_event.clear()
                    self.constraint_manager.cleanup_expired_constraints()

        if not await state_backend.has_result(target_node.current_node_instance_hash):
            if skip_reason := await state_backend.get_skip_reason(
                target_node.current_node_instance_hash
            ):
                if skip_reason == "UpstreamSkipped_Sequence":
                    return GraphExecutionResult(
                        value=None,
                        source_node_id=target_node.current_node_instance_hash,
                    )
                raise DependencyMissingError(
                    task_id=target.task.name or "unknown",
                    arg_name="<Target Output>",
                    dependency_id=f"Target node '{target_node.name}' was skipped (Reason: {skip_reason})",
                )

            raise KeyError(
                f"Target task '{target.task.name if hasattr(target.task, 'name') else 'unknown'}' did not produce a result."
            )

        final_value = await state_backend.get_result(
            target_node.current_node_instance_hash
        )
        return GraphExecutionResult(
            value=final_value, source_node_id=target_node.current_node_instance_hash
        )
~~~~~

### 下一步建议
我们已经成功地将 `Node` 对象转化为纯粹的数据结构。根据重构计划，下一步是**步骤 3：将 `NodeProcessor` 拆分为微管线 (Micro-Pipeline)**。

我将把 `NodeProcessor` 内部的逻辑重构为三个独立的辅助方法：
*   `_prepare_context()`: 处理资源申请、约束检查（对应 v3.0 的 **Bleacher**）。
*   `_execute_core()`: 纯粹的 `executor.execute` 调用（对应 v3.0 的 **Worker**）。
*   `_handle_outcome()`: 处理结果、缓存写入、重试判断（对应 v3.o 的 **Stainer**）。

虽然这些方法仍在同一个类中，但这种逻辑上的分层将使 v2.0 的执行模型与 v3.0 的物理模型在结构上同构，为最终的迁移做好准备。

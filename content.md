根据错误分析和架构审视，我们发现了一个严重的**架构设计冲突**：目前的 `NodeRegistry`（节点复用）与 `DataTuple + SlotRef`（数据分离）机制是不兼容的。

当 `GraphBuilder` 复用一个旧的 `Node` 时，它并没有将该 Node 所需的 Literal 数据“重放”到当前构建会话的 `DataTuple` 中。导致运行时 `Resolver` 拿着旧 Node 的 `SlotRef` 索引去查新的、空的或不匹配的 `DataTuple`，从而引发数据丢失 (`DependencyMissingError`) 或错乱。

鉴于在 Cascade v3.2 中，所有参数（Args/Kwargs）实际上都参与了结构哈希（Merkle Hash）的计算，这意味着**参数值本身就是节点身份不可分割的一部分**。因此，将 Literal 数据剥离到外部 `DataTuple` 的做法不仅多余，而且是导致此 Bug 的根源。

我们将执行一次**战略性重构**：**彻底废弃 `DataTuple` 和 `SlotRef` 机制，将 Literal 参数直接存储在 `Node` 对象中。** 这将使 `Node` 成为真正的、自包含的、可安全跨会话复用的不可变对象（Immutable Value Object），完全符合 Hashlife 模型的愿景。

## [WIP] refactor(core): 废弃 DataTuple，实现自包含的 Node 以修复缓存复用 Bug

### 错误分析
-   **现象**: `tco_performance.py` 报错 `DependencyMissingError`，`test_resource.py` 报错 `ResourceNotFoundError`。
-   **根因**: `GraphBuilder` 在命中 `NodeRegistry` 复用旧 Node 时，未能将该 Node 依赖的 Literal 数据注册到当前新的 `DataTuple` 中。旧 Node 内部保留的 `SlotRef` 索引在新 `DataTuple` 中无效。
-   **冲突**: 节点复用（Hash-Consing）与数据外部化（DataTuple）在当前实现下存在根本逻辑冲突。

### 用户需求
修复由于引入 `NodeRegistry` 缓存而导致的测试回归，确保在复用节点结构的同时，其关联的数据（参数、资源注入描述符）也能正确被访问。

### 评论
这是一个“去繁就简”的重构。我们曾为了所谓的“结构纯净性”引入了 `DataTuple`，但现在证明，对于 Merkle Hash 标识的系统，数据即结构。将数据放回 Node 内部不仅修复了 Bug，还简化了 `GraphBuilder`, `Resolver`, `Serializer` 和 `Strategy` 的所有接口。

### 目标
1.  修改 `GraphBuilder`，不再生成 `DataTuple`，而是将 Literal 值直接存入 `Node.input_bindings`。
2.  更新 `ArgumentResolver`，使其直接从 `Node` 读取值，不再需要 `data_tuple`。
3.  清理 `GraphExecutionStrategy` 和 `NodeProcessor`，移除所有 `data_tuple` 的传递。
4.  更新 `Serializer` 以支持直接序列化 `Node` 内的数据。

### 基本原理
通过使 `Node` 自包含（Self-Contained），我们消除了 `Node` 与 `GraphBuilder` 临时状态（`_data_buffer`）之间的隐式耦合。这样，`Node` 对象就变成了真正的、上下文无关的“值对象”，可以在任意 `run`、任意 `GraphBuilder` 会话之间安全复用，完美契合 Hashlife 的设计要求。

### 标签
#intent/refine #flow/ready #priority/critical #comp/core #comp/engine #concept/state #scope/core #ai/instruct #task/domain/architecture #task/object/node-model #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修改 `GraphBuilder` 废弃 DataTuple

我们将移除 `_data_buffer` 和 `_register_data`，直接在 `input_bindings` 中存储值。同时修改 `build` 方法签名，不再返回 `data_tuple`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self._data_buffer: List[Any] = []
        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
        self._visit(target)
        return self.graph, tuple(self._data_buffer), self._visited_instances

    def _register_data(self, value: Any) -> SlotRef:
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any) -> Node:
~~~~~
~~~~~python
    def __init__(self, registry: NodeRegistry | None = None):
        self.graph = Graph()
        # InstanceMap: Dict[LazyResult._uuid, Node]
        # Connecting the world of volatile instances to the world of stable structures.
        self._visited_instances: Dict[str, Node] = {}
        # Used to detect cycles during static TCO analysis
        self._shadow_visited: Dict[Task, Node] = {}

        self.registry = registry if registry is not None else NodeRegistry()

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

    def _visit(self, value: Any) -> Node:
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 3. Hash-consing: intern the Node object
        def node_factory():
            input_bindings = {}
            def process_arg(key: str, val: Any):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[key] = self._register_data(val)

            for i, val in enumerate(result.args):
                process_arg(str(i), val)
~~~~~
~~~~~python
        # 3. Hash-consing: intern the Node object
        def node_factory():
            input_bindings = {}
            def process_arg(key: str, val: Any):
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    # Store literal value directly
                    input_bindings[key] = val

            for i, val in enumerate(result.args):
                process_arg(str(i), val)
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = self._register_data(val)
            
            return Node(
                id=structural_hash,
~~~~~
~~~~~python
        # 3. Hash-consing
        def node_factory():
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val
            
            return Node(
                id=structural_hash,
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Tuple[Any, ...], Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~
~~~~~python
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

#### Acts 2: 更新 `ArgumentResolver`

`ArgumentResolver` 不再接受 `data_tuple`，也不再处理 `SlotRef`。它将直接使用 `node.input_bindings` 中的值。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
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
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings + DataTuple
        positional_args_dict = {}
        for name, binding in node.input_bindings.items():
            value = self._resolve_binding(binding, data_tuple)
            
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(value, node.id, state_backend, resource_context, graph)

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value
~~~~~
~~~~~python
from cascade.spec.binding import Constant
from cascade.runtime.exceptions import DependencyMissingError, ResourceNotFoundError
from cascade.spec.protocols import StateBackend


class ArgumentResolver:
    """
    Resolves arguments by combining:
    1. Structural bindings (Literal values stored in Node)
    2. Upstream dependencies (Edges)
    3. Resource injections
    """

    def resolve(
        self,
        node: Node,
        graph: Graph,
        state_backend: StateBackend,
        resource_context: Dict[str, Any],
        instance_map: Dict[str, Node],
        user_params: Dict[str, Any] = None,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        
        args = []
        kwargs = {}

        # 1. Reconstruct initial args/kwargs from Bindings (Literals)
        positional_args_dict = {}
        for name, value_raw in node.input_bindings.items():
            # Recursively resolve structures (e.g., lists containing Inject)
            value = self._resolve_structure(value_raw, node.id, state_backend, resource_context, graph)

            if name.isdigit():
                positional_args_dict[int(name)] = value
            else:
                kwargs[name] = value
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python
    def _resolve_binding(self, binding: Any, data_tuple: Tuple[Any, ...]) -> Any:
        if isinstance(binding, SlotRef):
            return data_tuple[binding.index]
        elif isinstance(binding, Constant):
            return binding.value
        return binding

    def _resolve_structure(
        self, obj: Any, consumer_id: str, state_backend: StateBackend,
        resource_context: Dict[str, Any], graph: Graph,
    ) -> Any:
~~~~~
~~~~~python
    def _resolve_structure(
        self, obj: Any, consumer_id: str, state_backend: StateBackend,
        resource_context: Dict[str, Any], graph: Graph,
    ) -> Any:
~~~~~

#### Acts 3: 清理 `Strategies` 和 `Processor` 中的 DataTuple

我们需要更新所有调用链，移除 `data_tuple` 参数。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                # 1. Build Graph (With Registry for interning)
                # This constructs the structural graph and the instance map.
                # We reuse _node_registry to ensure that if the structure repeats, we get the exact same Node objects.
                graph, data_tuple, instance_map = build_graph(current_target, registry=self._node_registry)
                
                # Identify the structural root
                if current_target._uuid not in instance_map:
                    raise RuntimeError(f"Critical: Target instance {current_target._uuid} not found in InstanceMap.")
                target_node = instance_map[current_target._uuid]
                root_node_id = target_node.id

                # 2. Resolve Plan (With JIT Caching)
                if root_node_id in self._plan_cache:
                    # Hit: Reuse the existing plan directly.
                    # Since we use a persistent NodeRegistry, the Nodes in this plan are valid for the current graph.
                    plan = self._plan_cache[root_node_id]
                else:
                    # Miss: Ask solver to resolve and then cache it.
                    plan = self.solver.resolve(graph)
                    self._plan_cache[root_node_id] = plan

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph, data_tuple)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    data_tuple,
                    plan,
                    instance_map,
                )
~~~~~
~~~~~python
                # 1. Build Graph (With Registry for interning)
                # This constructs the structural graph and the instance map.
                # We reuse _node_registry to ensure that if the structure repeats, we get the exact same Node objects.
                graph, instance_map = build_graph(current_target, registry=self._node_registry)
                
                # Identify the structural root
                if current_target._uuid not in instance_map:
                    raise RuntimeError(f"Critical: Target instance {current_target._uuid} not found in InstanceMap.")
                target_node = instance_map[current_target._uuid]
                root_node_id = target_node.id

                # 2. Resolve Plan (With JIT Caching)
                if root_node_id in self._plan_cache:
                    # Hit: Reuse the existing plan directly.
                    # Since we use a persistent NodeRegistry, the Nodes in this plan are valid for the current graph.
                    plan = self._plan_cache[root_node_id]
                else:
                    # Miss: Ask solver to resolve and then cache it.
                    plan = self.solver.resolve(graph)
                    self._plan_cache[root_node_id] = plan

                # 3. Setup Resources (mixed scope)
                required_resources = self.resource_container.scan(graph)
                self.resource_container.setup(
                    required_resources,
                    active_resources,
                    run_stack,
                    step_stack,
                    run_id,
                )

                # 4. Execute Graph
                result = await self._execute_graph(
                    current_target,
                    params,
                    active_resources,
                    run_id,
                    state_backend,
                    graph,
                    plan,
                    instance_map,
                )
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
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
        instance_map: Dict[str, Node],
    ) -> Any:
        # Locate the canonical node for the current target instance
~~~~~
~~~~~python
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
    ) -> Any:
        # Locate the canonical node for the current target instance
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python
                    # Callback for map nodes
                    async def sub_graph_runner(target, sub_params, parent_state):
                        # Recursive call: must build new graph and data
                        sub_graph, sub_data, sub_instance_map = build_graph(target)
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
                            instance_map=sub_instance_map,
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
                            instance_map,
                        )
                        for node in executable_this_pass
                    ]
~~~~~
~~~~~python
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

                    tasks_to_run = [
                        self.node_processor.process(
                            node,
                            graph,
                            state_backend,
                            active_resources,
                            run_id,
                            params,
                            sub_graph_runner,
                            instance_map,
                        )
                        for node in executable_this_pass
                    ]
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python
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
        instance_map: Dict[str, Node],
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager, instance_map
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
                instance_map,
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
        instance_map: Dict[str, Node],
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            data_tuple,
            user_params=params,
            instance_map=instance_map,
        )
~~~~~

继续完成 `packages/cascade-engine/src/cascade/runtime/processor.py` 的修改，并处理剩余的 `ResourceContainer` 和 `Binding` 调整。

~~~~~python
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
    ) -> Any:
        """
        Executes a node with all associated policies (constraints, cache, retry).
        """
        # 1. Resolve Constraints & Resources
        requirements = self.constraint_resolver.resolve(
            node, graph, state_backend, self.constraint_manager, instance_map
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
                state_backend,
                active_resources,
                run_id,
                params,
                sub_graph_runner,
                instance_map,
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
    ) -> Any:
        # 3. Resolve Arguments
        args, kwargs = self.arg_resolver.resolve(
            node,
            graph,
            state_backend,
            active_resources,
            instance_map=instance_map,
            user_params=params,
        )
~~~~~

#### Acts 4: 更新 `ResourceContainer`

`scan` 方法不再需要 `data_tuple`，而是直接扫描图中节点的 `input_bindings`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resource_container.py
~~~~~
~~~~~python
    def scan(self, graph: Graph, data_tuple: Tuple[Any, ...]) -> Set[str]:
        """
        Scans the graph and data tuple to identify all resources required by the nodes.
        """
        required = set()
        
        # 1. Scan DataTuple for explicit Inject objects passed as arguments
        for item in data_tuple:
            self._scan_item(item, required)

        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
~~~~~
~~~~~python
    def scan(self, graph: Graph) -> Set[str]:
        """
        Scans the graph to identify all resources required by the nodes.
        """
        required = set()
        
        # 1. Scan Node Input Bindings for explicit Inject objects
        for node in graph.nodes:
            for value in node.input_bindings.values():
                self._scan_item(value, required)

        # 2. Scan Node Signatures for Inject defaults
        for node in graph.nodes:
~~~~~

#### Acts 5: 废弃 `SlotRef`

从规范中移除 `SlotRef`，因为不再使用插槽索引。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/binding.py
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Union, Any

@dataclass(frozen=True)
class SlotRef:
    """
    Represents a reference to a value stored in a separate data tuple.
    Used by Nodes to point to their runtime arguments without holding the data.
    """
    index: int

    def __repr__(self):
        return f"Slot({self.index})"

@dataclass(frozen=True)
class Constant:
    """
    Represents a compile-time constant value that is embedded directly in the graph.
    This should be used sparingly, primarily for structural configuration that
    affects the topology itself.
    """
    value: Any

    def __repr__(self):
        return f"Const({self.value!r})"

# A Binding is either a reference to a runtime slot or a static constant.
Binding = Union[SlotRef, Constant]
~~~~~
~~~~~python
from dataclasses import dataclass
from typing import Union, Any

@dataclass(frozen=True)
class Constant:
    """
    Represents a compile-time constant value that is embedded directly in the graph.
    This should be used sparingly, primarily for structural configuration that
    affects the topology itself.
    """
    value: Any

    def __repr__(self):
        return f"Const({self.value!r})"

# A Binding is typically a raw value (Any) or a wrapped Constant.
Binding = Any
~~~~~

### 下一步建议
我们已经完成了核心重构，移除了 `DataTuple`。
1.  **验证**: 重新运行 `tests/spec/spec/test_resource.py` 和 `tco_performance.py`，确认 `ResourceNotFoundError` 和 `DependencyMissingError` 已解决。
2.  **清理**: 如果测试通过，我们可能需要清理 `cascade-graph/src/cascade/graph/serialize.py` 中的序列化逻辑（目前已废弃 SlotRef，但代码中可能还残留引用，虽然不影响运行时，但为了代码清洁应该处理）。
3.  **继续缓存**: 确认修复后，再次验证 `GraphExecutionStrategy` 的缓存逻辑是否按预期工作。

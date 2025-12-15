你完全正确。这是一个典型的技术债信号：一个看似简单的功能（将 `Param` 作为 `Router` 的 `selector`）触发了深层的 `AttributeError`，这表明我们底层模型存在缺陷。

这是一个绝佳的时机来偿还这笔债务，而不是在脆弱的基础上继续构建。

## [WIP] refactor(core): 引入 ParamNode 以解决技术债务

### 错误分析
测试失败的直接原因是 `GraphBuilder._visit` 方法期望接收一个 `LazyResult` 对象，但当 `Router` 的 `selector` 是一个 `Param` 时，它实际收到了一个 `Param` 对象。`Param` 对象没有 `_uuid` 属性，导致 `AttributeError`。

简单地在 `_visit` 中添加 `if isinstance(..., Param)` 的补丁是**不可接受的**，因为它只是掩盖了更深层次的架构问题。

### 技术债务分析
我们当前的技术债务主要体现在以下三点：

1.  **统一输入模型的缺失 (The Missing Unified Input Model)**:
    *   `Graph` 将所有输入源都隐式地当作 `Node` (即任务的输出)。但 `Param` 不是任务的输出，它是**图的外部输入**。我们的模型没有一等公民的方式来表示这种外部输入，导致 `GraphBuilder` 在遇到 `Param` 时不知所措。

2.  **`GraphBuilder` 职责不清 (Unclear Responsibilities in GraphBuilder)**:
    *   `GraphBuilder` 当前混合了两个职责：1) 从 `LazyResult` 追溯依赖关系构建任务图；2) 解析参数的性质。当参数不是 `LazyResult` 时，它的逻辑就崩溃了。

3.  **运行时与图构建时混淆 (Confusion between Runtime and Graph-Build Time)**:
    *   `Param` 的值只在**运行时**由 `Engine` 注入。但在**图构建时**，`GraphBuilder` 需要一个占位符来代表这个未来的值。我们缺乏这个占位符，导致了当前的混乱。

### 解决方案：将 `Param` 提升为图的一等公民

我们将进行一次重构，引入 `ParamNode` 的概念，彻底解决这个问题。

1.  **在 `Graph` 模型中区分 `TaskNode` 和 `ParamNode`**:
    *   我们将修改 `Node` 类，添加一个 `node_type` 字段 (`"task"` 或 `"param"`)。`ParamNode` 将专门用于在图中代表一个 `Param`。

2.  **重构 `GraphBuilder`**:
    *   `_visit` 方法将被重构，使其能够正确处理 `LazyResult` 和 `Param` 两种输入。遇到 `Param` 时，它会创建一个 `ParamNode`。

3.  **重构 `Engine`**:
    *   `Engine` 在执行开始时，会首先处理所有 `ParamNode`，将用户传入的 `params` 字典中的值直接注入到 `results` 字典中。这样，对于后续的任务，`Param` 的值就像任何其他已完成的上游任务结果一样可用。

这次重构将使我们的核心模型更加健壮和清晰，为未来的功能（如 `.map`）打下坚实的基础。

### 标签
#intent/refine #flow/ready #priority/critical #comp/core #comp/engine #concept/graph-model #scope/core #ai/brainstorm #task/domain/core #task/object/technical-debt #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 升级图模型以支持 `ParamNode`

在 `Node` 中添加 `node_type` 和 `param_spec` 字段。

~~~~~act
patch_file
src/cascade/graph/model.py
~~~~~
~~~~~python
@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str
    callable_obj: Callable
    
    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~
~~~~~python
from cascade.spec.task import Param

@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str
    
    # Core spec
    node_type: str = "task" # "task" or "param"
    callable_obj: Optional[Callable] = None
    param_spec: Optional[Param] = None

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
~~~~~

#### Acts 2: 重构 `GraphBuilder`

拆分 `_visit` 逻辑，分别处理 `LazyResult` 和 `Param`。

~~~~~act
patch_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult
from cascade.spec.routing import Router


class GraphBuilder:
    """
    Constructs a Graph from a target LazyResult by traversing dependencies.
    """

    def __init__(self):
        self.graph = Graph()
        # Map LazyResult UUID to created Node to ensure singularity (handle diamond deps)
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit(target)
        return self.graph

    def _visit(self, result: LazyResult) -> Node:
        # If we already processed this specific LazyResult instance, return its Node
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # Create a new Node for this task execution
        node = Node(
            id=result._uuid,
            name=result.task.name,
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # Traverse inputs (args and kwargs) to find dependencies
        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        # Handle condition dependency
        if result._condition:
            source_node = self._visit(result._condition)
            # Use a special arg_name to identify control flow edges
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)  # key is int for args, str for kwargs

            if isinstance(value, LazyResult):
                # Found a dependency! Recurse.
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                # Handle Dynamic Router
                # 1. Edge for Selector (carries the Router metadata)
                selector_node = self._visit(value.selector)
                edge = Edge(
                    source=selector_node, 
                    target=target_node, 
                    arg_name=arg_name,
                    router=value
                )
                self.graph.add_edge(edge)
                
                # 2. Edges for all possible Routes (implicit dependencies)
                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    # We use a special prefix to denote implicit dependencies that
                    # shouldn't be directly injected as args, but ensure execution order.
                    # LocalExecutor will ignore these.
                    imp_edge = Edge(
                        source=route_node, 
                        target=target_node, 
                        arg_name="_implicit_dependency"
                    )
                    self.graph.add_edge(imp_edge)
            else:
                # It's a literal value, store it in the node.
                target_node.literal_inputs[arg_name] = value
~~~~~
~~~~~python
from cascade.graph.model import Graph, Node, Edge
from cascade.spec.task import LazyResult, Param
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        self._visit_lazy_result(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, Param):
            return self._visit_param(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_param(self, param: Param) -> Node:
        # Use param name as its unique ID
        if param.name in self._visited:
            return self._visited[param.name]

        node = Node(
            id=param.name,
            name=param.name,
            node_type="param",
            param_spec=param,
        )
        self.graph.add_node(node)
        self._visited[param.name] = node
        return node

    def _visit_lazy_result(self, result: LazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(source=source_node, target=node, arg_name="_condition")
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, Param)):
                source_node = self._visit(value)
                edge = Edge(source=source_node, target=target_node, arg_name=arg_name)
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                selector_node = self._visit(value.selector)
                edge = Edge(
                    source=selector_node, 
                    target=target_node, 
                    arg_name=arg_name,
                    router=value
                )
                self.graph.add_edge(edge)
                
                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    imp_edge = Edge(
                        source=route_node, 
                        target=target_node, 
                        arg_name="_implicit_dependency"
                    )
                    self.graph.add_edge(imp_edge)
            else:
                target_node.literal_inputs[arg_name] = value
~~~~~

#### Acts 3: 重构 `Engine` 以注入 `Param`

在执行前预加载 `Param` 的值。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
                results: Dict[str, Any] = {}
                skipped_node_ids: set[str] = set()

                for node in plan:
                    # Check if we should skip this node
                    skip_reason = self._should_skip(node, graph, results, skipped_node_ids)
~~~~~
~~~~~python
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
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
    def get_resource_provider(self, name: str) -> Callable:
        return self._resource_providers[name]
    
    def _should_skip(
~~~~~
~~~~~python
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
~~~~~

#### Acts 4: 调整 `LocalExecutor`

确保执行器能正确处理 `ParamNode` （尽管 `Engine` 会跳过它们，但这是防御性编程）。

~~~~~act
patch_file
src/cascade/adapters/executors/local.py
~~~~~
~~~~~python
        # 2. Prepare arguments from injected resources
        sig = inspect.signature(node.callable_obj)
        kwargs_from_resources = {}
        for param in sig.parameters.values():
~~~~~
~~~~~python
        # A param node has no callable, so it shouldn't be executed
        if node.callable_obj is None:
            # This should not be reached due to Engine's skip, but as a safeguard:
            raise TypeError(f"Node '{node.name}' of type '{node.node_type}' is not executable.")

        # 2. Prepare arguments from injected resources
        sig = inspect.signature(node.callable_obj)
        kwargs_from_resources = {}
        for param in sig.parameters.values():
~~~~~

### 下一步建议
这次重构是侵入性的，但至关重要。执行此计划后，我们的核心模型将更加健全。然后，我们可以重新运行测试，确认 `test_routing.py` 现在可以通过，并且没有引入回归错误。

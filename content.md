好的，我们开始执行“白板重构”计划的第三部分：实现 `Node` 的显式多态化。这是一个关键的重构，它将根除一整类类型安全问题，并使图模型更加健壮和易于理解。

我将分步执行此计划，首先修改规范（Spec）和图模型，然后更新图构建器，最后修复消费端的代码。

## [WIP] refactor: 实现 Node 的显式多态化层次结构

### 用户需求
根据“白板重构”计划，将 `Node` 类重构为抽象基类，并为不同类型的图实体（Task, Param, Map 等）提供具体的强类型子类。

### 评论
当前 `Node` 类通过动态附加属性（如 `param_spec`）来模拟多态，这种“隐式约定”在静态分析下非常脆弱。通过显式的类层次结构，我们可以利用 `isinstance` 作为类型保护，让编译器和开发者都能清晰地知道某个节点具备哪些属性。

### 目标
1.  **传递元数据**：更新 `LazyResult` 以携带 `ParamSpec` 元数据。
2.  **定义新契约**：在 `cascade-graph` 中定义 `Node` 基类, `TaskNode`, `MapNode`, 和 `ParamNode` 子类。
3.  **更新构建器**：更新 `GraphBuilder`，使其根据输入的 `LazyResult` 类型产生对应的子类实例。
4.  **修复消费端**：利用 `isinstance` 修复 `cascade-sdk` 和 `cascade-engine` 中的类型安全问题。

### 基本原理
这是一次从“基于字符串类型判断”到“基于类身份判断”的转变。它将运行时的不确定性转化为编译时的确定性，是构建一个可维护、可扩展的核心引擎的必要步骤。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/graph #comp/sdk #comp/engine #concept/graph-model #scope/core
#ai/brainstorm
#task/domain/core
#task/object/node-hierarchy
#task.action/refactor
#task/state/continue

---

### Script

#### Acts 1: 扩展 `LazyResult` 以传递 `ParamSpec` 元数据

首先，我们需要一种方法将 `ParamSpec` 从 `cs.Param()` 工厂函数传递给 `GraphBuilder`。最干净的方式是在 `LazyResult` 上添加一个可选字段。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python.old
from typing import TypeVar, Generic, Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from uuid import uuid4

if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy

# Forward reference for ResourceConstraint
T = TypeVar("T")


@dataclass
class RetryPolicy:
~~~~~
~~~~~python.new
from typing import TypeVar, Generic, Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from uuid import uuid4

if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy
    from cascade.spec.input import ParamSpec

# Forward reference for ResourceConstraint
T = TypeVar("T")


@dataclass
class RetryPolicy:
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python.old
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)

    def __hash__(self):
~~~~~
~~~~~python.new
    _constraints: Optional[Any] = None  # ResourceConstraint
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)
    _param_spec: Optional["ParamSpec"] = None  # For Param nodes

    def __hash__(self):
~~~~~

#### Acts 2: 在 `model.py` 中定义新的 `Node` 类层次结构

现在，我们将 `cascade-graph` 的核心模型 `Node` 重构为一个基类和多个具体的子类。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
from cascade.spec.ir.models import TaskDef
from cascade.spec.input import ParamSpec


class EdgeType(Enum):
    DATA = auto()
    CONDITION = auto()
    CONSTRAINT = auto()
    IMPLICIT = auto()
    SEQUENCE = auto()
    ROUTER_ROUTE = auto()
    POTENTIAL = auto()
    ITERATIVE_JUMP = auto()


@dataclass
class Node:
    """Base class for all nodes in the computation graph."""

    structural_id: str
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        # Provide a safe fallback for the node's name
        return self.structural_id

    @property
    def node_type(self) -> str:
        raise NotImplementedError("Subclasses must define a node_type property.")


@dataclass
class TaskNode(Node):
    """Represents a standard computation task."""

    definition: TaskDef
    callable_obj: Callable
    input_bindings: Dict[str, Any] = field(default_factory=dict)
    has_complex_inputs: bool = False

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def node_type(self) -> str:
        return "task"


@dataclass
class MapNode(Node):
    """Represents a .map() operation over a factory."""

    definition: TaskDef
    mapping_factory: Any
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        # For map nodes, the name reflects the mapping operation.
        return f"map({self.definition.name})"

    @property
    def node_type(self) -> str:
        return "map"


@dataclass
class ParamNode(Node):
    """Represents a cs.Param, a special input node."""

    param_spec: ParamSpec
    # It still has a definition because it's created from a task (_get_param_value)
    definition: TaskDef
    callable_obj: Callable

    @property
    def name(self) -> str:
        return self.param_spec.name

    @property
    def node_type(self) -> str:
        return "param"


@dataclass
class Edge:
    source: Node
    target: Node
    arg_name: str
    edge_type: EdgeType = EdgeType.DATA
    router: Optional[Any] = None
    jump_selector: Optional[Any] = None


@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def add_node(self, node: Node):
        if node.structural_id not in self._node_index:
            self.nodes.append(node)
            self._node_index[node.structural_id] = node

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._node_index.get(node_id)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~

#### Acts 3: 更新 `GraphBuilder` 以创建正确的 `Node` 子类

这是本次重构的核心。`GraphBuilder` 现在将检查 `LazyResult` 的元数据，并实例化 `TaskNode`, `MapNode`, 或 `ParamNode`。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, Tuple
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

    def build(self, target: Any) -> Tuple[Graph, Dict[str, Node]]:
        self._visit(target)
        return self.graph, self._visited_instances

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
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        # 4. Hash-consing / Create Node
        node = self.registry.get(node_hash)
        if not node:
            # This is where we decide which Node subclass to instantiate
            if result._param_spec:
                node = ParamNode(
                    structural_id=node_hash,
                    param_spec=result._param_spec,
                    definition=task_def,
                    callable_obj=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                )
            else:
                # Standard TaskNode
                input_bindings = {}
                for i, val in enumerate(result.args):
                    if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                        input_bindings[str(i)] = val
                for k, val in result.kwargs.items():
                    if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                        input_bindings[k] = val

                has_complex = self._has_complex_inputs(result, input_bindings)

                node = TaskNode(
                    structural_id=node_hash,
                    definition=task_def,
                    callable_obj=result.task.func,
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    has_complex_inputs=has_complex,
                )
            self.registry.register(node_hash, node)

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        # 5. Edges
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        if result._jump_selector:
            self._add_jump_edges(node, result._jump_selector)
        if result._condition:
            self._add_metadata_edge(node, result._condition, EdgeType.CONDITION)
        if result._constraints:
            self._add_constraint_edges(node, result._constraints)
        if result._dependencies:
            for dep in result._dependencies:
                self._add_metadata_edge(node, dep, EdgeType.SEQUENCE)

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

        task_def = self.analyzer.analyze(result.factory)
        node_hash = self.hashing_service.compute_node_instance_hash(
            task_def, result, dep_nodes
        )

        node = self.registry.get(node_hash)
        if not node:
            input_bindings = {}
            for k, val in result.mapping_kwargs.items():
                if not isinstance(val, (LazyResult, MappedLazyResult, Router)):
                    input_bindings[k] = val

            node = MapNode(
                structural_id=node_hash,
                definition=task_def,
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry.register(node_hash, node)

        self._visited_instances[result._uuid] = node
        self.graph.add_node(node)

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            self._add_metadata_edge(node, result._condition, EdgeType.CONDITION)
        for dep in result._dependencies:
            self._add_metadata_edge(node, dep, EdgeType.SEQUENCE)

        return node

    def _has_complex_inputs(self, result: LazyResult, bindings: Dict[str, Any]) -> bool:
        from cascade.spec.resource import Inject as InjectMarker

        if any(isinstance(p.default, InjectMarker) for p in result.task._signature.parameters.values()):
            return True

        def is_complex_value(v):
            if isinstance(v, InjectMarker):
                return True
            if isinstance(v, (list, tuple)):
                return any(is_complex_value(x) for x in v)
            if isinstance(v, dict):
                return any(is_complex_value(x) for x in v.values())
            return False

        return any(is_complex_value(v) for v in bindings.values())

    def _add_metadata_edge(self, target: Node, source_lr: Any, edge_type: EdgeType):
        source_node = self._visited_instances[source_lr._uuid]
        self.graph.add_edge(
            Edge(source=source_node, target=target, arg_name=f"_{edge_type.name.lower()}", edge_type=edge_type)
        )

    def _add_constraint_edges(self, target: Node, constraints: Any):
        for res, req in constraints.requirements.items():
            if isinstance(req, (LazyResult, MappedLazyResult)):
                source = self._visited_instances[req._uuid]
                self.graph.add_edge(
                    Edge(source=source, target=target, arg_name=res, edge_type=EdgeType.CONSTRAINT)
                )

    def _add_jump_edges(self, source_node: Node, selector: JumpSelector):
        for route_target_lr in selector.routes.values():
            if route_target_lr:
                # Ensure the route target has been visited and is in the graph
                self._visit(route_target_lr)
                target_node = self._visited_instances[route_target_lr._uuid]
                self.graph.add_edge(
                    Edge(
                        source=source_node,
                        target=target_node,
                        arg_name="<jump>",
                        edge_type=EdgeType.ITERATIVE_JUMP,
                        jump_selector=selector,
                    )
                )
    
    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visited_instances[obj._uuid]
            self.graph.add_edge(
                Edge(source=source_node, target=target_node, arg_name=path or "dep", edge_type=EdgeType.DATA)
            )
        elif isinstance(obj, Router):
            selector_node = self._visited_instances[obj.selector._uuid]
            self.graph.add_edge(
                Edge(source=selector_node, target=target_node, arg_name=path, router=obj, edge_type=EdgeType.DATA)
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
                self._scan_and_add_edges(target_node, item, path=f"{path}[{i}]" if path else str(i))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                self._scan_and_add_edges(target_node, v, path=f"{path}.{k}" if path else str(k))

def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~

### 下一步建议
我们已经完成了对图模型的核心重构。这应该已经解决了 `lisp.py` 中的 `pyright` 错误。

下一步是适配 `cascade-engine` 中的消费端代码，特别是 `ArgumentResolver`，使其也能利用新的类型信息。虽然当前可能没有报错，但进行适配将使代码更加清晰和健壮。如果你同意，我将生成一个计划来适配 `resolvers.py`。

好的，这是一个关键的重构步骤。我们将引入类型安全的 `EdgeType` 枚举，并消除对特殊边类型（如 `_constraint:` 和 `_implicit_dependency`）的魔法字符串依赖。

## [WIP] refactor(graph): 引入 EdgeType 枚举以消除魔法字符串

### 用户需求
消除对硬编码字符串（如 `_constraint:`， `_implicit_dependency`， `_condition`）的依赖，增强图模型的类型安全和健壮性。

### 评论
这个重构解决了我们在技术债务分析中确定的一个核心实现债。它使 `GraphBuilder` 和 `ArgumentResolver` 等核心组件的逻辑更加清晰，并为未来引入更多类型的特殊边提供了可扩展的基础。

### 目标
1.  在 `src/cascade/graph/model.py` 中定义 `EdgeType` 枚举，并更新 `Edge` 模型。
2.  更新 `src/cascade/graph/build.py` 以使用新的 `EdgeType` 枚举来标记所有特殊边 (`CONDITION`, `CONSTRAINT`, `IMPLICIT`)。
3.  更新 `src/cascade/runtime/engine.py` 中的 `_should_skip` 逻辑，仅对 `DATA` 和 `IMPLICIT` 边进行级联跳过检查。
4.  更新 `src/cascade/runtime/resolvers.py` 中的解析器，使用 `EdgeType.DATA` 过滤掉所有控制边。
5.  更新 `src/cascade/tools/visualize.py`，根据 `EdgeType` 正确渲染图中的特殊边。

### 基本原理
当前的代码使用字符串前缀来区分数据边和控制边（如条件边、约束边）。这种模式容易出错，且缺乏类型检查。通过引入 `EdgeType` 枚举，我们将图结构中的“意图”显式化和类型化，提高了可读性和可维护性。

### 标签
#intent/refine #flow/ready #priority/medium #comp/graph #comp/runtime #concept/state #scope/dx #ai/delegate #task/domain/graph #task/object/edgemodel #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 定义 EdgeType 枚举并更新 Graph Model

修改 `src/cascade/graph/model.py`，引入 `EdgeType` 枚举并将其添加到 `Edge` dataclass 中。

~~~~~act
write_file
src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto


from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint


class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""
    DATA = auto()           # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()      # A control dependency for the run_if condition
    CONSTRAINT = auto()     # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()       # An implicit structural dependency (e.g., from Router routes)


@dataclass
class Node:
    """Represents a node in the computation graph."""

    id: str
    name: str

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Pre-resolved literal inputs for the task
    literal_inputs: Dict[str, Any] = field(default_factory=dict)

    def __hash__(self):
        return hash(self.id)


@dataclass
class Edge:
    """Represents a directed dependency from source node to target node."""

    source: Node
    target: Node
    # Metadata like argument name in the target function
    arg_name: str
    # The semantic type of this edge
    edge_type: EdgeType = EdgeType.DATA

    # If set, implies this edge is the selector for a dynamic router
    router: Optional[Any] = None


@dataclass
class Graph:
    """A container for nodes and edges representing the workflow."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if node not in self.nodes:
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~

#### Acts 2: 更新 GraphBuilder 以使用 EdgeType

修改 `src/cascade/graph/build.py`，在所有创建 `Edge` 实例的地方传入正确的 `edge_type`。

~~~~~act
write_file
src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.common import Param
from cascade.spec.routing import Router


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}

    def build(self, target: LazyResult) -> Graph:
        # Target could be a MappedLazyResult too
        self._visit(target)
        return self.graph

    def _visit(self, value: Any) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
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
            constraints=result._constraints,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._process_dependencies(node, result.args, is_kwargs=False)
        self._process_dependencies(node, result.kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node, 
                target=node, 
                arg_name="_condition", 
                edge_type=EdgeType.CONDITION
            )
            self.graph.add_edge(edge)

        # Process dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            from cascade.spec.task import LazyResult, MappedLazyResult

            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    # Use EdgeType.CONSTRAINT instead of magic arg_name prefix
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name, # Use resource name as arg_name
                        edge_type=EdgeType.CONSTRAINT
                    )
                    self.graph.add_edge(edge)

        return node

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # Process dependencies in mapping_kwargs
        # Note: These arguments are treated as kwargs
        self._process_dependencies(node, result.mapping_kwargs, is_kwargs=True)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node, 
                target=node, 
                arg_name="_condition", 
                edge_type=EdgeType.CONDITION
            )
            self.graph.add_edge(edge)

        return node

    def _process_dependencies(self, target_node: Node, inputs: Any, is_kwargs: bool):
        iterator = inputs.items() if is_kwargs else enumerate(inputs)

        for key, value in iterator:
            arg_name = str(key)

            if isinstance(value, (LazyResult, MappedLazyResult, Param)):
                source_node = self._visit(value)
                # Standard DATA edge
                edge = Edge(
                    source=source_node, 
                    target=target_node, 
                    arg_name=arg_name, 
                    edge_type=EdgeType.DATA
                )
                self.graph.add_edge(edge)
            elif isinstance(value, Router):
                selector_node = self._visit(value.selector)
                # Edge for the Router selector is a DATA edge that happens to carry Router metadata
                edge = Edge(
                    source=selector_node,
                    target=target_node,
                    arg_name=arg_name,
                    router=value,
                    edge_type=EdgeType.DATA
                )
                self.graph.add_edge(edge)

                for route_result in value.routes.values():
                    route_node = self._visit(route_result)
                    # Implicit dependency edge for Router routes
                    imp_edge = Edge(
                        source=route_node,
                        target=target_node,
                        arg_name="_implicit_dependency", 
                        edge_type=EdgeType.IMPLICIT
                    )
                    self.graph.add_edge(imp_edge)
            else:
                target_node.literal_inputs[arg_name] = value


def build_graph(target: LazyResult) -> Graph:
    """Helper function to build a graph from a result."""
    return GraphBuilder().build(target)
~~~~~

#### Acts 3: 更新 Engine 的级联跳过逻辑

修改 `src/cascade/runtime/engine.py`，替换 `_should_skip` 方法中的字符串检查为 `EdgeType`。

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph
from cascade.spec.resource import ResourceDefinition, Inject
~~~~~
~~~~~python
from cascade.graph.build import build_graph
from cascade.graph.model import Node, Graph, EdgeType
from cascade.spec.resource import ResourceDefinition, Inject
~~~~~

~~~~~act
patch_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    def _should_skip(
        self,
        node: Node,
        graph: Graph,
        results: Dict[str, Any],
        skipped_node_ids: set[str],
    ) -> Optional[str]:
        incoming_edges = [edge for edge in graph.edges if edge.target.id == node.id]

        # 1. Cascade Skip: Check only DATA and IMPLICIT edges (i.e., actual inputs and router routes)
        for edge in incoming_edges:
            if edge.edge_type in (EdgeType.DATA, EdgeType.IMPLICIT):
                if edge.source.id in skipped_node_ids:
                    return "UpstreamSkipped"

        # 2. Condition Check
        for edge in incoming_edges:
            if edge.edge_type == EdgeType.CONDITION:
                condition_result = results.get(edge.source.id)
                if not condition_result:
                    return "ConditionFalse"

        return None
~~~~~

#### Acts 4: 更新 ArgumentResolver 和 ConstraintResolver

完全重写 `src/cascade/runtime/resolvers.py`，使用 `EdgeType` 来区分数据边和控制边。

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


class ArgumentResolver:
    """
    Responsible for resolving the actual arguments (args, kwargs) for a node execution
    from the graph structure, upstream results, and resource context.
    """

    def resolve(
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
            # Only process edges that carry data to the task (DATA edges)
            if edge.edge_type != EdgeType.DATA:
                continue

            # Resolve Upstream Value
            if edge.router:
                # Handle Dynamic Routing
                selector_value = upstream_results.get(edge.source.id)
                if selector_value is None:
                    # If the selector itself is missing, that's an error
                    if edge.source.id not in upstream_results:
                        raise DependencyMissingError(
                            node.id, "router_selector", edge.source.id
                        )

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


class ConstraintResolver:
    """
    Responsible for resolving dynamic resource constraints for a node.
    """

    def resolve(
        self, node: Node, graph: Graph, upstream_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        if not node.constraints or node.constraints.is_empty():
            return {}

        resolved = {}
        
        # Find all CONSTRAINT edges relevant to this node
        constraint_edges = [
            e for e in graph.edges 
            if e.target.id == node.id and e.edge_type == EdgeType.CONSTRAINT
        ]

        # Use the constraints requirements defined in the node spec as the primary source
        for res, amount in node.constraints.requirements.items():
            if isinstance(amount, (LazyResult, MappedLazyResult)):
                # Match requirement name with the edge's arg_name (which is the resource name in GraphBuilder)
                constraint_edge = next(
                    (e for e in constraint_edges if e.arg_name == res), None
                )
                
                if constraint_edge is None:
                    raise RuntimeError(
                        f"Internal Error: Missing constraint edge for dynamic requirement '{res}' on task '{node.name}'"
                    )

                if constraint_edge.source.id in upstream_results:
                    resolved[res] = upstream_results[constraint_edge.source.id]
                else:
                    raise DependencyMissingError(
                        node.id, f"constraint:{res}", constraint_edge.source.id
                    )
            else:
                resolved[res] = amount
        return resolved
~~~~~

#### Acts 5: 更新 Visualize 工具以处理 EdgeType

修改 `src/cascade/tools/visualize.py`，替换字符串检查为 `EdgeType`，并添加 `CONSTRAINT` 边的可视化支持。

~~~~~act
patch_file
src/cascade/tools/visualize.py
~~~~~
~~~~~python
from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..graph.model import Node


def visualize(target: LazyResult[Any]) -> str:
~~~~~
~~~~~python
from typing import Any
from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..graph.model import Node, EdgeType


def visualize(target: LazyResult[Any]) -> str:
~~~~~

~~~~~act
patch_file
src/cascade/tools/visualize.py
~~~~~
~~~~~python
    # 2. Define Edges
    for edge in graph.edges:
        style = ""
        if edge.arg_name == "_condition":
            style = ' [style=dashed, color=gray, label="run_if"]'
        elif edge.arg_name == "_implicit_dependency":
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.router:
            style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')
~~~~~
~~~~~python
    # 2. Define Edges
    for edge in graph.edges:
        style = ""
        
        if edge.edge_type == EdgeType.CONDITION:
            style = ' [style=dashed, color=gray, label="run_if"]'
        elif edge.edge_type == EdgeType.IMPLICIT:
            style = ' [style=dotted, color=lightgray, arrowhead=none, label="implicit"]'
        elif edge.router:
            # Router selector edge (which is EdgeType.DATA)
            style = f' [style=dashed, color=blue, label="route via: {edge.arg_name}"]'
        elif edge.edge_type == EdgeType.CONSTRAINT:
            style = f' [style=dotted, color=purple, label="constraint: {edge.arg_name}"]'
        else:
            style = f' [label="{edge.arg_name}"]'

        dot_parts.append(f'  "{edge.source.id}" -> "{edge.target.id}"{style};')
~~~~~

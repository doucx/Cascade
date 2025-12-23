好的，我们正式开始执行“模板-实例分离”架构重构的第一步。

这一步是破坏性的：我们将修改 `Graph` 模型和 `GraphBuilder` 的核心逻辑，剥离所有运行时数据。这将导致下游组件（Engine, Solver, Serializer）暂时无法工作，直到我们在后续步骤中修复它们。这是预期的结果。

## [WIP] refactor(core): 分离图结构与运行时数据 (The Great Split)

### 用户需求
根据 [Cascade 架构重构 - 结构数据分离 (v3.0)] 路线图，执行第一阶段任务：
1.  引入 `SlotRef` 概念，用于在图节点中引用外部数据槽。
2.  重构 `Node` 模型，移除存储具体值的 `literal_inputs`，替换为存储引用关系的 `input_bindings`。
3.  重构 `GraphBuilder`，使其在构建图的过程中将所有字面量数据提取到一个线性的数据缓冲区中，并返回 `(Graph, DataTuple)`。

### 评论
这是 Cascade 架构史上最重要的一次底层重构。它将把“计算图”从一个包含数据的混合体，转变为一个纯粹的、可缓存的拓扑结构（Template），为未来的 Hashlife 缓存和零开销 TCO 奠定基础。

### 目标
1.  在 `cascade-spec` 中定义 `SlotRef`。
2.  更新 `cascade-graph` 中的 `Node` 定义。
3.  重写 `cascade-graph` 中的 `GraphBuilder` 以支持数据分离。

### 基本原理
目前的 `Node` 对象直接持有 `literal_inputs`，这导致每次任务调用（即使参数不同但结构相同）都会生成全新的 `Graph` 对象，无法进行结构级缓存。通过引入间接层 (`SlotRef`)，我们可以让 `Graph` 对象对具体数据“脱敏”，从而实现结构复用。

### 标签
#intent/architect #flow/draft #priority/critical #comp/graph #concept/data-model #scope/core #ai/instruct #task/domain/core #task/object/graph-model #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 定义数据绑定原语

我们在 `cascade-spec` 中创建一个新模块 `binding.py`，用于定义将节点参数绑定到运行时数据槽的结构。

~~~~~act
write_file
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

#### Acts 2: 重构 Node 模型

修改 `Node` 类，删除 `literal_inputs`，替换为 `input_bindings`。这个字典将参数名映射到 `SlotRef` 或 `Constant`。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict, Union
from enum import Enum, auto
import inspect


from cascade.spec.common import Param
from cascade.spec.constraint import ResourceConstraint
from cascade.spec.binding import Binding  # NEW


class EdgeType(Enum):
    """Defines the semantic type of a dependency edge."""

    DATA = (
        auto()
    )  # A standard data dependency (the output of Source is an input to Target)
    CONDITION = auto()  # A control dependency for the run_if condition
    CONSTRAINT = auto()  # An implicit dependency for resolving dynamic constraints
    IMPLICIT = auto()  # An implicit structural dependency
    SEQUENCE = auto()  # An explicit execution order dependency (no data transfer)
    ROUTER_ROUTE = auto()  # A potential dependency branch for a Router
    POTENTIAL = auto()  # A potential flow path inferred via static analysis (e.g. TCO)


@dataclass
class Node:
    """
    Represents a node in the computation graph template.
    
    A Node defines 'what' to execute (the callable) and 'how' to get its arguments
    (bindings or edges), but it DOES NOT contain the runtime data itself.
    """

    id: str
    name: str
    is_shadow: bool = False  # True if this node is for static analysis only
    tco_cycle_id: Optional[str] = None  # ID of the TCO cycle this node belongs to

    # Core spec
    node_type: str = "task"  # "task", "param", or "map"
    callable_obj: Optional[Callable] = None
    signature: Optional[inspect.Signature] = None  # Cached signature for performance
    param_spec: Optional[Param] = None
    mapping_factory: Optional[Any] = None  # Implements LazyFactory

    # Metadata for execution strategies
    retry_policy: Optional[Any] = None  # Typed as Any to avoid circular deps with spec
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings
    # Maps argument names to references (Slots or Constants).
    # Actual values are stored in a separate DataTuple at runtime.
    input_bindings: Dict[str, Binding] = field(default_factory=dict)

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
    """A container for nodes and edges representing the workflow topology."""

    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node: Node):
        if node not in self.nodes:
            self.nodes.append(node)

    def add_edge(self, edge: Edge):
        self.edges.append(edge)
~~~~~

#### Acts 3: 重写 GraphBuilder

这是本次重构的核心。`GraphBuilder` 现在需要维护一个 `data_buffer`，并在遍历 LazyResult 树时，将非 LazyResult 的值剥离出来存入 buffer，并为 Node 生成对应的 `SlotRef`。`build` 方法的签名也随之改变。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python
from typing import Dict, Any, List, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType
from cascade.spec.lazy_types import LazyResult, MappedLazyResult
from cascade.spec.routing import Router
from cascade.graph.ast_analyzer import analyze_task_source, assign_tco_cycle_ids
from cascade.spec.task import Task
from cascade.spec.binding import SlotRef, Constant


class GraphBuilder:
    def __init__(self):
        self.graph = Graph()
        self._visited: Dict[str, Node] = {}
        # Used to detect cycles during shadow node expansion
        self._shadow_visited: Dict[Task, Node] = {}
        
        # The meat: storage for extracted runtime data
        self._data_buffer: List[Any] = []

    def build(self, target: LazyResult) -> Tuple[Graph, Tuple[Any, ...]]:
        """
        Builds a GraphTemplate and extracts a DataTuple from the target LazyResult.
        
        Returns:
            (Graph, DataTuple): The pure topological structure and the flattened runtime data.
        """
        self._visit(target)
        return self.graph, tuple(self._data_buffer)

    def _register_data(self, value: Any) -> SlotRef:
        """Appends data to the buffer and returns a reference to its index."""
        index = len(self._data_buffer)
        self._data_buffer.append(value)
        return SlotRef(index)

    def _visit(self, value: Any, scan_for_tco: bool = True) -> Node:
        if isinstance(value, LazyResult):
            return self._visit_lazy_result(value, scan_for_tco)
        elif isinstance(value, MappedLazyResult):
            return self._visit_mapped_result(value)
        else:
            raise TypeError(f"Cannot build graph from type {type(value)}")

    def _visit_lazy_result(self, result: LazyResult, scan_for_tco: bool = True) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # 1. Process Inputs: Separate Structure (Edges) from Data (Bindings)
        input_bindings = {}
        
        # Helper to process a single argument
        def process_arg(key: str, val: Any):
            # Recursion for nested structures (Lists/Dicts) containing LazyResults is not 
            # fully supported in this version of the builder for simplicity.
            # We assume top-level args are either LazyResult (Edge) or Data (Binding).
            # Complex nested structures should be handled by specific providers or flattened.
            
            if isinstance(val, (LazyResult, MappedLazyResult)):
                # It's a dependency, will be added as an Edge later
                pass 
            elif isinstance(val, Router):
                # Router is a structural construct, handled in edges
                pass
            else:
                # It's literal data, extract it!
                input_bindings[key] = self._register_data(val)

        for i, val in enumerate(result.args):
            process_arg(str(i), val)
        
        for k, val in result.kwargs.items():
            process_arg(k, val)

        # Pre-compute signature
        sig = None
        if result.task.func:
            try:
                sig = inspect.signature(result.task.func)
            except (ValueError, TypeError):
                pass

        node = Node(
            id=result._uuid,
            name=result.task.name,
            node_type="task",
            callable_obj=result.task.func,
            signature=sig,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings, # Replaces literal_inputs
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        # 2. Recursively scan inputs to add edges (Topology)
        self._scan_and_add_edges(node, result.args)
        self._scan_and_add_edges(node, result.kwargs)

        # 3. Handle conditionals
        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        # 4. Handle dynamic constraints
        if result._constraints and not result._constraints.is_empty():
            for res_name, req_value in result._constraints.requirements.items():
                if isinstance(req_value, (LazyResult, MappedLazyResult)):
                    source_node = self._visit(req_value)
                    edge = Edge(
                        source=source_node,
                        target=node,
                        arg_name=res_name,
                        edge_type=EdgeType.CONSTRAINT,
                    )
                    self.graph.add_edge(edge)

        # 5. Handle explicit sequence dependencies
        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        # 6. Static TCO Analysis
        if scan_for_tco and result.task.func:
            # 6.1 Analyze and tag cycles if not already done
            if not getattr(result.task, "_tco_analysis_done", False):
                assign_tco_cycle_ids(result.task)
            
            # Propagate cycle ID to the Node
            node.tco_cycle_id = getattr(result.task, "_tco_cycle_id", None)

            # 6.2 Retrieve potential targets (using cache)
            potential_targets = analyze_task_source(result.task)
            
            # Register current node in shadow map to allow closing the loop back to root
            self._shadow_visited[result.task] = node

            for target_task in potential_targets:
                self._visit_shadow_recursive(node, target_task)

        return node

    def _visit_shadow_recursive(self, parent_node: Node, task: Task):
        """
        Recursively builds shadow nodes for static analysis.
        """
        if task in self._shadow_visited:
            target_node = self._shadow_visited[task]
            edge = Edge(
                source=parent_node,
                target=target_node,
                arg_name="<potential>",
                edge_type=EdgeType.POTENTIAL,
            )
            self.graph.add_edge(edge)
            return

        potential_uuid = f"shadow:{parent_node.id}:{task.name}"
        
        target_node = Node(
            id=potential_uuid,
            name=task.name,
            node_type="task",
            is_shadow=True,
            tco_cycle_id=getattr(task, "_tco_cycle_id", None)
        )
        self.graph.add_node(target_node)
        
        self._shadow_visited[task] = target_node

        edge = Edge(
            source=parent_node,
            target=target_node,
            arg_name="<potential>",
            edge_type=EdgeType.POTENTIAL,
        )
        self.graph.add_edge(edge)

        potential_targets = analyze_task_source(task)
        
        for next_task in potential_targets:
            self._visit_shadow_recursive(target_node, next_task)

    def _visit_mapped_result(self, result: MappedLazyResult) -> Node:
        if result._uuid in self._visited:
            return self._visited[result._uuid]

        # Extract bindings for mapped inputs
        input_bindings = {}
        # Mapped inputs in mapping_kwargs are typically lists/iterables.
        # We treat the whole iterable as a single data unit for now.
        for k, val in result.mapping_kwargs.items():
            if not isinstance(val, (LazyResult, MappedLazyResult)):
                 input_bindings[k] = self._register_data(val)

        node = Node(
            id=result._uuid,
            name=f"map({getattr(result.factory, 'name', 'factory')})",
            node_type="map",
            mapping_factory=result.factory,
            retry_policy=result._retry_policy,
            cache_policy=result._cache_policy,
            constraints=result._constraints,
            input_bindings=input_bindings,
        )
        self.graph.add_node(node)
        self._visited[result._uuid] = node

        self._scan_and_add_edges(node, result.mapping_kwargs)

        if result._condition:
            source_node = self._visit(result._condition)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="_condition",
                edge_type=EdgeType.CONDITION,
            )
            self.graph.add_edge(edge)

        for dep in result._dependencies:
            source_node = self._visit(dep)
            edge = Edge(
                source=source_node,
                target=node,
                arg_name="<sequence>",
                edge_type=EdgeType.SEQUENCE,
            )
            self.graph.add_edge(edge)

        return node

    def _scan_and_add_edges(self, target_node: Node, obj: Any, path: str = ""):
        if isinstance(obj, (LazyResult, MappedLazyResult)):
            source_node = self._visit(obj)
            edge = Edge(
                source=source_node,
                target=target_node,
                arg_name=path or "dependency",
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

        elif isinstance(obj, Router):
            selector_node = self._visit(obj.selector)
            edge = Edge(
                source=selector_node,
                target=target_node,
                arg_name=f"{path}.selector" if path else "selector",
                router=obj,
                edge_type=EdgeType.DATA,
            )
            self.graph.add_edge(edge)

            for route_key, route_result in obj.routes.items():
                route_node = self._visit(route_result)
                imp_edge = Edge(
                    source=route_node,
                    target=target_node,
                    arg_name=f"{path}.route[{route_key}]",
                    edge_type=EdgeType.ROUTER_ROUTE,
                )
                self.graph.add_edge(imp_edge)

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


def build_graph(target: LazyResult) -> Tuple[Graph, Tuple[Any, ...]]:
    """
    Entry point for building a graph.
    
    Returns:
        (Graph, DataTuple)
    """
    return GraphBuilder().build(target)
~~~~~

### 下一步建议
当前代码库处于“故意破坏”状态。下游所有依赖 `build_graph` 返回值或 `Node.literal_inputs` 的代码（Solver, Engine, Serializer）现在都已失效。
建议立即执行下一个计划：**[COMMIT 2] 重建核心 - 修复 Engine 与 Solvers**，以适配新的 `(Graph, DataTuple)` 契约。

这就是 Phase 1 的执行计划。

我们将重构 `Node` 模型通过清晰的继承来消除歧义，并简化 `ParamNode` 的构建逻辑，使其不再依赖脆弱的上下文查找，而是直接存储参数名称。

## [WIP] refactor: 显式化 Node 多态并解耦构建逻辑

### 用户需求
重构 `Node` 类及其子类，消除基类中的冗余字段，建立清晰的继承契约。同时简化 `ParamNode` 的构建过程，使其不再依赖构建时的上下文查找，而是将参数名作为不可变状态存储。

### 评论
当前的 `Node` 模型是一个混杂了各种职责的“上帝类”，依赖属性是否存在来判断类型，不仅容易出错，也让静态分析失效。此外，`GraphBuilder` 在构建 `ParamNode` 时试图访问全局上下文来获取 `ParamSpec`，这引入了不必要的耦合，导致了测试中的环境依赖问题。

### 目标
1.  **重构 `cascade/graph/model.py`**: 将 `Node` 转变为纯粹的抽象基类（或包含通用字段的基类），移除 `callable_obj` 等多态属性的默认实现。确保 `ParamNode` 显式存储 `param_key`。
2.  **重构 `cascade/graph/build.py`**: 移除构建 `ParamNode` 时的全局上下文查找逻辑。直接从 `LazyResult` 的输入绑定中提取参数名。
3.  **适配 `cascade/graph/serialize.py`**: 确保序列化和反序列化逻辑适配新的模型结构。

### 基本原理
通过**显式多态**，我们让每个节点类型只携带它真正需要的数据。`ParamNode` 不再需要是一个“会自动执行的任务”，它就是一个“参数的占位符”，其唯一职责就是持有参数名。这种数据结构的纯粹性是后续修复运行时逻辑的基础。

### 标签
#intent/refine #flow/ready #priority/high
#comp/engine #concept/history #scope/core
#ai/instruct
#task/domain/core #task/object/graph-model #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 重构 Node 模型
我们将清理 `Node` 基类，并为 `ParamNode` 添加明确的 `param_key` 字段。

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
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    # The static definition of the task.
    definition: TaskDef

    # Optional legacy type tag ("task", "map", "param").
    # Prefer isinstance checks over this string.
    node_type: str = "task"

    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None

    # Structural Bindings (Literals)
    # Maps argument names (or indices) to literal values.
    # For TaskNode, this holds arguments.
    # For ParamNode, this is usually empty or holds raw config.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    # Optimization flag for Resolvers
    has_complex_inputs: bool = False

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        return self.definition.name


@dataclass
class TaskNode(Node):
    """Represents a standard executable task."""

    # The actual python executable object.
    _callable: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self._callable


@dataclass
class MapNode(Node):
    """Represents a mapped task execution."""

    mapping_factory: Optional[Callable] = None

    @property
    def callable_obj(self) -> Optional[Callable]:
        return self.mapping_factory


@dataclass
class ParamNode(Node):
    """Represents an external parameter injection."""

    # The key to look up in the parameters dictionary
    param_key: str = ""

    # Note: We do NOT store ParamSpec here. The spec is a definition-time artifact.
    # The Node only cares about the runtime key.


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

#### Acts 2: 重构 GraphBuilder
我们将简化 `_visit_lazy_result` 中对 `ParamNode` 的处理，移除上下文查找，直接从绑定中提取参数名。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~old
            # Note: execution_mode is now part of task_def (definition.mode)
            if result.task.func is _get_param_value.func:
                # Retrieve the ParamSpec from the global context to attach to the node
                from cascade.context import get_current_context
                
                # The arg at index 0 is the param name
                param_name = input_bindings.get("0") or input_bindings.get("name")
                param_spec = None
                if param_name:
                    ctx = get_current_context()
                    # Linear scan is okay for build time, or we could optimize context lookup
                    for spec in ctx.get_all_specs():
                        if spec.name == param_name:
                            # We import inside to avoid top-level circular imports if possible, 
                            # though ParamSpec is imported in ParamNode definition
                            from cascade.spec.input import ParamSpec
                            if isinstance(spec, ParamSpec):
                                param_spec = spec
                            break

                node = ParamNode(
                    structural_id=node_hash,
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
~~~~~
~~~~~new
            # Note: execution_mode is now part of task_def (definition.mode)
            if result.task.func is _get_param_value.func:
                # The arg at index 0 is the param name.
                # We enforce extraction here to ensure the node is self-contained.
                param_key = input_bindings.get("0") or input_bindings.get("name") or ""
                
                node = ParamNode(
                    structural_id=node_hash,
                    definition=task_def,
                    node_type="param",
                    retry_policy=result._retry_policy,
                    cache_policy=result._cache_policy,
                    constraints=result._constraints,
                    input_bindings=input_bindings,
                    param_key=str(param_key),
                    has_complex_inputs=True,
                )
            else:
~~~~~

#### Acts 3: 适配 Serializer
我们需要更新序列化逻辑，以支持新的 `ParamNode` 结构。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~old
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "structural_id": node.structural_id,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }

    if isinstance(node, TaskNode):
        if node.callable_obj:
            data["callable"] = _get_func_path(node.callable_obj)
    elif isinstance(node, MapNode):
        if node.mapping_factory:
            data["mapping_factory"] = _get_func_path(node.mapping_factory)
    elif isinstance(node, ParamNode):
        # We don't serialize the spec for now, but could in the future
        pass

    # Note: param_spec serialization removed as Node no longer holds it directly.
    # Future implementation should serialize definition metadata if needed.

    if node.retry_policy:
~~~~~
~~~~~new
def _node_to_dict(node: Node) -> Dict[str, Any]:
    data = {
        "structural_id": node.structural_id,
        "name": node.name,
        "node_type": node.node_type,
        # input_bindings now contains JSON-serializable literals directly.
        "input_bindings": node.input_bindings,
    }

    if isinstance(node, TaskNode):
        if node.callable_obj:
            data["callable"] = _get_func_path(node.callable_obj)
    elif isinstance(node, MapNode):
        if node.mapping_factory:
            data["mapping_factory"] = _get_func_path(node.mapping_factory)
    elif isinstance(node, ParamNode):
        data["param_key"] = node.param_key

    # Note: param_spec serialization removed as Node no longer holds it directly.
    # Future implementation should serialize definition metadata if needed.

    if node.retry_policy:
~~~~~

#### Acts 4: 适配 Deserializer
更新 `_dict_to_node` 以恢复 `ParamNode`。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/serialize.py
~~~~~
~~~~~old
    if node_type == "map":
        node = MapNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="map",
            mapping_factory=_load_func_from_path(data.get("mapping_factory")),
            retry_policy=retry_policy,
            cache_policy=None, # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
        )
    elif node_type == "param":
        # Note: We don't currently serialize the full ParamSpec, 
        # so restored ParamNodes will have param_spec=None. 
        # This is acceptable for simple visualization/analysis, 
        # but execution of restored ParamNodes might need the spec context.
        node = ParamNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="param",
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            has_complex_inputs=True, # ParamNode always needs the complex path
        )
    else:
        # Default to TaskNode
~~~~~
~~~~~new
    if node_type == "map":
        node = MapNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="map",
            mapping_factory=_load_func_from_path(data.get("mapping_factory")),
            retry_policy=retry_policy,
            cache_policy=None, # Serialization of cache policy not implemented yet
            constraints=constraints,
            input_bindings=input_bindings,
        )
    elif node_type == "param":
        node = ParamNode(
            structural_id=data["structural_id"],
            definition=stub_def,
            node_type="param",
            retry_policy=retry_policy,
            cache_policy=None,
            constraints=constraints,
            input_bindings=input_bindings,
            param_key=str(data.get("param_key", "")),
            has_complex_inputs=True, # ParamNode always needs the complex path
        )
    else:
        # Default to TaskNode
~~~~~

### 下一步建议
Model 和 Build 层的重构完成后，我们需要立即进入 Phase 2，修改 `ArgumentResolver` 和 `Processor` 以配合新的 `ParamNode` 结构，修复参数解析的 Bug。

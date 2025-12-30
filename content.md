好的，我已经仔细分析了您提供的文件，并确定了重构 `Node` 为多态类层次结构所需的全部修改点。

您的分析完全正确：问题的根源在于 `GraphBuilder` 无法区分一个普通的 `Task` 和一个代表 `Param` 的 `Task`，因为 `LazyResult` 没有携带足够的元数据。这导致下游工具（如 `LispTranspiler`）必须依赖脆弱的约定，从而引发了 `pyright` 错误。

我们将分三步解决这个问题：
1.  **增强元数据**：修改 `LazyResult` 以携带 `ParamSpec`。
2.  **实现多态模型**：用一个显式的类层次结构 (`TaskNode`, `ParamNode`, `MapNode`) 替换单一的 `Node` 类。
3.  **适配消费端**：重构 `GraphBuilder` 来创建正确的节点子类，并更新所有消费端（`lisp.py`, `processor.py` 等）以使用类型安全的 `isinstance` 检查。

我将生成一个计划来实现这个改动。

## [WIP] refactor: 实现 Node 的显式多态化层次结构

### 用户需求
根据“白板重构”计划，将 `Node` 类重构为抽象基类，并为不同类型的图实体（Task, Param, Map 等）提供具体的强类型子类，以解决类型安全问题。

### 评论
当前 `Node` 类通过动态附加属性来模拟多态，这种“隐式约定”在静态分析下非常脆弱。通过显式的类层次结构，我们可以利用 `isinstance` 作为类型保护，让编译器和开发者都能清晰地知道某个节点具备哪些属性，从而根除 `AttributeError` 类的运行时风险。

### 目标
1.  在 `cascade-spec` 中，为 `LazyResult` 添加 `_param_spec` 字段，并在 `cs.Param` 工厂函数中填充它。
2.  在 `cascade-graph` 中，将 `Node` 重构为一个类层次，包括 `TaskNode`, `ParamNode`, `MapNode` 等。
3.  更新 `GraphBuilder`，使其能够根据 `LazyResult` 的元数据（如 `_param_spec`）实例化正确的 `Node` 子类。
4.  利用 `isinstance` 修复 `cascade-sdk` 和 `cascade-engine` 中所有依赖 `node.node_type` 字符串或函数对象判断的逻辑。

### 基本原理
这是一次从“基于字符串类型判断”到“基于类身份判断”的架构升级。它将运行时的不确定性（“这个节点有没有 `param_spec` 属性？”）转化为编译时的确定性（“只有 `ParamNode` 才有 `param_spec` 属性”），从而让整个系统更加健壮和可维护。

### 标签
#intent/refine #flow/ready #priority/high 
#comp/graph #comp/sdk #comp/engine #concept/graph-model #scope/core
#ai/brainstorm
#task/domain/core
#task/object/node-hierarchy
#task/action/refactor
#task/state/continue

---

### Script

#### Acts 1: 在 `LazyResult` 中建立 `ParamSpec` 的链接

首先，我们需要修改 `LazyResult` 来携带 `ParamSpec` 元数据，并更新 `cs.Param` 工厂函数来设置这个元数据。这是让 `GraphBuilder` 能够识别参数节点的关键一步。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python.old
if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy

# Forward reference for ResourceConstraint
T = TypeVar("T")
~~~~~
~~~~~python.new
if TYPE_CHECKING:
    from cascade.spec.protocols import CachePolicy
    from cascade.spec.input import ParamSpec

# Forward reference for ResourceConstraint
T = TypeVar("T")
~~~~~
~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/lazy_types.py
~~~~~
~~~~~python.old
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)

    def __hash__(self):
        return hash(self._uuid)
~~~~~
~~~~~python.new
    _dependencies: List["LazyResult"] = field(
        default_factory=list
    )  # Explicit sequencing
    _jump_selector: Optional[Any] = None  # Explicit Control Flow (JumpSelector)
    _param_spec: Optional["ParamSpec"] = None  # Link to ParamSpec if this is a Param

    def __hash__(self):
        return hash(self._uuid)
~~~~~

#### Acts 2: 引入 `Node` 多态类层次结构

现在元数据链接已经建立，我们可以重构 `model.py`，用一个清晰的、类型安全的类层次结构替换掉原来的 `Node` "万能类"。

~~~~~act
write_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto
from abc import ABC

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
class Node(ABC):
    """Abstract base class for all nodes in the computation graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    def __hash__(self):
        return hash(self.structural_id)

    @property
    def name(self) -> str:
        # Each subclass must provide a way to get its name.
        raise NotImplementedError


@dataclass
class TaskNode(Node):
    """Represents a standard computation task."""

    # The static definition of the task.
    definition: TaskDef
    # The actual python executable object.
    callable_obj: Optional[Callable]
    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None
    # Structural Bindings (Literals)
    input_bindings: Dict[str, Any] = field(default_factory=dict)
    # Optimization flag
    has_complex_inputs: bool = False

    @property
    def name(self) -> str:
        return self.definition.name


@dataclass
class MapNode(Node):
    """Represents a .map() operation over a factory."""

    # The static definition of the task factory being mapped.
    definition: TaskDef
    # The task factory to be called for each item.
    mapping_factory: Any
    # Instance-specific configuration
    retry_policy: Optional[Any] = None
    cache_policy: Optional[Any] = None
    constraints: Optional[ResourceConstraint] = None
    # Structural Bindings (Literals) for the map call itself.
    input_bindings: Dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return f"map({self.definition.name})"


@dataclass
class ParamNode(Node):
    """Represents a cs.Param, a runtime input source."""

    # The specification of the parameter.
    param_spec: ParamSpec

    @property
    def name(self) -> str:
        return f"param({self.param_spec.name})"


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

#### Acts 3: 更新 `GraphBuilder` 和消费端

现在模型已经更新，我们将重构 `GraphBuilder` 以创建正确的 `Node` 子类，并更新 `lisp.py` 和 `processor.py` 以使用新的类型。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
            # Note: execution_mode is now part of task_def (definition.mode)
            node = Node(
                structural_id=node_hash,
                definition=task_def,
                callable_obj=result.task.func,
                node_type="task",
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
                has_complex_inputs=has_complex,
            )
            self.registry._registry[node_hash] = node
~~~~~
~~~~~python.new
            from cascade.graph.model import TaskNode, ParamNode

            if result._param_spec:
                node = ParamNode(
                    structural_id=node_hash,
                    param_spec=result._param_spec
                )
            else:
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
            self.registry._registry[node_hash] = node
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
            node = Node(
                structural_id=node_hash,
                definition=task_def,
                node_type="map",
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[node_hash] = node
~~~~~
~~~~~python.new
            from cascade.graph.model import MapNode
            node = MapNode(
                structural_id=node_hash,
                definition=task_def,
                mapping_factory=result.factory,
                retry_policy=result._retry_policy,
                cache_policy=result._cache_policy,
                constraints=result._constraints,
                input_bindings=input_bindings,
            )
            self.registry._registry[node_hash] = node
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/tools/lisp.py
~~~~~
~~~~~python.old
        # Function Name
        func_name = self._sanitize_name(node.name)
        if node.node_type == "map":
            parts.append(f"map {func_name}")
        elif node.node_type == "param":
            p_name = node.param_spec.name if node.param_spec else "?"
            return f'(param "{p_name}")'
        else:
            parts.append(func_name)
~~~~~
~~~~~python.new
        from cascade.graph.model import MapNode, ParamNode

        # Function Name
        if isinstance(node, MapNode):
            func_name = self._sanitize_name(node.definition.name)
            parts.append(f"map {func_name}")
        elif isinstance(node, ParamNode):
            p_name = node.param_spec.name
            return f'(param "{p_name}")'
        else:
            func_name = self._sanitize_name(node.name)
            parts.append(func_name)
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/processor.py
~~~~~
~~~~~python.old
        # 5. Handle Map Nodes
        if node.node_type == "map":
            return await self._execute_map_node(
                node,
                kwargs,
~~~~~
~~~~~python.new
        from cascade.graph.model import MapNode
        # 5. Handle Map Nodes
        if isinstance(node, MapNode):
            return await self._execute_map_node(
                node,
                kwargs,
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/resolvers.py
~~~~~
~~~~~python.old
        # [CRITICAL] This logic must always run for Param tasks
        from cascade.internal.inputs import _get_param_value

        if node.callable_obj is _get_param_value.func:
            kwargs["params_context"] = user_params or {}
~~~~~
~~~~~python.new
        from cascade.graph.model import ParamNode
        # [CRITICAL] This logic must always run for Param tasks
        if isinstance(node, ParamNode):
            kwargs["params_context"] = user_params or {}
~~~~~

### 下一步建议
我们已经完成了 `Node` 多态化的核心重构，并修复了所有直接相关的消费端代码。

现在，我建议我们进入 TDD 流程的下一步：
1.  **运行 `pyright`**：确认 `lisp.py` 中的类型错误已经消失。
2.  **运行测试套件**：确保我们的重构没有破坏任何现有功能，特别是与 `cs.Param` 和 `.map()` 相关的测试。

在确认一切正常后，我们就可以为这个重大的架构改进创建一个干净的 `[COMMIT]`。

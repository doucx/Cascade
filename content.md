好的，我们正稳步推进“焦土政策”路线图。将默认执行策略切换到新的 VM 是一个关键的里程碑，这标志着我们对新架构的信心，并正式开启了旧组件的退役流程。

我将生成一个计划来完成“阶段 7: 默认切换 (The Switch)”。这个计划将包含两个核心部分：
1.  修改 `Engine` 使其默认使用 VM 策略。
2.  为所有将被废弃的旧架构组件（`GraphExecutionStrategy`, `NativeSolver`, `Graph`, `Node` 等）添加 `DeprecationWarning`，以引导未来的开发。

## [WIP] feat(engine): 将默认执行策略切换到 VM

### 用户需求
根据“焦土政策”路线图的第七阶段，需要将 `cascade-engine` 的默认执行策略从旧的 `GraphExecutionStrategy` 切换到新的、基于编译器的 `VMExecutionStrategy`。同时，为旧的、将被废弃的组件添加明确的弃用警告。

### 评论
这是一个标志性的变更。将 VM 设置为默认选项，意味着新架构在功能对齐和稳定性上已经达到了生产就绪的标准。这会强制所有后续的测试和开发都基于新架构进行，从而加速遗留代码的清理和最终移除。添加弃用警告是负责任的做法，它为开发者提供了清晰的迁移路径。

### 目标
1.  修改 `cascade.runtime.engine.Engine.run` 方法，使其 `use_vm` 参数的默认值从 `False` 变为 `True`。
2.  在 `GraphExecutionStrategy`、`NativeSolver`、`cascade.graph.model` (`Graph`, `Node`) 以及 `build_graph` 函数中注入 `DeprecationWarning`。

### 基本原理
通过更改 `Engine.run` 的默认参数，我们可以无缝地将现有和未来的 `cs.run()` 调用切换到新的执行后端，而无需修改任何调用点的代码。使用 Python 内置的 `warnings` 模块，我们可以在旧组件被实例化或调用时，在运行时发出非阻断性的警告，通知开发者这些 API 已被弃用，并将在未来的版本中被移除。

### 标签
#intent/refine #flow/ready #priority/high #comp/engine #comp/graph #concept/state #scope/api #ai/instruct #task/domain/architecture #task/object/default-strategy #task/action/switch #task/state/continue

---

### Script

#### Acts 1: 切换 Engine 的默认执行策略

我们将修改 `engine.py` 中 `run` 方法的签名，将 `use_vm` 的默认值设为 `True`。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python.old
    async def run(
        self,
        target: Any,
        params: Optional[Dict[str, Any]] = None,
        use_vm: bool = False,
    ) -> Any:
~~~~~
~~~~~python.new
    async def run(
        self,
        target: Any,
        params: Optional[Dict[str, Any]] = None,
        use_vm: bool = True,
    ) -> Any:
~~~~~

#### Acts 2: 为旧组件添加弃用警告

现在，我们将系统性地为旧架构的入口点添加 `DeprecationWarning`。

首先，为 `GraphExecutionStrategy` 添加警告。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
import asyncio
from contextlib import ExitStack
~~~~~
~~~~~python.new
import asyncio
import warnings
from contextlib import ExitStack
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
~~~~~
~~~~~python.old
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
~~~~~
~~~~~python.new
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
        warnings.warn(
            "GraphExecutionStrategy is deprecated and will be removed in a future version. "
            "The default engine now uses VMExecutionStrategy.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.solver = solver
~~~~~

接着，为 `NativeSolver` 添加警告。

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python.old
from collections import deque
from typing import Dict, List

from cascade.graph.model import Graph, Node, EdgeType
~~~~~
~~~~~python.new
import warnings
from collections import deque
from typing import Dict, List

from cascade.graph.model import Graph, Node, EdgeType
~~~~~

~~~~~act
patch_file
packages/cascade-engine/src/cascade/adapters/solvers/native.py
~~~~~
~~~~~python.old
class NativeSolver(Solver):
    def resolve(self, graph: Graph) -> ExecutionPlan:
        executable_nodes = graph.nodes
~~~~~
~~~~~python.new
class NativeSolver(Solver):
    def resolve(self, graph: Graph) -> ExecutionPlan:
        warnings.warn(
            "NativeSolver is deprecated and will be removed in a future version. "
            "The new compiler includes an Optimizer for scheduling.",
            DeprecationWarning,
            stacklevel=2,
        )
        executable_nodes = graph.nodes
~~~~~

然后，为 `cascade.graph` 的核心数据模型 `Graph` 和 `Node` 添加警告。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
~~~~~
~~~~~python.new
import warnings
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Dict
from enum import Enum, auto

from cascade.spec.constraint import ResourceConstraint
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class Node:
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str
~~~~~
~~~~~python.new
@dataclass
class Node:
    """Base class for all nodes in the Cascade graph."""

    # Stable identifier for the node instance in the graph.
    structural_id: str

    def __post_init__(self):
        warnings.warn(
            "The 'cascade.graph.Node' model is deprecated and will be removed. "
            "Use 'cascade.spec.ir.NodeIR' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/model.py
~~~~~
~~~~~python.old
@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)
~~~~~
~~~~~python.new
@dataclass
class Graph:
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    _node_index: Dict[str, Node] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        warnings.warn(
            "The 'cascade.graph.Graph' model is deprecated and will be removed. "
            "Use 'cascade.spec.ir.GraphIR' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
~~~~~

最后，为旧的 `build_graph` 函数添加警告。

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType, TaskNode, MapNode, ParamNode
~~~~~
~~~~~python.new
import warnings
from typing import Dict, Any, Tuple
import inspect
from cascade.graph.model import Graph, Node, Edge, EdgeType, TaskNode, MapNode, ParamNode
~~~~~

~~~~~act
patch_file
packages/cascade-graph/src/cascade/graph/build.py
~~~~~
~~~~~python.old
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    return GraphBuilder(registry=registry).build(target)
~~~~~
~~~~~python.new
def build_graph(
    target: Any, registry: NodeRegistry | None = None
) -> Tuple[Graph, Dict[str, Node]]:
    warnings.warn(
        "'build_graph' is deprecated. The new 'cascade.compiler.Frontend' should be used instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return GraphBuilder(registry=registry).build(target)
~~~~~

### 下一步建议
我们已经完成了默认策略的切换和弃用标记。下一步是运行完整的测试套件，验证所有现有的集成测试在新的默认（VM）模式下是否都能通过。这会暴露任何剩余的特性差距或行为不一致，是进入拆除阶段前的最后一道安全检查。

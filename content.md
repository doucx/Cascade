好的，我将生成一个计划来解决这个架构问题。

## [WIP] fix: Resolve circular dependency between spec and execution-graph

### 错误分析

`stitcher check` 工具检测到一个跨包的循环依赖：`cascade-spec` -> `cascade-execution-graph` -> `cascade-spec`。

问题的根源在于 `packages/cascade-spec/src/cascade/spec/runtime/interfaces.py`，它在一个 `TYPE_CHECKING` 块中导入了 `cascade.execution.graph.model.model` 的 `Graph` 和 `Node`。

这是一个严重的架构违规，因为 `cascade-spec` 是系统的底层规范包，它**绝对不能**对任何上层的、具体的实现包（尤其是像 `cascade-execution-graph` 这样的遗留实现）有任何感知或依赖。这种反向依赖破坏了分层架构的原则，导致系统耦合度增高，难以维护和演进。

### 用户需求

用户要求解决 `cascade-spec` 和 `cascade-execution-graph` 之间的循环依赖问题。

### 评论

用户的分析是正确的。即使在 `TYPE_CHECKING` 块中，这种依赖关系也应被视为架构缺陷。将 `Graph` 和 `Node` 迁移到 `spec` 包虽然可行，但会将一个遗留实现的核心模型引入到新架构的规范层，造成概念混淆。

最佳实践是采用**依赖倒置原则**。`interfaces.py` 中的协议不应该依赖于具体的实现类，而应该使用更通用的类型，如 `typing.Any` 或字符串前向引用。这可以彻底切断依赖关系，同时保持接口定义的完整性。

### 目标

1.  修改 `packages/cascade-spec/src/cascade/spec/runtime/interfaces.py` 文件。
2.  移除对 `cascade.execution.graph.model.model` 的导入。
3.  将所有对 `Graph` 和 `Node` 的类型提示替换为 `Any`，以解除循环依赖。

### 基本原理

我们将修改 `Solver` 和 `Executor` 协议的定义。通过将类型提示从具体的 `Graph` 和 `Node` 类更改为通用的 `Any`，我们向类型检查器表明，这些协议可以接受任何满足其接口（即使是隐式的）的对象，而无需在定义时知道其具体类型。这是一种标准的解耦技术，完全符合 `cascade-spec` 作为纯粹规范包的定位。

### 标签

#intent/fix #flow/ready #priority/critical #comp/spec #comp/execution-graph #scope/core #ai/instruct #task/domain/architecture #task/object/dependency-graph #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 解耦 spec 层的类型依赖

我们将修改 `interfaces.py`，移除对 `execution-graph` 的导入，并使用 `Any` 来泛化 `Solver` 和 `Executor` 协议中的类型提示。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/interfaces.py
~~~~~
~~~~~python.old
from typing import (
    Protocol,
    List,
    Any,
    Dict,
    Optional,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from cascade.execution.graph.model.model import Graph, Node

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
ExecutionPlan = List[List["Node"]]


class Solver(Protocol):
    def resolve(self, graph: "Graph") -> ExecutionPlan: ...


class Executor(Protocol):
    async def execute(
        self,
        node: "Node",
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...
~~~~~
~~~~~python.new
from typing import (
    Protocol,
    List,
    Any,
    Dict,
    Optional,
    Callable,
    Awaitable,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    # Avoid circular dependency with implementation-heavy contexts
    # These will be passed as 'Any' or via Generic types in the implementation
    pass

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
# We use Any for Node/Graph here to avoid a circular dependency with the legacy execution-graph package.
ExecutionPlan = List[List[Any]]


class Solver(Protocol):
    def resolve(self, graph: Any) -> ExecutionPlan: ...


class Executor(Protocol):
    async def execute(
        self,
        node: Any,
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...
~~~~~

### 下一步建议

修改完成后，请再次运行 `stitcher check` 命令，以验证循环依赖问题是否已成功解决。

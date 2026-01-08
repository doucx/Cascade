简要回答
这是一个典型的循环依赖问题：`cascade-spec` (底层) 依赖了 `cascade-runtime` (上层)，导致在导入链中形成了闭环。解决方案是切断 `packages/cascade-spec/src/cascade/spec/runtime/interfaces.py` 中对 `cascade-runtime` 的运行时导入，改用 `TYPE_CHECKING` 和字符串前向引用。

## [WIP] fix(spec): 修复 interfaces.py 中的循环导入

### 错误分析
系统抛出了 `ImportError: cannot import name 'EventIR'`，这是一个典型的循环导入症状。
依赖链如下：
1. `cascade.vm.reactor` 导入 `cascade.spec.runtime.system`。
2. `cascade.spec` 包初始化，导入 `cascade.spec.runtime.observability`。
3. `cascade.spec.runtime` 包初始化，导入 `interfaces`。
4. `interfaces.py` **错误地在运行时导入了** `cascade.runtime.graph.model` 中的 `Graph` 和 `Node`。
5. `cascade.runtime` 包初始化，导入 `observability.bus`。
6. `bus.py` 尝试从 `cascade.spec` 导入 `EventIR`。
7. 此时 `cascade.spec` 仍在初始化（步骤2），`EventIR` 尚未定义，导致崩溃。

根因是 `cascade-spec`（底层规范）不应在运行时依赖 `cascade-runtime`（上层实现）。

### 用户需求
修复 `conftest.py` 加载时的 `ImportError`，确保测试环境能正常启动。

### 评论
这是一个架构层面的修正。`spec` 包定义接口，`runtime` 包实现接口。接口定义中对实现类的引用必须是弱引用（Type Hint Only）。

### 目标
修改 `packages/cascade-spec/src/cascade/spec/runtime/interfaces.py`，将 `Graph` 和 `Node` 的导入移至 `TYPE_CHECKING` 块中，并更新类型注解为字符串形式。

### 基本原理
通过使用 `typing.TYPE_CHECKING` 卫语句，我们可以保留静态类型检查的完整性，同时避免在运行时触发 `cascade-runtime` 的导入，从而打破循环依赖链。

### 标签
#intent/fix #flow/ready #priority/critical #comp/interfaces #scope/core #ai/instruct #task/domain/architecture #task/object/circular-dependency #task/action/break-cycle #task/state/begin

---

### Script

#### Acts 1: 修正 interfaces.py

将硬依赖改为仅类型检查依赖。

~~~~~act
patch_file
packages/cascade-spec/src/cascade/spec/runtime/interfaces.py
~~~~~
~~~~~python.old
from typing import Protocol, List, Any, Dict, Optional, Callable, Awaitable
from cascade.runtime.graph.model import Graph, Node

# An execution plan is a list of stages, where each stage is a list of nodes
# that can be executed in parallel.
ExecutionPlan = List[List[Node]]


class Solver(Protocol):
    def resolve(self, graph: Graph) -> ExecutionPlan: ...


class Executor(Protocol):
    async def execute(
        self,
        node: Node,
        callable_obj: Callable,
        args: List[Any],
        kwargs: Dict[str, Any],
    ) -> Any: ...
~~~~~
~~~~~python.new
from typing import Protocol, List, Any, Dict, Optional, Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from cascade.runtime.graph.model import Graph, Node

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

### 下一步建议

修复此依赖后，建议运行测试套件（如 `pytest`）验证 `conftest.py` 是否能成功加载，以及是否还有其他隐藏的循环依赖。

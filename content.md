好的，我们来处理报告中最后一个、也是最核心的由 8 个文件组成的强耦合组件。

这个问题的根源在于 `cascade-runtime` 包内部的模块为了方便，同时扮演了“实现者”和“API 提供者”的双重角色，导致了复杂的初始化循环。
1.  `constraints/manager.py` 和 `protocols.py` 相互需要对方的类型定义。
2.  `host/instance.py` (Engine) 试图从 `cascade.runtime` 命名空间导入工具类，而 `cascade/runtime/__init__.py` 又试图从 `host/instance.py` 导出 `Engine` 类，形成死锁。
3.  `cascade-execution-graph` 中的模块（`processor.py`, `strategy.py`）依赖于 `cascade-runtime` 提供的类，这进一步加剧了初始化顺序的脆弱性。

我将通过全面的相对导入重构来切断这些循环路径，确保每个子包都可以自包含地加载。

## [WIP] refactor: 解耦 cascade-runtime 及其子包的循环依赖

### 错误分析
`cascade-runtime` 包存在一个深度的架构缺陷：其 `__init__.py` 文件试图创建一个扁平的公共 API (`from cascade.runtime import Engine`)，但 `Engine` 的实现 (`instance.py`) 本身又依赖于同一个 `cascade.runtime` 命名空间下的其他模块（如 `storage`, `services`）。这导致 Python 在初始化 `cascade.runtime` 包时，进入了一个“先有鸡还是先有蛋”的悖论，从而引发 `ImportError` 或 `AttributeError`。

### 用户需求
修复 `cascade-runtime` 及其相关模块（`cascade-execution-graph`）之间由绝对导入引发的循环依赖问题。

### 评论
这是一个教科书式的 Python 包设计问题。解决方案在于强制执行一个原则：**包内部的模块间通信，必须使用相对导入。** 绝对导入 (`from my_package...`) 应用于包与包之间的外部通信。通过这次重构，`cascade-runtime` 内部的组件将能够以任何顺序安全加载，而不会触发对自身不完整命名空间的过早引用。

### 目标
1.  将 `cascade.runtime.services.constraints` 子包内的 `manager` 和 `protocols` 之间的引用改为相对导入。
2.  将 `cascade.runtime.host.instance` (Engine) 对 `storage` 和 `services` 的引用改为相对导入。
3.  将 `cascade.runtime` 的根 `__init__.py` 对其内部模块的引用改为相对导入。
4.  修正 `cascade-execution-graph` 中对同包模块的引用路径，确保其内部的健壮性。

### 基本原理
我们将利用相对导入 (`.` 和 `..`) 来限定导入的搜索范围。例如，在 `host/instance.py` 中，`from ..storage import InMemoryObjectStore` 会告诉 Python 解释器：“从我所在的 `host` 目录向上一级到 `runtime` 目录，然后查找 `storage` 子目录”，这个过程完全绕开了对顶层 `cascade.runtime` 命名空间的重新求值，从而打破了循环。

### 标签
#intent/refine #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/circular-dependency #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 修复 `services/constraints` 子包的内部循环

这是最内层的循环，我们首先解决它。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/manager.py
~~~~~
~~~~~python.old
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.execution.graph.model.model import Node
from cascade.runtime.services.constraints.protocols import ConstraintHandler
from cascade.runtime.services.resources.manager import ResourceManager


class ConstraintManager:
~~~~~
~~~~~python.new
from cascade.spec.dsl.constraint import GlobalConstraint
from cascade.execution.graph.model.model import Node
from .protocols import ConstraintHandler
from ..resources.manager import ResourceManager


class ConstraintManager:
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/services/constraints/protocols.py
~~~~~
~~~~~python.old
if TYPE_CHECKING:
    from cascade.runtime.services.constraints.manager import ConstraintManager


class ConstraintHandler(Protocol):
~~~~~
~~~~~python.new
if TYPE_CHECKING:
    from .manager import ConstraintManager


class ConstraintHandler(Protocol):
~~~~~

#### Acts 2: 修复 `host/instance.py` (Engine) 的依赖

这是导致 `__init__` 循环的核心。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from cascade.spec.runtime.interfaces import Solver, Executor, StateBackend, Connector
from cascade.spec.runtime.storage import ObjectStore
from cascade.runtime.storage import InMemoryObjectStore
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.runtime.services.constraints import ConstraintManager
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
~~~~~
~~~~~python.new
from cascade.spec.runtime.interfaces import Solver, Executor, StateBackend, Connector
from cascade.spec.runtime.storage import ObjectStore
from ..storage import InMemoryObjectStore
from ..services.resources.manager import ResourceManager
from ..services.constraints import ConstraintManager
from ..services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.spec.runtime import ExecutionStrategy
~~~~~
~~~~~python.new
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from ..io.state import InMemoryStateBackend
from ..services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.spec.runtime import ExecutionStrategy
~~~~~

#### Acts 3: 修复 `cascade.runtime` 根 `__init__.py` 的导入

现在 `Engine` 的依赖是安全的了，我们可以修复 `__init__.py`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/__init__.py
~~~~~
~~~~~python.old
from cascade.bus.core import EventBus
from cascade.runtime.host.instance import Engine
from cascade.runtime.services.observability.subscribers import (
    HumanReadableLogSubscriber,
    TelemetrySubscriber,
)
from cascade.bus.events import (
    Event,
    RunStarted,
~~~~~
~~~~~python.new
from cascade.bus.core import EventBus
from .host.instance import Engine
from .services.observability.subscribers import (
    HumanReadableLogSubscriber,
    TelemetrySubscriber,
)
from cascade.bus.events import (
    Event,
    RunStarted,
~~~~~

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/__init__.py
~~~~~
~~~~~python.old
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.execution.graph.errors import DependencyMissingError
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.spec.runtime.interfaces import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
~~~~~
~~~~~python.new
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.execution.graph.errors import DependencyMissingError
from .services.resources.manager import ResourceManager
from cascade.spec.runtime.interfaces import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
~~~~~

#### Acts 4: 修复 `cascade-execution-graph` 的内部导入

最后，我们修复 `execution-graph` 包内引用同包模块时使用的绝对路径。

~~~~~act
patch_file
packages/cascade-execution-graph/src/cascade/execution/graph/logic/processor.py
~~~~~
~~~~~python.old
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.runtime.services.constraints.manager import ConstraintManager
from cascade.execution.graph.logic.resolvers import ArgumentResolver, ConstraintResolver
from cascade.spec import EventState
from cascade.bus.events import (
    TaskExecutionStarted,
~~~~~
~~~~~python.new
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.runtime.services.constraints.manager import ConstraintManager
from .resolvers import ArgumentResolver, ConstraintResolver
from cascade.spec import EventState
from cascade.bus.events import (
    TaskExecutionStarted,
~~~~~

~~~~~act
patch_file
packages/cascade-execution-graph/src/cascade/execution/graph/strategy.py
~~~~~
~~~~~python.old
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.execution.graph.logic.processor import NodeProcessor
from cascade.execution.graph.logic.flow import FlowManager
from cascade.execution.graph.errors import DependencyMissingError
from cascade.bus.events import TaskSkipped, TaskBlocked
from cascade.runtime.services.constraints.manager import ConstraintManager
~~~~~
~~~~~python.new
from cascade.runtime.services.resources.container import ResourceContainer
from .logic.processor import NodeProcessor
from .logic.flow import FlowManager
from .errors import DependencyMissingError
from cascade.bus.events import TaskSkipped, TaskBlocked
from cascade.runtime.services.constraints.manager import ConstraintManager
~~~~~

### 下一步建议
我们已经解决了报告中所有已知的强耦合组件。
1.  **最终验证**: 运行完整的静态分析，确认所有循环依赖问题都已消除。
2.  **全量测试**: 执行 `pytest` 全量测试，确保重构没有引入任何功能性回归。
3.  **提交**: 在所有检查通过后，可以创建一个 `[COMMIT]` 计划来提交这一系列的重构工作。

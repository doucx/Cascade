我们将按照代码审计的结果，执行第一阶段任务：**优化 `__init__.py` 的导出与层级提升**。

## [WIP] 计划：提升组件导出层级

### 标签
#intent/refine #flow/ready #priority/medium
#comp/compiler #comp/runtime #scope/dx
#task/domain/architecture #task/object/exports #task/action/elevation
#task/state/begin

### 目标分析
1.  **`cascade-compiler`**: 将 `IRGenerator`（前端）、`Builder`（后端）以及核心 Policy/Context 协议提升至顶层入口。
2.  **`cascade-runtime`**: 提升常用事件类（如 `TaskExecutionFinished`）和 `TelemetrySubscriber`，增强 API 的可用性。
3.  **`cascade-common`**: 确保命名空间一致性。
---

### Script

#### Acts 1: 提升 `cascade-compiler` 核心入口

我们通过 `write_file` 更新 `cascade-compiler` 的根 `__init__.py`，使其成为编译器的单一权威入口点，并同步清理 backend/frontend 的导出以保持一致。

~~~~~act
write_file
packages/cascade-compiler/src/cascade/compiler/__init__.py
~~~~~
~~~~~python
from .backend.builder import Builder
from .frontend.generator import IRGenerator, GenerationResult
from .backend.expansion.context import ExpansionContext
from .backend.wiring.context import WiringContext
from .backend.expansion.protocol import ExpansionPolicy
from .backend.wiring.protocol import WiringPolicy

__all__ = [
    "Builder",
    "IRGenerator",
    "GenerationResult",
    "ExpansionContext",
    "WiringContext",
    "ExpansionPolicy",
    "WiringPolicy",
]
~~~~~

#### Acts 2: 丰富 `cascade-runtime` 的事件与服务导出

将 `TelemetrySubscriber` 和所有具体的生命周期事件提升到 `cascade.runtime` 命名空间下。

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/__init__.py
~~~~~
~~~~~python
from cascade.runtime.services.observability.bus import EventBus
from cascade.runtime.host.instance import Engine
from cascade.runtime.services.observability.subscribers import (
    HumanReadableLogSubscriber,
    TelemetrySubscriber,
)
from cascade.runtime.services.observability.events import (
    Event,
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
    TaskBlocked,
    ConnectorConnected,
    ConnectorDisconnected,
)
from cascade.execution.graph.errors import DependencyMissingError
from cascade.runtime.services.resources.manager import ResourceManager
from cascade.spec.runtime.interfaces import ExecutionPlan, Solver, Executor, CachePolicy

__all__ = [
    "EventBus",
    "Engine",
    "HumanReadableLogSubscriber",
    "TelemetrySubscriber",
    "Event",
    "RunStarted",
    "RunFinished",
    "TaskExecutionStarted",
    "TaskExecutionFinished",
    "TaskSkipped",
    "TaskRetrying",
    "TaskBlocked",
    "ConnectorConnected",
    "ConnectorDisconnected",
    "DependencyMissingError",
    "ResourceManager",
    "ExecutionPlan",
    "Solver",
    "Executor",
    "CachePolicy",
]
~~~~~

### 下一步建议
我们已经优化了导出层级。接下来，根据审计报告的第二项，我们应该开始**测试套件优化**：
- 将 `EventDrivenRunner` 从 `cascade-vm` 移动到 `cascade-test-utils`，因为它是一个纯粹的测试支架，不应出现在物理引擎的生产路径中。
- 检查 `test-utils` 的 `__init__.py` 导出，确保这些工具能被全局测试轻松引用。

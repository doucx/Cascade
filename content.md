好的，你提供的 traceback 非常清晰。我的上一个计划引入了一个错误的导入路径，导致了 `ImportError`。我将立即修复这个问题。

这是一个标准的 TDD 修补流程：你提供了失败的证据（RED 状态），现在我来修复它（进入 GREEN 状态）。

## [WIP] fix(runtime): 修正 Engine 中 ExecutionStrategy 的导入路径

### 错误分析
Traceback 明确指出 `from cascade.runtime.strategies import ExecutionStrategy` 导入失败。这是因为 `ExecutionStrategy` 协议（Protocol）被定义在 `cascade-spec` 包中，而不是 `cascade-runtime` 包。`rg` 的输出也证实了这一点，`ExecutionStrategy` 位于 `packages/cascade-spec/src/cascade/spec/runtime/strategies.py`。

我的上一个补丁错误地将导入源指向了 `cascade.runtime`，从而导致了这个模块加载错误。

### 用户需求
修复 `cascade.runtime.host.instance.py` 中的 `ImportError`，使其能够成功启动。

### 评论
这是一个在重构过程中常见的错误，即错误地引用了模块的位置。感谢你提供的即时反馈，这使得修复过程非常高效。遵循规范，将接口定义（`spec`）与实现（`runtime`）分离，可以使这类问题更容易被定位。

### 目标
1.  定位 `packages/cascade-runtime/src/cascade/runtime/host/instance.py` 文件中的错误导入语句。
2.  将其从 `from cascade.runtime.strategies import ExecutionStrategy` 修正为 `from cascade.spec.runtime import ExecutionStrategy`。

### 基本原理
`ExecutionStrategy` 是一个接口协议，是系统不同组件之间交互的契约。根据我们的架构原则，所有契约都应定义在 `cascade-spec` 包中。运行时 (`cascade-runtime`) 应该依赖并实现这个契约，而不是自己定义它。因此，导入路径必须指向 `cascade.spec.runtime`。

### 标签
#intent/fix #flow/ready #priority/critical #comp/runtime #scope/core #ai/instruct #task/domain/runtime #task/object/engine #task/action/decouple #task/state/continue

---

### Script

#### Acts 1: 修正错误的导入路径

我们将修改 `instance.py` 文件，将 `ExecutionStrategy` 的导入路径指向正确的 `cascade.spec.runtime` 模块。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/host/instance.py
~~~~~
~~~~~python.old
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.runtime.strategies import ExecutionStrategy


class Engine:
~~~~~
~~~~~python.new
from cascade.runtime.services.constraints.handlers import (
    PauseConstraintHandler,
    ConcurrencyConstraintHandler,
    RateLimitConstraintHandler,
)
from cascade.runtime.io.state import InMemoryStateBackend
from cascade.runtime.services.resources.container import ResourceContainer
from cascade.spec.runtime import ExecutionContext
from cascade.spec.runtime import ExecutionStrategy


class Engine:
~~~~~

### 下一步建议
修复此导入错误后，`Engine` 类的解耦就应该完成了。我们可以继续进行重构路线图的 **Phase 4: 依赖清理与配置 (Dependency Cleanup)**，即从 `cascade-runtime/pyproject.toml` 中移除不再需要的 `python-constraint` 依赖。

我已收到这些核心消费者的源文件上下文。我将立即修复 `cascade-application`、`cascade-library` 和 `cascade-sdk` 中因 `EventBus` 重构导致的导入错误。

这是本次重构的收尾阶段，旨在恢复整个 monorepo 核心链路的连通性。

## [WIP] refactor: 完成 monorepo 核心组件对 EventBus 的适配

### 用户需求

修复 `cascade-application`、`cascade-library` 和 `cascade-sdk` 中由于 `cascade-engine` 内 `MessageBus` 重命名为 `EventBus` 而引发的导入错误和类型不匹配问题。

### 评论

这是一个关键的同步步骤。虽然核心重构发生在 `cascade-engine` 内部，但作为其紧密耦合的兄弟包，SDK 和 Application 层必须立即跟进，否则将导致整个开发环境瘫痪。完成这一步后，Cascade 的核心执行链路将完全恢复正常，且具备了更清晰的语义划分。

### 目标

1.  更新 `cascade-application` 的 `CascadeApp`，使其使用 `EventBus` 进行运行时事件管理。
2.  更新 `cascade-library` 的 `SubflowProvider`，使其在启动子工作流时使用 `EventBus`。
3.  更新 `cascade-sdk` 的 `testing` 模块，将 `SpySubscriber` 的目标从 `MessageBus` 切换为 `EventBus`。

### 基本原理

我们将采用“从外向内”的修正方式，将所有指向 `cascade.runtime.bus.MessageBus` 的路径重定向到 `cascade.runtime.EventBus`。这利用了我们在 `cascade-engine` 中建立的统一导出机制。对于 `CascadeApp` 这种同时涉及 `common.messaging.bus`（UI 反馈）和 `runtime.EventBus`（系统事件）的复杂场景，重命名后两者的职责将变得一目了然。

### 标签

#intent/refine #flow/ready #priority/high #comp/engine #comp/sdk #comp/application #scope/api #ai/instruct #task/domain/architecture #task/object/event-bus #task/action/synchronize #task/state/end

---

### Script

#### Acts 1: 更新 `cascade-application` 的导入与逻辑

修复 `CascadeApp` 及其辅助组件对总线的引用。

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
~~~~~
~~~~~python.new
from cascade.runtime.engine import Engine
from cascade.runtime import EventBus
from cascade.runtime.events import (
~~~~~

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
class DryRunConsoleSubscriber:
    def __init__(self, bus: MessageBus):
        bus.subscribe(PlanAnalysisStarted, self.on_start)
        bus.subscribe(PlanNodeInspected, self.on_node)
~~~~~
~~~~~python.new
class DryRunConsoleSubscriber:
    def __init__(self, bus: EventBus):
        bus.subscribe(PlanAnalysisStarted, self.on_start)
        bus.subscribe(PlanNodeInspected, self.on_node)
~~~~~

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
        bus.set_renderer(self.renderer)

        # 3. Setup Event System
        self.event_bus = MessageBus()
        self.log_subscriber = HumanReadableLogSubscriber(self.event_bus)
~~~~~
~~~~~python.new
        bus.set_renderer(self.renderer)

        # 3. Setup Event System
        self.event_bus = EventBus()
        self.log_subscriber = HumanReadableLogSubscriber(self.event_bus)
~~~~~

~~~~~act
patch_file
packages/cascade-application/src/cascade/app/__init__.py
~~~~~
~~~~~python.old
    def dry_run(self) -> None:
        # Create a temporary local bus for the dry run report
        # We don't want to use the main app bus because dry_run
        # is a special analysis mode, not a "run".
        local_bus = MessageBus()
        DryRunConsoleSubscriber(local_bus)
~~~~~
~~~~~python.new
    def dry_run(self) -> None:
        # Create a temporary local bus for the dry run report
        # We don't want to use the main app bus because dry_run
        # is a special analysis mode, not a "run".
        local_bus = EventBus()
        DryRunConsoleSubscriber(local_bus)
~~~~~

#### Acts 2: 更新 `cascade-library` 的子流驱动

修复子流执行时对孤立总线的创建。

~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/subflow.py
~~~~~
~~~~~python.old
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus


class SubflowProvider(Provider):
~~~~~
~~~~~python.new
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime import EventBus


class SubflowProvider(Provider):
~~~~~

~~~~~act
patch_file
packages/cascade-library/src/cascade/providers/subflow.py
~~~~~
~~~~~python.old
    # Note: The subflow runs in isolation. It does not share the parent's
    # resource manager or event bus.
    # For now, subflow logs are not forwarded to the parent bus to keep things clean.
    # Errors will propagate as exceptions.
    sub_bus = MessageBus()
    sub_engine = Engine(
        solver=NativeSolver(),
~~~~~
~~~~~python.new
    # Note: The subflow runs in isolation. It does not share the parent's
    # resource manager or event bus.
    # For now, subflow logs are not forwarded to the parent bus to keep things clean.
    # Errors will propagate as exceptions.
    sub_bus = EventBus()
    sub_engine = Engine(
        solver=NativeSolver(),
~~~~~

#### Acts 3: 更新 `cascade-sdk` 的测试工具

修复 `SpySubscriber` 对总线的注入。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
from cascade.adapters.executors.local import LocalExecutor

from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.spec.protocols import (
~~~~~
~~~~~python.new
from cascade.adapters.executors.local import LocalExecutor

from cascade.runtime.engine import Engine
from cascade.runtime import EventBus
from cascade.runtime.events import Event
from cascade.spec.protocols import (
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/testing.py
~~~~~
~~~~~python.old
class SpySubscriber:
    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)
~~~~~
~~~~~python.new
class SpySubscriber:
    def __init__(self, bus: EventBus):
        self.events = []
        bus.subscribe(Event, self.collect)
~~~~~

### 下一步建议

`EventBus` 的重构工作已经圆满结束。现在系统的运行时事件流和 UI 消息流已经在命名层面完全隔离。

我建议的下一步是：
1.  **全面测试**: 运行 `pytest` 验证所有包的集成测试，确保没有任何遗漏的导入错误。
2.  **重命名 UI 总线**: 既然 `EventBus` 已经就绪，我们可以开始下一阶段任务：将 `cascade-common` 中的 `MessageBus` 重命名为 `FeedbackBus` 或 `Notifier`，以彻底完善总线系统的语义化设计。如果你准备好了，请指示我开始。

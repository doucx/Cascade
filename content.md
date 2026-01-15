## 我们将更新 `cascade-sdk` 的导出路径，使其直接从 `cascade-bus` 包中获取 `EventBus`、`FeedbackBus` 和 `Event`。同时，我们将更新 `cascade-sdk` 的依赖配置，确保其包含新创建的 `cascade-bus`。

## 标签
#intent/refine #flow/ready #priority/high
#comp/sdk #comp/bus #scope/api
#ai/instruct
#task/domain/infrastructure #task/object/cascade-bus #task/action/sdk-integration #task/state/continue

---

### Script

#### Acts 1: 更新 `cascade-sdk` 的导出映射

我们将修改 `sdk.py` 中的 `_IMPORT_MAP` 和 `TYPE_CHECKING` 块。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
    "EventBus": ("cascade.runtime.services.observability.bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.services.observability.events", "Event"),
    "DependencyMissingError": (
~~~~~
~~~~~python.new
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
    "EventBus": ("cascade.bus.core", "EventBus"),
    "FeedbackBus": ("cascade.bus.feedback", "FeedbackBus"),
    "Event": ("cascade.bus.events", "Event"),
    "DependencyMissingError": (
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
if TYPE_CHECKING:
    from cascade.spec.dsl.task import task
    from cascade.spec.dsl.fluent import LazyResult
    from cascade.spec.dsl.routing import Router
    from cascade.spec.dsl.jump import Jump
    from cascade.spec.dsl.resources import resource, inject
    from cascade.spec.dsl.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.bus.core import EventBus
    from cascade.bus.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline
~~~~~
~~~~~python.new
if TYPE_CHECKING:
    from cascade.spec.dsl.task import task
    from cascade.spec.dsl.fluent import LazyResult
    from cascade.spec.dsl.routing import Router
    from cascade.spec.dsl.jump import Jump
    from cascade.spec.dsl.resources import resource, inject
    from cascade.spec.dsl.constraint import with_constraints
    from cascade.common.context import get_current_context

    from cascade.control_flow import select_jump, bind

    from cascade.runtime.host.instance import Engine
    from cascade.bus.core import EventBus
    from cascade.bus.feedback import FeedbackBus
    from cascade.bus.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline
~~~~~

#### Acts 2: 更新 `cascade-sdk` 的依赖配置

我们将 `cascade-bus` 添加到 `cascade-sdk` 的 `pyproject.toml` 中。

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml.old
dependencies = [
  "cascade-spec",
  "cascade-runtime",
  "cascade-common",
  "cascade-application",
  "cascade-library"
]
~~~~~
~~~~~toml.new
dependencies = [
  "cascade-spec",
  "cascade-runtime",
  "cascade-common",
  "cascade-application",
  "cascade-library",
  "cascade-bus"
]
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/pyproject.toml
~~~~~
~~~~~toml.old
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-common = { workspace = true }
cascade-application = { workspace = true }
cascade-graph = { workspace = true }
~~~~~
~~~~~toml.new
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-runtime = { workspace = true }
cascade-common = { workspace = true }
cascade-application = { workspace = true }
cascade-graph = { workspace = true }
cascade-bus = { workspace = true }
~~~~~

### 下一步建议

`cascade-sdk` 的导出路径已经完成切换。现在，SDK 作为一个门面（Facade），其背后的 Bus 逻辑已经完全指向了 `cascade-bus`。

目前的状态是：
- 物理文件已拆分并安置。
- `sdk` 导出路径已更新。
- 但其他包（如 `runtime` 内部）可能还有旧的 import 语句需要清理。

你可以执行你的 **Import 清理脚本** 来完成最后的逻辑闭环。清理完成后，整个 Cascade 项目将完全摆脱对旧位置 Bus 的依赖。

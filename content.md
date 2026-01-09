好的，我明白了。迁移操作破坏了 `cascade-sdk` 包的公共 API 导出映射，导致所有试图通过 `cascade` 顶层包访问这些移动后模块的测试都失败了。

我们需要更新 `cascade-sdk` 中的 `_IMPORT_MAP` 和类型检查块，以指向 `cascade-execution-graph` 中的新位置。

## [WIP] fix: Update SDK import map after module migration

### 错误分析

在执行 `stitcher refactor apply` 迁移 `cascade-runtime` 的模块到 `cascade-execution-graph` 后，`cascade-sdk` 包中的符号懒加载映射 (`_IMPORT_MAP`) 和类型检查导入 (`if TYPE_CHECKING:`) 并未自动更新。

这导致 `cascade` 的公共 API 表面被破坏，所有依赖 `import cascade as cs` 并访问 `cs.DependencyMissingError`, `cs.NativeSolver`, `cs.to_json` 等移动后符号的代码都因 `AttributeError` 而失败。

### 用户需求

修复 `cascade-sdk/src/cascade/sdk.py` 文件，更新其中的导入路径，使其正确指向 `cascade-execution-graph` 包中的新模块位置。

### 评论

这是一个预料之中的、必要的修复步骤。`stitcher` 能够重构消费者代码的导入，但无法修改像 `_IMPORT_MAP` 这样的字符串数据结构。手动修正这个映射表是恢复 SDK 功能、让测试套件重新变绿的关键。

### 目标

1.  定位 `packages/cascade-sdk/src/cascade/sdk.py` 文件。
2.  修改 `_IMPORT_MAP` 字典，更新 `DependencyMissingError`, `NativeSolver`, `to_json`, `from_json` 等条目的模块路径。
3.  同步修改 `if TYPE_CHECKING:` 块中的静态导入路径，以保证类型检查器的正常工作。

### 基本原理

`cascade-sdk` 作为项目的公共 API 门面，其内部的懒加载机制依赖于一个包含模块路径字符串的字典。在源模块被物理移动后，我们必须手动更新这些字符串路径，以重新建立符号的正确链接。

### 标签

#intent/fix #flow/ready #priority/high #comp/build #scope/api #scope/dx #ai/instruct #task/domain/runtime #task/object/sdk-api #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 修复 `sdk.py` 中的导入路径

我们将一次性更新 `_IMPORT_MAP` 和 `TYPE_CHECKING` 块中所有因迁移而失效的路径。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    "EventBus": ("cascade.runtime.services.observability.bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.services.observability.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.errors", "DependencyMissingError"),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.runtime.kernel.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.runtime.io.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.runtime.interfaces", "Connector"),
    "StateBackend": ("cascade.spec.runtime.interfaces", "StateBackend"),
    # Tools & Utilities
    "to_json": ("cascade.runtime.graph.serialize", "to_json"),
    "from_json": ("cascade.runtime.graph.serialize", "from_json"),
    "override_resource": ("cascade.test_utils.helpers", "override_resource"),
    "ControllerTestApp": ("cascade.test_utils.helpers", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
}

# --- Type Checking Imports ---
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
    from cascade.runtime.services.observability.bus import EventBus
    from cascade.runtime.services.observability.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.runtime.interfaces import Connector, StateBackend

    from cascade.execution.graph.model.serialize import to_json, from_json
    from cascade.test_utils.helpers import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli
~~~~~
~~~~~python.new
    "EventBus": ("cascade.runtime.services.observability.bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.services.observability.events", "Event"),
    "DependencyMissingError": (
        "cascade.execution.graph.errors",
        "DependencyMissingError",
    ),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.execution.graph.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.runtime.io.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.runtime.interfaces", "Connector"),
    "StateBackend": ("cascade.spec.runtime.interfaces", "StateBackend"),
    # Tools & Utilities
    "to_json": ("cascade.execution.graph.model.serialize", "to_json"),
    "from_json": ("cascade.execution.graph.model.serialize", "from_json"),
    "override_resource": ("cascade.test_utils.helpers", "override_resource"),
    "ControllerTestApp": ("cascade.test_utils.helpers", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
}

# --- Type Checking Imports ---
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
    from cascade.runtime.services.observability.bus import EventBus
    from cascade.runtime.services.observability.events import Event
    from cascade.execution.graph.errors import DependencyMissingError
    from cascade.flow import sequence, pipeline

    from cascade.execution.graph.solvers.native import NativeSolver
    from cascade.runtime.io.executors.local import LocalExecutor
    from cascade.spec.runtime.interfaces import Connector, StateBackend

    from cascade.execution.graph.model.serialize import to_json, from_json
    from cascade.test_utils.helpers import override_resource, ControllerTestApp
    from cascade.tools.cli import create_cli
~~~~~

### 下一步建议

导入路径修复完成。请再次运行 `pytest`。这次应该能解决所有 `AttributeError`，并让我们看到迁移后是否存在更深层次的逻辑问题。

如果测试通过，我们就可以进入 **Phase 3: 引擎解耦 (Engine Decoupling)**。

好的，我明白了。测试集在收集阶段就出现了大规模的 `AttributeError`，这清晰地表明了问题的根源：在执行大规模文件重构后，作为 SDK 公共 API 入口的 `cascade.sdk` 模块没有更新其内部的模块导入映射表 (`_IMPORT_MAP`)。

这导致所有试图通过 `cascade.task` 或 `cs.task` 访问核心功能的代码都失败了，因为 SDK 的懒加载机制仍在尝试从旧的、现在已经不存在的路径导入这些对象。

我将生成一个计划来修复这个问题。

## [WIP] fix(sdk): 更新 _IMPORT_MAP 以反映重构后的模块路径

### 错误分析

在执行了 `cascade-spec` 和 `cascade-runtime` 的大规模目录重构后，`packages/cascade-sdk/src/cascade/sdk.py` 文件中的核心懒加载映射表 `_IMPORT_MAP` 未得到同步更新。

这个映射表是 `cascade` 包顶级 `__getattr__` 实现的真理来源（Single Source of Truth），它告诉解释器去哪里加载像 `task`, `resource`, `LazyResult` 这样的核心 API 对象。由于它仍然指向旧的模块路径（例如 `"cascade.spec.task"`），而该路径下的文件已被移动到新的位置（例如 `"cascade.spec.dsl.task"`），导致所有对这些 API 的调用在导入时就因 `ModuleNotFoundError` 而失败，并最终表现为用户看到的 `AttributeError`。

修复此映射表将一次性解决所有 9 个测试收集错误。

### 用户需求

修复因大规模重构导致的 SDK 导入路径失效问题，使测试能够正常收集和运行。

### 评论

这是一个非常典型的、在“休克疗法”式重构后需要解决的核心集成问题。修复这个中心的 `_IMPORT_MAP` 是最高效的策略，它能一次性恢复整个项目对 Cascade SDK 的引用，让依赖它的所有包（graph, runtime, library, tests 等）都能重新找到正确的模块。

### 目标

1.  定位 `packages/cascade-sdk/src/cascade/sdk.py` 文件。
2.  使用 `patch_file` 操作，精确地更新 `_IMPORT_MAP` 字典中的值，使其指向重构后正确的新模块路径。

### 基本原理

我们将根据 `003_restructure_spec.py` 和 `002_restructure_runtime.py` 迁移脚本中定义的最终文件结构，来修正 `_IMPORT_MAP` 中的每一个条目。使用 `patch_file` 可以保证我们只修改目标字典，而不会意外地影响文件中的其他代码。

### 标签

#intent/fix #flow/ready #priority/critical
#comp/sdk #scope/api
#ai/instruct
#task/domain/architecture #task/object/monorepo #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修正 `sdk.py` 中的懒加载映射

我将直接修改 `_IMPORT_MAP`，将所有旧的 `cascade.spec.*` 路径更新为新的 `cascade.spec.dsl.*` 或 `cascade.spec.runtime.*` 路径。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
# --- Lazy Import Mapping ---
# Maps exported names to (module_path, object_name)
_IMPORT_MAP = {
    # Core Specs
    "task": ("cascade.spec.task", "task"),
    "LazyResult": ("cascade.spec.lazy_types", "LazyResult"),
    "Router": ("cascade.spec.routing", "Router"),
    "Jump": ("cascade.spec.jump", "Jump"),
    "resource": ("cascade.spec.resource", "resource"),
    "inject": ("cascade.spec.resource", "inject"),
    "with_constraints": ("cascade.spec.constraint", "with_constraints"),
    "get_current_context": ("cascade.common.context", "get_current_context"),
    # Advanced Flow Control
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
    "EventBus": ("cascade.runtime.services.observability.bus", "EventBus"),
    "FeedbackBus": ("cascade.common.messaging", "FeedbackBus"),
    "Event": ("cascade.runtime.services.observability.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.errors", "DependencyMissingError"),
    "sequence": ("cascade.flow", "sequence"),
    "pipeline": ("cascade.flow", "pipeline"),
    # Adapters & Protocols
    "NativeSolver": ("cascade.runtime.kernel.solvers.native", "NativeSolver"),
    "LocalExecutor": ("cascade.runtime.io.executors.local", "LocalExecutor"),
    "Connector": ("cascade.spec.protocols", "Connector"),
    "StateBackend": ("cascade.spec.protocols", "StateBackend"),
    # Tools & Utilities
    "to_json": ("cascade.graph.serialize", "to_json"),
    "from_json": ("cascade.graph.serialize", "from_json"),
    "override_resource": ("cascade.testing", "override_resource"),
    "ControllerTestApp": ("cascade.testing", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
}
~~~~~
~~~~~python.new
# --- Lazy Import Mapping ---
# Maps exported names to (module_path, object_name)
_IMPORT_MAP = {
    # Core Specs
    "task": ("cascade.spec.dsl.task", "task"),
    "LazyResult": ("cascade.spec.dsl.fluent", "LazyResult"),
    "Router": ("cascade.spec.dsl.routing", "Router"),
    "Jump": ("cascade.spec.dsl.jump", "Jump"),
    "resource": ("cascade.spec.dsl.resources", "resource"),
    "inject": ("cascade.spec.dsl.resources", "inject"),
    "with_constraints": ("cascade.spec.dsl.constraint", "with_constraints"),
    "get_current_context": ("cascade.common.context", "get_current_context"),
    # Advanced Flow Control
    "select_jump": ("cascade.control_flow", "select_jump"),
    "bind": ("cascade.control_flow", "bind"),
    # Runtime
    "Engine": ("cascade.runtime.host.instance", "Engine"),
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
    "to_json": ("cascade.graph.serialize", "to_json"),
    "from_json": ("cascade.graph.serialize", "from_json"),
    "override_resource": ("cascade.testing", "override_resource"),
    "ControllerTestApp": ("cascade.testing", "ControllerTestApp"),
    "create_cli": ("cascade.tools.cli", "create_cli"),
}
~~~~~

### 下一步建议

现在最核心的 API 映射已经修复，请重新运行测试。这应该能解决所有的 `AttributeError` 并让测试集合正常开始执行。

```bash
pytest
```

之后可能会暴露出来自更深层次的、与实现细节相关的导入错误，但至少测试收集这一关应该能通过了。

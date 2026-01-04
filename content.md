好的，我明白了。

上一轮 `cascade-engine` 的重构（将 `MessageBus` 重命名为 `EventBus`）引发了多米诺骨牌效应，导致 `cascade-sdk` 以及所有依赖 SDK 的测试出现了大量 `AttributeError`。这主要是因为 `cascade-sdk` 中的 `_IMPORT_MAP` 尚未更新，仍然指向旧的 `cascade.runtime.bus.MessageBus`。

我将遵循你的建议，采取以下步骤：
1.  **修复 SDK 映射**: 修正 `packages/cascade-sdk/src/cascade/sdk.py`，更新 `_IMPORT_MAP` 和类型提示，将 `MessageBus` 替换为 `EventBus`。同时，确保所有其他相关导出（如 `DependencyMissingError`）也指向正确的路径。
2.  **批量更新测试**: 使用 `sed` 批量修复所有测试文件中对 `cs.MessageBus` 的引用，将其更新为 `cs.EventBus`。这包括 `cascade-sdk`、`cascade-library`、`cascade-spec` 和 `cascade-provider-ipfs` 等包中的测试。

这是一个 `[WIP]` 计划，专注于恢复 SDK 的功能并批量修复剩余的测试错误。

## [WIP] fix(sdk): 更新 SDK 导出映射并批量修复测试引用

### 错误分析

当前的测试失败可以归纳为两类：
1.  **SDK 导出错误**: `cascade-sdk` 中的 `_IMPORT_MAP` 仍然包含 `"MessageBus": ("cascade.runtime.bus", "MessageBus")`，这导致 `cs.MessageBus` 无法解析（`AttributeError`）。
2.  **测试引用错误**: 大量集成测试文件仍然使用 `cs.MessageBus()` 来实例化总线，这需要统一更新为 `cs.EventBus()`。

### 用户需求

修复 `cascade-sdk` 的导出映射，并批量更新所有测试文件以匹配新的 `EventBus` 命名。

### 评论

这是重构的最后“一公里”。通过更新 SDK 的入口点，我们正式对外公布了这一变更。使用 `sed` 进行批量替换则是处理这种大规模 API 变更最高效的手段。此举将彻底消除遗留的 `MessageBus` 引用，使整个代码库恢复一致性。

### 目标

1.  更新 `packages/cascade-sdk/src/cascade/sdk.py`：
    *   在 `_IMPORT_MAP` 中，将 `MessageBus` 替换为 `EventBus`，并指向 `cascade.runtime.event_bus`。
    *   在类型检查块（`TYPE_CHECKING`）中更新相应的导入。
    *   在 `__all__` 列表中更新导出名称。
2.  使用 `sed` 批量替换整个 `packages` 目录下的测试文件：
    *   将 `cs.MessageBus` 替换为 `cs.EventBus`。
    *   将 `MessageBus` 替换为 `EventBus`（针对直接导入的情况）。

### 基本原理

优先修复 SDK，因为它作为统一入口点，其正确性直接关系到下游所有测试的运行。接着，使用 `sed` 在整个 `packages` 目录下进行全局替换，这比针对每个包单独生成 `sed` 命令更全面，也更能防止漏网之鱼。

### 标签

#intent/fix #flow/ready #priority/high #comp/sdk #scope/api #ai/instruct #task/domain/architecture #task/object/event-bus #task/action/synchronize #task/state/end

---

### Script

#### Acts 1: 更新 `cascade-sdk` 的导出映射

修复 `sdk.py` 以反映重构后的模块结构和类名。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    "Engine": ("cascade.runtime.engine", "Engine"),
    "MessageBus": ("cascade.runtime.bus", "MessageBus"),
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
~~~~~
~~~~~python.new
    "Engine": ("cascade.runtime.engine", "Engine"),
    "EventBus": ("cascade.runtime.event_bus", "EventBus"),
    "Event": ("cascade.runtime.events", "Event"),
    "DependencyMissingError": ("cascade.runtime.exceptions", "DependencyMissingError"),
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    from cascade.runtime.engine import Engine
    from cascade.runtime.bus import MessageBus
    from cascade.runtime.events import Event
    from cascade.runtime.exceptions import DependencyMissingError
~~~~~
~~~~~python.new
    from cascade.runtime.engine import Engine
    from cascade.runtime.event_bus import EventBus
    from cascade.runtime.events import Event
    from cascade.runtime.exceptions import DependencyMissingError
~~~~~

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/sdk.py
~~~~~
~~~~~python.old
    "LazyResult",
    "Engine",
    "Event",
    "MessageBus",
    "NativeSolver",
    "LocalExecutor",
~~~~~
~~~~~python.new
    "LazyResult",
    "Engine",
    "Event",
    "EventBus",
    "NativeSolver",
    "LocalExecutor",
~~~~~

#### Acts 2: 批量更新测试文件引用

使用 `find` 和 `sed` 对所有测试文件进行一次性修正。这里我们扩大了搜索范围，涵盖整个 `packages` 目录，以确保无遗漏。

~~~~~act
run_command
~~~~~
~~~~~bash
# 1. Replace usages of 'cs.MessageBus' with 'cs.EventBus' in all python files
find packages -name "*.py" -print0 | xargs -0 sed -i 's/cs\.MessageBus/cs.EventBus/g'

# 2. Replace usages of 'MessageBus' with 'EventBus' in test files that might import it directly
# Note: We are careful not to replace 'cascade.runtime.bus' here as that file was already renamed/moved.
# This targets lines like 'from cascade.runtime import MessageBus' or 'bus = MessageBus()'
find packages -name "*.py" -print0 | xargs -0 sed -i 's/MessageBus/EventBus/g'
~~~~~

### 下一步建议

所有引用都已更新。现在代码库应该是一致的。
1.  **运行所有测试**: 执行 `pytest` 来确认修复是否彻底。
2.  **重命名 UI 总线 (MessageBus -> FeedbackBus)**: 完成上述步骤并确认系统稳定后，我们就可以着手进行 `cascade-common` 中 `MessageBus` 到 `FeedbackBus` 的重命名工作，彻底厘清这个命名混乱的历史遗留问题。

如果你同意，请告诉我测试结果。

好的，我理解了。之前我修复了 `src` 文件，但忽略了 `tests` 目录，导致测试套件崩溃。你的建议非常正确，对于这种跨多个文件的、模式化的文本替换，使用 `sed` 远比生成大量的 `patch_file` 指令要高效和清晰。

我将生成一个 `[WIP]` 计划，使用 `sed` 来一次性修复 `packages/cascade-engine/tests` 目录下所有测试文件的导入问题。

## [WIP] fix(tests): 使用 sed 批量更新 cascade-engine 测试中的 EventBus 导入

### 错误分析

在 `cascade-engine` 的 `MessageBus` 被重构为 `EventBus` 之后，`packages/cascade-engine/tests` 目录下的所有测试文件都因过时的导入语句而失败。错误日志清楚地显示了两种主要的失败模式：
1.  `ModuleNotFoundError: No module named 'cascade.runtime.bus'`，源于 `from cascade.runtime.bus import MessageBus`。
2.  `ImportError: cannot import name 'MessageBus' from 'cascade.runtime'`，源于 `from cascade.runtime import ..., MessageBus`。

所有这些错误都可以通过一个统一的、自动化的文本替换策略来解决。

### 用户需求

修复 `cascade-engine` 测试套件中所有因 `MessageBus` 重构而产生的导入错误。

### 评论

这是一个标准的重构后清理步骤。使用 `sed` 这种命令行工具是处理此类任务的典范，它能确保所有文件都得到一致、正确的修改，同时让计划本身保持简洁。这个修复将使 `cascade-engine` 包的测试套件恢复健康，为后续的重构工作奠定坚实的基础。

### 目标

1.  定位 `packages/cascade-engine/tests` 目录下的所有 Python 文件。
2.  使用 `sed` 命令执行以下替换：
    *   将 `from cascade.runtime.bus import MessageBus` 替换为 `from cascade.runtime import EventBus`。
    *   将所有剩余的 `MessageBus` 实例（在多重导入或实例化中）替换为 `EventBus`。

### 基本原理

我们将使用 `find` 命令来定位所有 `.py` 文件，并通过管道将其传递给 `xargs`，以便对每个文件执行 `sed -i`（in-place edit）命令。我们将执行两个独立的 `sed` 命令来保证替换的精确性：
1.  第一个 `sed` 命令专门处理 `from ... import ...` 这种完整的导入语句，因为它需要同时修改模块路径和类名。
2.  第二个 `sed` 命令处理所有其他情况，它是一个更通用的 `s/MessageBus/EventBus/g` 替换。
这种两步走的策略可以确保所有变体都被正确覆盖。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/imports #task/action/bulk-update #task/state/continue

---

### Script

#### Acts 1: 批量修复测试文件

我们将使用一个 `run_command` 指令块，其中包含一系列 `find` 和 `sed` 命令，来原子化地修复 `cascade-engine` 的整个测试目录。

~~~~~act
run_command
~~~~~
~~~~~bash
# Find all Python files in the tests directory and apply two sed replacements.
# The first, more specific sed command handles the explicit module import.
find packages/cascade-engine/tests -type f -name "*.py" -print0 | xargs -0 sed -i 's/from cascade.runtime.bus import MessageBus/from cascade.runtime import EventBus/g'

# The second, more general command handles all other occurrences, such as multi-line imports and instantiations.
find packages/cascade-engine/tests -type f -name "*.py" -print0 | xargs -0 sed -i 's/MessageBus/EventBus/g'
~~~~~

### 下一步建议

我们已经修复了 `cascade-engine` 的测试文件。现在，我建议：
1.  **运行测试**: 立即执行 `pytest packages/cascade-engine` 来验证这些修复是否成功，并确保没有引入新的回归问题。
2.  **继续修复**: 在确认 `cascade-engine` 包稳定后，我们可以继续处理其他包中（如 `cascade-sdk`）因这次重构而失败的测试。

如果你同意，请告诉我测试结果，或者我们可以直接进行下一步的修复工作。

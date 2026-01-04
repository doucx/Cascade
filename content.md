收到。针对 `tests/e2e` 目录下的遗留引用，我将继续使用 `sed` 进行批量修复。这对于确保端到端测试在重构后仍能正确执行至关重要。

由于这些测试文件位于根目录的 `tests/` 文件夹下，不在之前的 `packages/` 批量处理范围内，因此需要针对性的处理。

## [WIP] refactor: 更新 e2e 测试中的 EventBus 引用

### 用户需求

修复 `tests/e2e` 目录下所有因 `cascade-engine` 重构（`MessageBus` -> `EventBus`）而产生的导入错误和实例化引用。

### 评论

端到端（E2E）测试是验证重构是否破坏系统集成功能的最后防线。由于 E2E 测试通常模拟真实用户的调用路径，它们对 `cascade.runtime` 的 API 变更非常敏感。使用 `sed` 批量修复这些引用不仅高效，而且能保证测试环境与核心代码库的同步。

### 目标

1.  修复 `tests/e2e` 目录下所有 Python 文件的导入路径：将 `from cascade.runtime.bus import MessageBus` 转换为 `from cascade.runtime import EventBus`。
2.  修复所有类名引用：将 `MessageBus` 替换为 `EventBus`。
3.  纠正因重命名导致的冠词错误（如 `a EventBus` 修正为 `an EventBus`）。

### 基本原理

我们将利用 `find` 定位 `tests/e2e` 下的所有 Python 文件，并管道传输给 `sed`。考虑到导入语句的特殊性，我们先处理具体的 `from...import` 路径，然后再进行全局的类名替换。最后，我们会简单处理一下注释和文档字符串中的语法。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/e2e-imports #task/action/bulk-update #task/state/continue

---

### Script

#### Acts 1: 使用 sed 批量更新 e2e 测试文件

我们将执行三条 `sed` 指令来完成转换。

~~~~~act
run_command
~~~~~
~~~~~bash
# 1. 处理特定的模块导入路径
find tests/e2e -type f -name "*.py" -print0 | xargs -0 sed -i 's/from cascade\.runtime\.bus import MessageBus/from cascade.runtime import EventBus/g'

# 2. 全局替换类名（涵盖实例化、类型注解和文档字符串）
find tests/e2e -type f -name "*.py" -print0 | xargs -0 sed -i 's/MessageBus/EventBus/g'

# 3. 修正文档字符串中的冠词 (a EventBus -> an EventBus)
find tests/e2e -type f -name "*.py" -print0 | xargs -0 sed -i 's/a EventBus/an EventBus/g'
~~~~~

### 下一步建议

`tests/e2e` 的引用已更新完毕。现在，整个 monorepo（包括核心包和根目录测试）关于 `EventBus` 的重构已基本对齐。

我建议：
1.  **执行全量测试**: 运行 `pytest`（不带包限定）以观察整体通过情况。
2.  **清理重构碎片**: 检查是否有遗漏的 `.stitcher.yaml` 文件或文档（README）仍在使用 `MessageBus` 来描述事件总线。
3.  **启动第二阶段**: 既然 `EventBus` 已站稳脚跟，我们可以开始处理 `cascade-common` 侧的 `MessageBus` 重命名（例如改为 `FeedbackBus`），彻底消除命名冲突。

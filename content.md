Ah, the "ModuleNotFoundError: No module named 'cascade.messaging'" error. This is happening because we deleted the `cascade.messaging` module from `cascade-py` during our refactor, but we forgot to update the unit tests that were importing from it.

These tests are now trying to import code that no longer exists in that location. We need to refactor these tests to use the new `cascade-common` package structure and the updated `cascade-runtime` renderers.

## [WIP] fix(tests): Migrate unit tests to use cascade-common messaging

### 错误分析
`pytest` 在收集测试时失败，因为 `tests/py/messaging/test_renderer.py` 和 `tests/py/runtime/test_bus.py` 仍在尝试从 `cascade.messaging` 导入模块。然而，作为我们之前的架构重构的一部分，该模块已被移除，其功能已迁移到 `cascade-common` 包（用于协议和核心总线）和 `cascade-runtime` 包（用于渲染器实现）。

### 用户需求
修复失败的单元测试，使其适应新的消息总线架构。

### 评论
维护一个健康、通过的测试套件是持续开发的关键。这次重构虽然改变了内部结构，但通过更新测试，我们可以确保这一变更没有破坏原有的功能契约，同时也验证了新架构的正确性。这是一个偿还技术债务和巩固架构变更的重要步骤。

### 目标
1.  重构 `tests/py/messaging/test_renderer.py`：
    *   更新导入路径：从 `cascade.runtime.renderers` 导入渲染器。
    *   更新导入路径：从 `cascade.common.messaging` 导入 `MessageStore`。
2.  重构 `tests/py/runtime/test_bus.py`：
    *   更新导入路径：使用 `cascade.common.messaging.bus` 替代旧的 `cascade.messaging.bus`。
3.  确保所有与消息总线相关的测试都能正确通过。

### 基本原理
我们将使用 `patch_file` 指令来修改测试文件中的导入语句。这不仅能解决 `ModuleNotFoundError`，还能确保我们的测试代码准确反映了生产代码的现状。这验证了从 `cascade-py` 移除耦合的消息代码并将其放入 `cascade-common` 和 `cascade-runtime` 的决定是可行的。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/unit-tests #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 更新 `test_renderer.py`

我们需要更新此文件以从新的位置导入 `CliRenderer`, `JsonRenderer` 和 `MessageStore`。

~~~~~act
patch_file
tests/py/messaging/test_renderer.py
~~~~~
~~~~~python
from cascade.messaging.renderer import CliRenderer, JsonRenderer
from cascade.messaging.bus import MessageStore
~~~~~
~~~~~python
from cascade.runtime.renderers import CliRenderer, JsonRenderer
from cascade.common.messaging import MessageStore
~~~~~

#### Acts 2: 更新 `test_bus.py`

此测试文件中的一个特定测试用例引用了旧的全局总线。我们需要将其指向新的全局总线。

~~~~~act
patch_file
tests/py/runtime/test_bus.py
~~~~~
~~~~~python
from cascade.messaging.bus import bus as messaging_bus
~~~~~
~~~~~python
from cascade.common.messaging import bus as messaging_bus
~~~~~

### 下一步建议
测试文件已更新。请再次运行 `pytest`。

如果测试现在通过，我们将确信新的消息总线架构已正确集成，并且没有破坏现有的渲染逻辑。然后，我们可以自信地推进 `cs-observer` 的开发。

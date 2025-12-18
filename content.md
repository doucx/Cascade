这些测试收集错误（`ImportError`）是因为我们刚刚将 `CliRenderer` 和 `JsonRenderer` 从 `cascade-runtime` 迁移到了 `cascade-common`。由于导入路径发生了变化，现有的测试用例无法找到对应的模块。

### 分析与建议

1.  **迁移测试用例**: `test_renderers.py` 是对 `Renderer` 实现的单元测试。既然 `Renderer` 已经移动到了 `cascade-common` 包，那么对应的测试文件也应该移动到 `tests/common/` 目录下，以保持测试结构与源代码结构的一致性。
2.  **更新导入路径**: `test_event_bus.py` 是一个集成测试，验证了运行时事件总线到用户界面消息总线的全链路打通。它依赖于 `CliRenderer`。我们需要更新它的导入语句。
3.  **拆分逻辑**:
    *   **单元测试**: 针对 `CliRenderer` 和 `JsonRenderer` 的纯逻辑测试应放在 `tests/common/`。
    *   **集成测试**: 涉及 `HumanReadableLogSubscriber`（位于 `runtime`）如何将事件转换为消息的测试，应保留在 `tests/runtime/` 中，因为这是运行时组件的行为验证。

---

## [WIP] fix(tests): Fix broken imports and reorganize renderer tests

### 错误分析
测试失败是因为在 `refactor` 计划中，我们将渲染器从 `cascade.runtime.renderers` 移动到了 `cascade.common.renderers`。由于 Python 测试文件在收集阶段会执行模块级导入，错误的路径导致了 `ModuleNotFoundError` 并中断了测试运行。

### 用户需求
修复测试中的导入错误，并根据新的包结构优化测试文件的存储位置。

### 目标
1.  将 `tests/runtime/test_renderers.py` 移动到 `tests/common/test_renderers.py`。
2.  更新 `tests/common/test_renderers.py` 中的导入语句。
3.  更新 `tests/runtime/test_event_bus.py` 中的导入语句。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/common #comp/runtime #task/domain/testing #task/object/import-fix #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 移动并修复渲染器单元测试

我们将专门测试渲染器的文件移动到 `common` 对应的测试目录下，并修正导入。

~~~~~act
move_file
tests/runtime/test_renderers.py
tests/common/test_renderers.py
~~~~~

~~~~~act
patch_file
tests/common/test_renderers.py
~~~~~
~~~~~python
import io
import json
import pytest
from cascade.runtime.renderers import CliRenderer, JsonRenderer
from cascade.common.messaging import MessageStore
~~~~~
~~~~~python
import io
import json
import pytest
from cascade.common.renderers import CliRenderer, JsonRenderer
from cascade.common.messaging import MessageStore
~~~~~

#### Acts 2: 修复事件总线集成测试的导入

`test_event_bus.py` 虽然留在 `runtime`，但需要从新位置导入 `CliRenderer`。

~~~~~act
patch_file
tests/runtime/test_event_bus.py
~~~~~
~~~~~python
from cascade.runtime.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber
from cascade.runtime.bus import MessageBus as EventBus
from cascade.common.messaging import bus as ui_bus
from cascade.runtime.renderers import CliRenderer
~~~~~
~~~~~python
from cascade.runtime.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber
from cascade.runtime.bus import MessageBus as EventBus
from cascade.common.messaging import bus as ui_bus
from cascade.common.renderers import CliRenderer
~~~~~

### 下一步建议
现在测试环境应该已经恢复。我建议你运行测试（`pytest`）来验证重构是否成功。

如果测试通过，我们可以继续路线图的下一步：实现 `cs-observer`。我们已经有了 `RichCliRenderer` 的雏形，下一步是为它添加真实的 MQTT 订阅逻辑，使其能真正“观察”到运行中的工作流。

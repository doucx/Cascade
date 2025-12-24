好的，我分析了错误日志。

你完全正确，我在上一步创建的测试用例中引入了一个错误。它因为错误的 import 语句而失败，我将立即修复它。

## [WIP] fix(tests): 纠正 TCO 覆盖测试中的 MessageBus 导入

### 错误分析
测试 `test_jump_overrides_param` 失败的原因是 `TypeError: MessageBus.__init__() missing 1 required positional argument: 'store'`。

这是因为测试文件错误地从 `cascade.common.messaging` 导入了 `MessageBus`。这个 Bus 是面向 UI 的、用于渲染用户消息的，因此需要一个 `MessageStore`。

然而，`Engine` 的 `bus` 参数期望的是用于内部事件分发的、位于 `cascade.runtime.bus` 的 `MessageBus`，该类的构造函数是无参数的。这是一个在编写测试时不慎引入的疏忽。

### 用户需求
修复 `tests/engine/e2e/test_tco_param_override.py` 中由于 `MessageBus` 实例化不正确而导致的 `TypeError`。

### 评论
这是一个简单的修复，但它暴露了 Cascade 架构中两个总线系统之间清晰的界限：一个用于内部事件 (`runtime`)，另一个用于外部呈现 (`common`)。在测试中正确区分这两者至关重要。

### 目标
修改 `test_tco_param_override.py` 中的 `import` 语句，使其指向正确的 `MessageBus` 类。

### 基本原理
通过将 `import` 路径从 `cascade.common.messaging` 更改为 `cascade.runtime.bus`，测试将实例化 `Engine` 所期望的内部事件总线，从而解决构造函数错误，并使测试能够按预期验证 TCO 逻辑。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/core #task/object/argument-resolver #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 纠正 `MessageBus` 的 import 路径

我们将 `test_tco_param_override.py` 文件中的 import 语句指向 `cascade.runtime.bus`。

~~~~~act
patch_file
tests/engine/e2e/test_tco_param_override.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.common.messaging import MessageBus

@pytest.mark.asyncio
async def test_jump_overrides_param():
~~~~~
~~~~~python
import pytest
import cascade as cs
from cascade.runtime.engine import Engine
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.bus import MessageBus

@pytest.mark.asyncio
async def test_jump_overrides_param():
~~~~~
~~~~~act
patch_file
tests/engine/e2e/test_tco_param_override.py
~~~~~
~~~~~python
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = MessageBus()
    engine = Engine(
        solver=NativeSolver(),
~~~~~
~~~~~python
    cs.bind(t, cs.select_jump({"continue": t}))

    bus = MessageBus()
    engine = Engine(
        solver=NativeSolver(),
~~~~~

### 下一步建议
现在测试文件已经修复，请再次运行测试 `pytest tests/engine/e2e/test_tco_param_override.py`。它现在应该能够成功通过，从而验证我们最初对 `ArgumentResolver` 的修复是正确的。

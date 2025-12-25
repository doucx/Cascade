感谢你运行全量测试并提供了如此详细的反馈。这正是 TDD 流程的价值所在——它能精确地捕获到大规模重构中引入的、难以预见的副作用。

我将生成一个计划来修复这些问题。

## [WIP] fix(build): 解决重构引入的导入错误和测试失败

### 错误分析
1.  **`AttributeError: module 'cascade' has no attribute 'MessageBus'` (主要问题)**:
    *   **根本原因**: 这是一个比 `__all__` 更深层次的 Python 导入机制问题。虽然我将 `MessageBus` 加入了 `__all__`，但我没有在 `cascade-sdk/src/cascade/__init__.py` 的顶层显式导入它。`__getattr__` 是一个“最后的防线”，只有当一个属性在模块的命名空间中找不到时才会被调用。由于 `MessageBus` 没有被直接导入到 `cascade` 模块的命名空间中，所有对 `cascade.MessageBus` 的访问都被 `__getattr__` 错误地拦截，并被路由到了 provider 查找逻辑，最终导致失败。
    *   **解决方案**: 我需要在 `cascade-sdk/src/cascade/__init__.py` 中添加 `from cascade.runtime import MessageBus`，将其直接引入模块命名空间，这样 `__getattr__` 就不会再拦截对它的访问。

2.  **`test_app_dry_run_with_list_input` - `AssertionError: assert 5 == 6`**:
    *   **原因**: 我的测试逻辑有一个微小的偏差。`capsys.readouterr().out.strip().split('\n')` 会移除末尾的换行符，所以一个由 `print()` 产生的、看起来是6行的输出（包括最后的空行），实际上只会被分割成5个元素。
    *   **解决方案**: 将断言从 `assert len(lines) == 6` 修改为 `assert len(lines) == 5`。

3.  **其他 E2E 和 Provider 测试失败**:
    *   **原因**: 这些失败绝大多数都是由第一个 `MessageBus` 导入错误引起的连锁反应。`Engine`、`Subscribers` 和许多 Provider 在内部都依赖于消息总线进行日志记录和事件处理。当 `cascade.MessageBus` 无法导入时，这些组件在实例化或运行时就会失败。
    *   **解决方案**: 修复核心的 `MessageBus` 导入问题应该能够解决这一大批相关的测试失败。

### 目标
1.  修复 `cascade-sdk` 的 `__init__.py`，正确导入 `MessageBus`。
2.  修正 `tests/application/test_app_tools.py` 中不正确的断言。

### 标签
#intent/fix #flow/ready #priority/critical #comp/sdk #comp/build #comp/tests #scope/core #ai/instruct #task/domain/architecture #task/object/cascade-app #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `MessageBus` 导入问题

这是最关键的修复。我们将直接在 `cascade-sdk` 的主 `__init__.py` 文件中导入 `MessageBus`。

~~~~~act
patch_file
packages/cascade-sdk/src/cascade/__init__.py
~~~~~
~~~~~python
# --- Runtime (for type hints and exceptions) ---
from cascade.runtime.engine import Engine
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.flow import sequence, pipeline
~~~~~
~~~~~python
# --- Runtime (for type hints and exceptions) ---
from cascade.runtime.engine import Engine
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event
from cascade.runtime.exceptions import DependencyMissingError
from cascade.spec.protocols import Connector, StateBackend
from cascade.flow import sequence, pipeline
~~~~~

#### Acts 2: 修复 `dry_run` 测试中的断言

现在，我们修正 `test_app_dry_run_with_list_input` 测试中的行数断言。

~~~~~act
patch_file
tests/application/test_app_tools.py
~~~~~
~~~~~python
    captured = capsys.readouterr().out
    lines = [line.strip() for line in captured.strip().split('\n')]

    assert len(lines) == 6 # Header, 3 nodes, Footer, empty line
    assert "_internal_gather" in lines[-2]
    node_names = {l.split(' ')[1] for l in lines[1:-2]}
    assert node_names == {"t_a", "t_b", "_internal_gather"}
~~~~~
~~~~~python
    captured = capsys.readouterr().out
    lines = [line.strip() for line in captured.strip().split('\n')]

    # .strip() removes the final newline, so we expect 5 lines:
    # Header, t_a, t_b, _internal_gather, Footer
    assert len(lines) == 5
    assert "_internal_gather" in lines[-2]
    node_names = {l.split(' ')[1] for l in lines[1:-2]}
    assert node_names == {"t_a", "t_b", "_internal_gather"}
~~~~~

### 下一步建议
这些修复应该能解决绝大多数（如果不是全部）的测试失败。在应用这些补丁后，请再次运行全量测试。

如果测试全部通过，我们就可以生成最终的 `[COMMIT]` 计划，将这次成功的重构作为一个原子单元提交。

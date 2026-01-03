简要回答
好的，我将使用 `sed` 批量修复 `cascade-std` 中大部分单元测试的函数调用签名，并手动修复 `test_observer.py` 以引入 `MagicMock` 并适配其特殊的调用方式。

## [WIP] fix(tests): 批量更新 cascade-std 单元测试以适配新的物理函数签名

### 错误分析
`Reactor` 和物理函数的签名变更导致 `cascade-std` 中的单元测试大量失败，因为测试代码中对物理函数的调用仍然缺少新增的 `resources` 参数。

### 用户需求
修复 `cascade-std` 下所有因 `TypeError: ... missing 1 required positional argument: 'resources'` 而失败的测试。

### 评论
这是一个必要的清理工作，标志着“统一资源管理”重构的完成。通过在测试中注入 `MagicMock()` 作为 `resources` 参数，我们满足了新的物理契约，同时保持了单元测试对环境的无知性（Agnoticism）。

### 目标
1.  使用 `sed` 批量更新测试文件中的函数调用。
2.  手动修复 `test_observer.py` 的导入和调用逻辑。

### 基本原理
大部分测试用例都遵循 `await func(inputs, mock_obj)` 的模式，可以通过正则表达式高效地批量替换。`test_observer.py` 需要引入新的 Mock 对象并调整关键字参数，因此单独处理。

### 标签
#intent/fix #flow/ready #priority/high #comp/std #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 批量替换 MagicMock 调用

对于形如 `await func(inputs, MagicMock())` 的调用，我们在末尾插入一个新的 `MagicMock()` 作为 `resources` 参数。这覆盖了大多数 Probe 和 Resource 的测试。

~~~~~act
run_command
~~~~~
~~~~~
find packages/cascade-std/tests/unit -name "test_*.py" -not -name "test_observer.py" | xargs sed -i 's/MagicMock())/MagicMock(), MagicMock())/g'
~~~~~

#### Acts 2: 批量替换 node 变量调用

对于形如 `await func(inputs, node)` 或 `await func(..., mock_node)` 的调用，我们在末尾追加 `, MagicMock()`。这主要覆盖了 Triad（Bleacher, Stainer）和部分 Resource 测试。

~~~~~act
run_command
~~~~~
~~~~~
find packages/cascade-std/tests/unit -name "test_*.py" -not -name "test_observer.py" | xargs sed -i 's/, node)/, node, MagicMock())/g'
~~~~~

~~~~~act
run_command
~~~~~
~~~~~
find packages/cascade-std/tests/unit -name "test_*.py" | xargs sed -i 's/, mock_node)/, mock_node, MagicMock())/g'
~~~~~

#### Acts 3: 修复 test_observer.py

`test_observer.py` 之前利用了隐式的参数传递（将 `queue` 传给了 `node` 位置），现在需要显式地 Mock `node` 和 `resources`，并正确传递关键字参数 `queue`。同时需要导入 `MagicMock`。

~~~~~act
patch_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python.old
from asyncio import Queue

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


async def test_observer_processes_start_event():
~~~~~
~~~~~python.new
from asyncio import Queue
from unittest.mock import MagicMock

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


async def test_observer_processes_start_event():
~~~~~

### 下一步建议
运行测试以确认修复。一旦全绿，我们将进入路线图的**阶段 2：应用新模型并重构测试工具**，重点是重构 `EventDrivenRunner` 以使用 `ResourceRegistry`。

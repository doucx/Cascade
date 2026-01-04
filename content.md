好的，感谢提供 `ExecutionContext` 的定义。我之前的计划中对它的实例化是错误的，忽略了必需的 `run_id`, `state_backend`, 和 `run_stack` 参数。

我将立即生成一个修复计划来纠正这个 `TypeError`。

## [WIP] fix: 纠正 VM E2E 测试中 ExecutionContext 的实例化

### 用户需求

修复 `test_vm_strategy.py` 中因 `ExecutionContext` 初始化参数不匹配而导致的 `TypeError`。

### 错误分析

`cascade.runtime.strategies.base.ExecutionContext` 的构造函数需要 `run_id`, `state_backend`, 和 `run_stack` 三个必需的位置参数。我生成的 E2E 测试代码在创建 `ExecutionContext` 实例时，仅提供了可选的 `active_resources` 参数，导致了 `TypeError`。

### 评论

这是一个简单的疏忽，但它凸显了编写高层级集成测试时准确模拟运行环境的重要性。通过提供必要的 mock 对象来满足 `ExecutionContext` 的契约，我们可以使测试更真实地反映 `VMExecutionStrategy` 的实际运行条件。

### 目标

1.  修改 `packages/cascade-engine/tests/integration/test_vm_strategy.py`。
2.  在测试 `test_vm_strategy_e2e_execution` 中，使用 `MagicMock` 和 `ExitStack` 来正确地实例化 `ExecutionContext`。

### 基本原理

为了解决 `TypeError`，我们必须为 `ExecutionContext` 提供所有必需的参数。在测试环境中，我们不需要一个功能齐全的 `state_backend` 或 `run_stack`，因此使用 `unittest.mock.MagicMock` 和一个空的 `contextlib.ExitStack` 是最合适的做法。

### 标签

#intent/fix #flow/ready #priority/high #comp/tests #comp/engine #scope/core #ai/instruct #task/domain/runtime #task/object/linker-protocol #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 `test_vm_strategy.py` 中的 `ExecutionContext`

我们将导入 `ExitStack` 并创建一个 `MagicMock` 来满足 `ExecutionContext` 的构造函数要求。

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_vm_strategy.py
~~~~~
~~~~~python.old
import pytest
from unittest.mock import MagicMock

from cascade.spec.task import task
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.runtime.strategies.base import ExecutionContext


@task
def add(a: int, b: int) -> int:
~~~~~
~~~~~python.new
import pytest
from unittest.mock import MagicMock
from contextlib import ExitStack

from cascade.spec.task import task
from cascade.runtime.strategies.vm import VMExecutionStrategy
from cascade.runtime.strategies.base import ExecutionContext


@task
def add(a: int, b: int) -> int:
~~~~~

~~~~~act
patch_file
packages/cascade-engine/tests/integration/test_vm_strategy.py
~~~~~
~~~~~python.old
    # 2. Setup strategy and context
    mock_bus = MagicMock()
    strategy = VMExecutionStrategy(bus=mock_bus)
    context = ExecutionContext(active_resources={})

    # 3. Execute
    result = await strategy.execute(target, context)
~~~~~
~~~~~python.new
    # 2. Setup strategy and context
    mock_bus = MagicMock()
    strategy = VMExecutionStrategy(bus=mock_bus)
    
    mock_state_backend = MagicMock()
    context = ExecutionContext(
        run_id="test-run-123",
        state_backend=mock_state_backend,
        run_stack=ExitStack(),
        active_resources={},
    )

    # 3. Execute
    result = await strategy.execute(target, context)
~~~~~

### 下一步建议

这个补丁应该可以解决最后的测试失败。请执行此计划，然后我们再重新运行一次测试套件。如果一切通过，我们就准备好创建 `[COMMIT]` 计划了。

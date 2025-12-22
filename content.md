You are absolutely right to point this out. The test is failing in a way that seems impossible, which is the classic sign that one of our fundamental assumptions is wrong. Thank you for your patience and for providing the precise output.

I have made a critical mistake in the previous plans. I was so focused on the `Connector` and race conditions that I overlooked the most obvious component: the **`Executor`**.

**The root cause is that the test is using `MockWorkExecutor`, which does not actually execute the task's code.**

Let's look at the `MockWorkExecutor` from `harness.py`:
```python
class MockWorkExecutor(Executor):
    async def execute(self, node: Node, args: List[Any], kwargs: Dict[str, Any]):
        await asyncio.sleep(0)
        # It does NOT call node.callable_obj(...)
        return "done"
```
This mock completely ignores the actual function body of `task_a`. It never calls the code that contains `spy.events.append("task_a_waiting")` or `await task_a_can_finish.wait()`.

Therefore, the `Engine` runs, "executes" the task (which does nothing), the workflow finishes instantly, the engine disconnects, and the test fails because the signal it's waiting for was never sent. My previous race condition analysis was correct in spirit, but the problem was even more severe than I thought.

To fix this, we must use the **real `LocalExecutor`** for this test, as it's the only component that will actually run our task's code. The `asyncio.Event` synchronization logic is still essential to prevent the original race condition.

I apologize for the oversight. Let's fix this correctly now.

## [WIP] fix(tests): Use real executor to enable test synchronization

### 错误分析
测试 `test_engine_recovers_from_malformed_rate_limit` 持续失败的根本原因在于，它错误地使用了 `MockWorkExecutor`。这个 Mock Executor 的设计是绕过并替换任务的实际执行逻辑，直接返回一个虚拟结果。因此，我们在 `task_a` 中精心设计的、用于同步测试的 `spy.events.append(...)` 和 `await task_a_can_finish.wait()` 代码**从未被执行**。这导致 `Engine` 瞬间完成了工作流并断开连接，而测试主线程则永远在等待一个永远不会被发出的信号，最终超时失败。

### 用户需求
修复该测试，使其能够稳定地验证 `Engine` 在收到无效约束后的恢复能力。

### 评论
这是一个深刻的教训：测试替身（Test Double）必须被精确地使用。在这种情况下，我们需要测试 `Engine` 与一个**正在执行并阻塞**的任务之间的交互，因此我们必须使用能够真正执行任务代码的 `LocalExecutor`。`MockWorkExecutor` 适用于那些我们只关心任务是否被调度，而不关心其内部逻辑的测试场景。

### 目标
1.  修改 `test_e2e_robustness.py`，在 `Engine` 的实例化过程中，将 `executor` 从 `MockWorkExecutor()` 替换为 `cs.adapters.executors.local.LocalExecutor()`。

### 基本原理
通过使用 `LocalExecutor`，我们确保了 `task_a` 的函数体会被真实地 `await`。这将触发 `spy.events.append()`，并使 `Engine` 在 `task_a_can_finish.wait()` 处可靠地暂停，从而为测试主线程注入控制消息创造了稳定、确定的窗口期，彻底解决了测试中的所有竞态条件。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/core #ai/instruct #task/domain/testing #task/object/test-harness #task/action/fix #task/state/continue

---

### Script

#### Acts 1: 替换为 `LocalExecutor`

我们将修改 `test_e2e_robustness.py` 来使用正确的 Executor。

~~~~~act
patch_file
tests/engine/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
import asyncio
import pytest
from unittest.mock import MagicMock, ANY

import cascade as cs
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskExecutionStarted
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict

from .harness import InProcessConnector, MockWorkExecutor, ControllerTestApp
~~~~~
~~~~~python
import asyncio
import pytest
from unittest.mock import MagicMock, ANY

import cascade as cs
from cascade.adapters.executors.local import LocalExecutor
from cascade.adapters.solvers.native import NativeSolver
from cascade.runtime.engine import Engine
from cascade.runtime.events import TaskExecutionStarted
from cascade.spec.constraint import GlobalConstraint
from dataclasses import asdict

from .harness import InProcessConnector, ControllerTestApp
~~~~~

~~~~~act
patch_file
tests/engine/e2e/test_e2e_robustness.py
~~~~~
~~~~~python
    # 2. Configure and start the engine in the background
    engine = Engine(
        solver=NativeSolver(),
        executor=MockWorkExecutor(),
        bus=engine_bus,
        connector=engine_connector,
    )
~~~~~
~~~~~python
    # 2. Configure and start the engine in the background
    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=engine_bus,
        connector=engine_connector,
    )
~~~~~

### 下一步建议
这次修复是直击要害的。请再次运行测试。它现在应该可以稳定地通过了。

一旦测试通过，我们就可以生成最终的 `[COMMIT]` 计划，将这个漫长但富有成效的调试过程画上句号。

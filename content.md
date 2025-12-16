这是一个预期的失败。由于我们将参数解析逻辑从 `LocalExecutor` 转移到了 `Engine`，`LocalExecutor` 的方法签名已更改，旧的测试调用方法失效。

我将修改 `tests/adapters/executors/test_local.py` 中的测试，使其遵循新的 `Executor` 协议：只接收已解析的 `args` 和 `kwargs`。

## [WIP] fix(tests): 修复 LocalExecutor 单元测试

### 错误分析
`tests/adapters/executors/test_local.py::test_local_executor` 仍在调用旧的 `LocalExecutor.execute(node, graph, upstream_results, resource_context)` 签名。新的签名是 `LocalExecutor.execute(node, args, kwargs)`。

### 用户需求
更新测试以匹配新的 `LocalExecutor` 接口，并确保其核心职责（执行函数）得到正确验证。

### 评论
这次修复是上次架构重构的收尾工作。通过简化 `LocalExecutor` 的测试，我们验证了它的单一职责：接收纯粹的参数并执行函数，而不依赖于复杂的图结构。

### 目标
1.  移除 `test_local_executor` 中所有冗余的图构建代码。
2.  模拟 `Engine` 解析出的最终 `args` 和 `kwargs`。
3.  使用新签名调用 `executor.execute()`。

### 基本原理
将测试的焦点从**图解析**转移到**函数执行**。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/tests #task/object/executor-tests #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 修复 `tests/adapters/executors/test_local.py`

我将重写 `test_local_executor`，使其直接模拟传入已解析的参数。

~~~~~act
write_file
tests/adapters/executors/test_local.py
~~~~~
~~~~~python
import asyncio
from typing import Any, Dict
from cascade.adapters.executors.local import LocalExecutor
from cascade.graph.model import Node
from cascade.spec.task import task


def test_local_executor_sync_execution():
    """
    Tests that the LocalExecutor can execute a synchronous function
    with resolved positional and keyword arguments.
    """
    
    # 1. Define the callable
    @task
    def add(x: int, y: int, z: int = 0) -> int:
        return x + y + z
    
    # 2. Simulate the Node (Only callable_obj is needed here)
    node_add = Node(id="add", name="add", callable_obj=add.func)

    # 3. Simulate arguments resolved by the Engine
    resolved_args = [5]  # positional argument 'x'
    resolved_kwargs = {"y": 10, "z": 2} # keyword arguments 'y' and 'z'

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_add, resolved_args, resolved_kwargs)
    )

    assert result == 17 # 5 + 10 + 2


def test_local_executor_async_execution():
    """
    Tests that the LocalExecutor can execute an asynchronous function.
    """
    
    @task
    async def async_add(x: int) -> int:
        await asyncio.sleep(0.01)
        return x + 1

    node_async = Node(id="async_add", name="async_add", callable_obj=async_add.func)
    
    resolved_args = [5]
    resolved_kwargs = {}

    executor = LocalExecutor()
    result = asyncio.run(
        executor.execute(node_async, resolved_args, resolved_kwargs)
    )
    
    assert result == 6
~~~~~

### 下一步建议

现在 `test_local.py` 已经修复并增强。在提交本次修复之前，我们应该确保新的 `DependencyMissingError` 及其行为在集成测试中得到验证。

我建议：
1. **添加 `src/cascade/runtime/exceptions.py` 的导入**: 在 `src/cascade/runtime/__init__.py` 中公开新定义的异常。
2. **更新集成测试**: 修改 `tests/integration/test_end_to_end.py` 或 `tests/runtime/test_control_flow.py`，以明确断言 `DependencyMissingError` 替代旧的 `KeyError`。

请指示是否继续进行这两步的更新，并准备提交。

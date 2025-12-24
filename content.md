好的，收到了新的测试错误。

 错误分析

错误日志非常清晰：`fixture 'engine' not found`。

这表明我新创建的测试文件 `tests/engine/runtime/test_static_analysis.py` 试图使用一个名为 `engine` 的 Pytest Fixture，但这个 Fixture 在测试的上下文中并不存在。

通常，`engine` Fixture 是在特定的测试文件或通用的 `conftest.py` 文件中定义的，用于创建一个配置好的 `Engine` 实例供测试使用。我在编写测试时，错误地假设了 `engine` Fixture 是全局可用的。

 解决方案

解决方案是在 `tests/engine/runtime/test_static_analysis.py` 文件内部定义一个局部的 `engine` Fixture。这个 Fixture 将会：
1.  导入必要的组件，如 `Engine`, `NativeSolver`, `LocalExecutor`, 和 `MessageBus`。
2.  创建一个配置好的 `Engine` 实例。
3.  `yield` 这个实例给测试函数使用。

这将使测试能够找到并使用一个有效的 `Engine` 实例，从而解决 `fixture not found` 的错误。

我将生成一个计划来修复这个问题。

## [WIP] fix(tests): 为静态分析测试添加缺失的 `engine` fixture

### 错误分析
新创建的集成测试 `tests/engine/runtime/test_static_analysis.py` 依赖于一个名为 `engine` 的 Pytest Fixture，但该 Fixture 并未在该文件的作用域内定义，导致 `fixture 'engine' not found` 错误。

### 用户需求
在 `test_static_analysis.py` 文件中添加一个 `engine` Fixture 的定义，以修复测试设置错误。

### 评论
这是一个常见的测试编写疏忽。通过提供一个局部的、配置正确的 `engine` Fixture，我们可以确保测试环境的完整性和隔离性，让测试能够专注于验证其核心逻辑——静态分析警告功能。

### 目标
1.  在 `tests/engine/runtime/test_static_analysis.py` 文件中导入 `Engine` 和其他必要的依赖。
2.  创建一个名为 `engine` 的 Pytest Fixture。
3.  在该 Fixture 中实例化并返回一个 `Engine` 对象。

### 基本原理
Pytest 的 Fixture 机制允许我们注入测试所需的依赖。通过在测试文件中定义一个与测试函数参数同名的 Fixture，Pytest 会在运行测试时自动调用该 Fixture 并将其返回值作为参数传入。我们将利用此机制来提供一个可用的 `Engine` 实例。

### 标签
#intent/fix #flow/ready #priority/critical #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/pytest-fixture #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 修复 `test_static_analysis.py`

我将使用 `write_file` 覆盖整个测试文件，以添加 Fixture 定义并确保所有导入都已就位。

~~~~~act
write_file
tests/engine/runtime/test_static_analysis.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from unittest.mock import MagicMock

# Imports for the new fixture
from cascade.runtime.engine import Engine
from cascade.adapters.solvers import NativeSolver
from cascade.adapters.executors import LocalExecutor
from cascade.runtime.bus import MessageBus


@pytest.fixture
def engine() -> Engine:
    """Provides a standard Engine instance for integration tests."""
    return Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=MessageBus(),  # A silent bus for clean test output
    )


@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global message bus where it is used by subscribers."""
    mock_bus = MagicMock()
    # Patch the bus used by HumanReadableLogSubscriber
    monkeypatch.setattr("cascade.runtime.subscribers.bus", mock_bus)
    return mock_bus


@cs.task
def another_task():
    return "dependency"


@cs.task
def heavy_recursive_task(n: int, dep=None):
    if n <= 0:
        return "done"
    # ANTI-PATTERN: Recursive call with another task as argument
    return heavy_recursive_task(n - 1, dep=another_task())


@cs.task
def simple_recursive_task(n: int):
    if n <= 0:
        return "done"
    # OKAY: Recursive call with only literals or simple variables
    return simple_recursive_task(n - 1)


@pytest.mark.asyncio
async def test_dynamic_recursion_emits_warning(
    engine: Engine, mock_messaging_bus: MagicMock
):
    """
    Verifies that the dynamic recursion anti-pattern triggers a static analysis warning.
    """
    workflow = heavy_recursive_task(2)
    await engine.run(workflow)

    expected_message = (
        "Task 'heavy_recursive_task' uses a dynamic recursion pattern (calling other "
        "tasks in its arguments) which disables TCO optimizations, "
        "leading to significant performance degradation."
    )

    mock_messaging_bus.warning.assert_called_once_with(
        "graph.analysis.warning",
        task_name="heavy_recursive_task",
        warning_code="CS-W001",
        message=expected_message,
    )


@pytest.mark.asyncio
async def test_simple_recursion_does_not_warn(
    engine: Engine, mock_messaging_bus: MagicMock
):
    """
    Verifies that a standard, optimizable recursive task does NOT trigger a warning.
    """
    workflow = simple_recursive_task(2)
    await engine.run(workflow)

    mock_messaging_bus.warning.assert_not_called()
~~~~~

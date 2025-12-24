好的，我们来完成“阶段二”的最后一步：编写测试来验证我们新加的 Linter 是否能按预期工作。

这是一个典型的 TDD (测试驱动开发) 流程中的“绿”灯环节：我们已经有了实现，现在需要编写一个测试来证明它是正确的。

我将生成一个计划，该计划会首先更新消息定义文件，然后创建一个新的测试文件来验证警告功能。

## [WIP] test(engine): 验证静态分析对动态递归的警告功能

### 用户需求
为新实现的动态递归静态分析器编写一个集成测试。该测试需要验证当引擎运行一个包含“动态递归”反模式的工作流时，会通过消息总线发出一个特定的警告。

### 评论
这是“阶段二：防线建设”的收官之作。通过编写这个测试，我们不仅能确保新功能的正确性，还能为未来的回归测试建立一道防线。遵循“测试意图而非实现”的原则，我们将通过 Mock 消息总线来断言正确的警告“意图”是否被发出，而不是去匹配具体的 UI 文本。

### 目标
1.  在 `cascade-common` 的 `runtime_events.json` 中为新的警告消息添加一个条目。
2.  创建一个新的测试文件 `tests/engine/runtime/test_static_analysis.py`。
3.  在该文件中定义一个包含“动态递归”反模式的任务。
4.  使用 `pytest` 和 `monkeypatch` 来 Mock 全局消息总线。
5.  运行工作流，并断言 `mock_bus.warning` 方法被以正确的语义 ID (`graph.analysis.warning`) 和预期的参数调用。
6.  （可选但推荐）添加一个反向测试，确保一个普通的递归任务**不会**触发警告。

### 基本原理
我们将创建一个集成测试，该测试会完整地运行 `Engine` 的图构建和执行流程。在 `GraphBuilder` 阶段，我们新加的分析逻辑会识别出反模式并在 `Node` 对象上设置 `warns_dynamic_recursion` 标志。随后，在 `GraphExecutionStrategy` 中，这个标志会被检测到，并通过 `bus` 发布一个 `StaticAnalysisWarning` 事件。我们的测试将拦截这个最终的 `bus.warning` 调用，从而验证整个链路的功能是通畅且正确的。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/engine #scope/dx #ai/instruct #task/domain/runtime #task/object/static-analysis #task/action/verification #task/state/continue

---

### Script

#### Acts 1: 更新消息模板

首先，我们在 `runtime_events.json` 中添加新的警告消息模板。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
~~~~~
~~~~~json
    "task.retrying": "   - ⚠️ Task '{task_name}' failed, retrying (attempt {attempt}/{max_attempts}). Delaying for {delay:.2f}s. Error: {error}",

    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector.",
~~~~~
~~~~~json
    "task.retrying": "   - ⚠️ Task '{task_name}' failed, retrying (attempt {attempt}/{max_attempts}). Delaying for {delay:.2f}s. Error: {error}",

    "graph.analysis.warning": "   - ⚠️ [Static Analysis][{warning_code}] in '{task_name}': {message}",

    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector.",
~~~~~

#### Acts 2: 创建静态分析的集成测试

现在，我们创建新的测试文件，并编写验证逻辑。

~~~~~act
write_file
tests/engine/runtime/test_static_analysis.py
~~~~~
~~~~~python
import pytest
import cascade as cs
from unittest.mock import MagicMock
from cascade.runtime.engine import Engine


@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global message bus where it is used by subscribers."""
    mock_bus = MagicMock()
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

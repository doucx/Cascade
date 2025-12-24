好的，我们来完成“阶段二”的验证工作。

首先，我需要为新的静态分析警告添加一个对应的用户可见消息。然后，我将编写一个集成测试来验证当引擎遇到“动态递归”反模式时，这个警告能够被正确地触发和发布。

这个测试将严格遵循“验证意图而非实现”的原则，通过 Mock 消息总线来断言正确的语义 ID 和数据负载被调用。

## [WIP] test(engine): 添加静态分析警告的集成测试

### 用户需求
编写一个集成测试，以验证当 `GraphExecutionStrategy` 检测到 `warns_dynamic_recursion` 标志时，能够通过 `HumanReadableLogSubscriber` 正确地发布一个警告消息。

### 评论
这是对“阶段二”成果的关键验证。一个没有被测试覆盖的功能是不存在的。这个测试将确保我们为提升开发者体验所做的静态分析工作能够端到端地正常运作，从图构建时的检测，到执行策略中的事件发布，再到最终通过消息总线呈现给用户。

### 目标
1.  在 `cascade-common` 的 `runtime_events.json` 中为新的警告添加消息模板。
2.  创建一个新的测试文件 `tests/engine/runtime/test_static_analysis.py`。
3.  在该文件中，定义一个包含“动态递归”反模式的工作流。
4.  编写一个测试用例，运行该工作流，并断言 `cascade.common.messaging.bus` 的 `warning` 方法被以 `graph.analysis.warning` 的消息 ID 调用。

### 基本原理
测试将使用 `monkeypatch` 来替换 `cascade.runtime.subscribers` 模块中导入的全局 `bus` 单例为一个 `MagicMock` 对象。然后，我们会配置一个真实的 `Engine`，并让其运行一个包含反模式的任务。`Engine` 的 `GraphExecutionStrategy` 会检测到节点的 `warns_dynamic_recursion` 标志并发布 `StaticAnalysisWarning` 事件。`HumanReadableLogSubscriber` 监听到此事件后，会调用被我们 Mock 的全局 `bus` 的 `.warning()` 方法。最后，我们对这个 Mock 对象的调用进行断言，从而验证了整个流程的正确意图。

### 标签
#intent/tooling #flow/ready #priority/high #comp/tests #comp/engine #scope/dx #ai/instruct #task/domain/runtime #task/object/static-analysis #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: `cascade-common` - 添加警告消息模板

我们首先在 `runtime_events.json` 中定义用户将看到的警告文本。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
~~~~~
~~~~~json
    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector.",

    "localbus.callback_error": "[LocalBus] Callback error on topic '{topic}': {error}",
    "localbus.retained_callback_error": "[LocalBus] Sync/Retained callback error on topic '{topic}': {error}"
}
~~~~~
~~~~~json
    "engine.connector.connected": "📡 Engine connected to external connector.",
    "engine.connector.disconnected": "🔌 Engine disconnected from external connector.",

    "graph.analysis.warning": "   - ⚠️  [CS-W001] Static analysis warning for task '{task_name}': {message}",

    "localbus.callback_error": "[LocalBus] Callback error on topic '{topic}': {error}",
    "localbus.retained_callback_error": "[LocalBus] Sync/Retained callback error on topic '{topic}': {error}"
}
~~~~~

#### Acts 2: `cascade-engine` - 编写集成测试

现在，我们创建新的测试文件并编写测试用例。

~~~~~act
write_file
tests/engine/runtime/test_static_analysis.py
~~~~~
~~~~~python
import pytest
from unittest.mock import MagicMock

import cascade as cs
from cascade.runtime import Engine, HumanReadableLogSubscriber, MessageBus
from cascade.adapters.solvers import NativeSolver
from cascade.adapters.executors import LocalExecutor


@pytest.mark.asyncio
async def test_dynamic_recursion_emits_warning(monkeypatch):
    """
    Verifies that the engine emits a static analysis warning when it detects
    the dynamic recursion anti-pattern.
    """
    # 1. Mock the user-facing message bus that the subscriber uses
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.runtime.subscribers.bus", mock_bus)

    # 2. Define the anti-pattern
    @cs.task
    def some_other_task(x):
        return x  # A simple task

    @cs.task
    def dynamic_recursive_task(x):
        if x <= 0:
            return "done"
        # ANTI-PATTERN: Recursive call with another task call in its arguments
        return dynamic_recursive_task(some_other_task(x - 1))

    # 3. Setup a real engine and subscriber
    engine_event_bus = MessageBus()
    # The subscriber listens to the engine's events
    _ = HumanReadableLogSubscriber(engine_event_bus)

    engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=engine_event_bus,  # Engine uses its internal event bus
    )

    # 4. Run the workflow
    await engine.run(dynamic_recursive_task(1))

    # 5. Assert the INTENT on the mocked user-facing bus
    mock_bus.warning.assert_called_once_with(
        "graph.analysis.warning",
        task_name="dynamic_recursive_task",
        warning_code="CS-W001",
        message=(
            "Task 'dynamic_recursive_task' uses a dynamic recursion pattern (calling other "
            "tasks in its arguments) which disables TCO optimizations, "
            "leading to significant performance degradation."
        ),
    )
~~~~~

### 下一步建议
我们已经成功为“阶段二”的功能添加了验证，确保了其健壮性。现在，我们已经为路线图的下一个主要步骤做好了充分准备。

我建议我们正式开始 **阶段三：内核突破 —— 结构化 JIT 与动态修补**。这项工作的核心目标是改造 `GraphExecutionStrategy`，使其利用 `template_id` 来缓存执行计划，从而彻底解决 Heavy Path 的性能瓶颈。

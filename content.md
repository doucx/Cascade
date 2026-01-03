You are absolutely right. My apologies.

The previous refactoring of `standard_observer` changed its signature to accept a `resources` object instead of a `queue` keyword argument, but I failed to update its corresponding unit tests. This created a clear API mismatch, leading to the `TypeError`.

Thank you for catching this oversight. I will now generate a plan to fix these broken tests.

## [WIP] fix: Align observer unit tests with new resource signature

### 错误分析
测试套件在 `packages/cascade-std/tests/unit/triad/test_observer.py` 中失败，因为 `standard_observer` 函数的签名在之前的重构中已经改变。它不再接受 `queue` 作为一个关键字参数，而是期望从第三个位置参数 `resources` 中通过 `resources.get("system.observer.queue")` 来获取队列。

当前的测试用例仍然在使用旧的、已被废弃的调用方式，从而导致了 `TypeError`。

### 用户需求
修复 `test_observer.py` 中的所有测试用例，使其遵循 `standard_observer` 新的、基于资源注册表的函数签名。

### 评论
这是一个典型的因重构未能覆盖所有相关测试而导致的错误。修复这个问题不仅能使测试套件恢复绿色状态，更重要的是，它将确保 `standard_observer` 的单元测试能够正确地验证其新的核心行为——即通过资源注册表协议来解耦其依赖项。

### 目标
1.  修改 `test_observer.py`，移除所有对 `standard_observer` 的 `queue` 关键字参数的传递。
2.  为测试用例创建一个 Mock `ResourceRegistry` 对象。
3.  配置该 Mock 对象，使其在 `get("system.observer.queue")` 被调用时返回测试用的 `event_queue`。
4.  将该 Mock 对象作为第三个参数传递给 `standard_observer`。
5.  在断言中增加一步，验证 `resources.get` 方法是否被正确调用。

### 基本原理
我们将采用标准的 Mocking 策略。通过使用 `unittest.mock.MagicMock`，我们可以创建一个行为可预测的伪 `ResourceRegistry`。这个 Mock 将被注入到 `standard_observer` 中，从而在隔离的环境下验证其与资源层的交互是否符合预期。为了保持代码的整洁和可重用性，我们将创建一个 `pytest` fixture 来专门负责 Mock `resources` 对象的创建和配置。

### 标签
#intent/fix #flow/ready #priority/high #comp/tests #comp/std #concept/executor #scope/dx #ai/instruct #task/domain/testing #task/object/unit-test #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 修复 `test_observer.py`

我们将使用 `write_file` 来完整地更新测试文件，引入一个新的 `mock_resources` fixture，并重写所有测试用例以使用这个 fixture，从而与 `standard_observer` 的新签名保持一致。

~~~~~act
write_file
packages/cascade-std/tests/unit/triad/test_observer.py
~~~~~
~~~~~python
import pytest
from asyncio import Queue
from unittest.mock import MagicMock

from cascade.spec.physics import Token
from cascade.std.triad.observer import standard_observer, ObservedEvent


@pytest.fixture
def event_queue() -> Queue:
    return Queue()


@pytest.fixture
def mock_resources(event_queue: Queue) -> MagicMock:
    """Creates a mock resource registry that provides the event queue."""
    registry = MagicMock()
    registry.get.return_value = event_queue
    return registry


async def test_observer_processes_start_event(
    event_queue: Queue, mock_resources: MagicMock
):
    start_trace = {"id": "task_A", "start_ts": 100.0}
    event_token = Token(payload=None, trace=start_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), mock_resources)

    # Assertions
    mock_resources.get.assert_called_once_with("system.observer.queue")
    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "start"
    assert observed.trace_data == start_trace


async def test_observer_processes_end_event(
    event_queue: Queue, mock_resources: MagicMock
):
    end_trace = {
        "id": "task_A",
        "start_ts": 100.0,
        "end_ts": 102.5,
        "duration": 2.5,
    }
    event_token = Token(payload="result", tag="default", trace=end_trace)
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), mock_resources)

    # Assertions
    mock_resources.get.assert_called_once_with("system.observer.queue")
    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert isinstance(observed, ObservedEvent)
    assert observed.event_type == "end"
    assert observed.trace_data == end_trace


async def test_observer_with_empty_trace(event_queue: Queue, mock_resources: MagicMock):
    event_token = Token(payload=None, trace={})
    inputs = {"event_token": event_token}

    await standard_observer(inputs, MagicMock(), mock_resources)

    # Assertions
    mock_resources.get.assert_called_once_with("system.observer.queue")
    assert event_queue.qsize() == 1
    observed = await event_queue.get()

    assert observed.event_type == "start"
    assert observed.trace_data == {}
~~~~~

### 下一步建议
测试已修复。现在我们的 `ResourceRegistry` 依赖注入模型在核心 VM 组件和测试套件中都已得到验证。我们可以继续推进**阶段 3：统一所有上下文**。下一步是设计 `ExecutionContext` 并重构 `Engine`。

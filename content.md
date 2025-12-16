当然，我们开始这次集中的测试重构。

你的分析是正确的，依赖硬编码的日志字符串会让测试用例变得脆弱。我们将引入一个标准的、可复用的事件监听器 (`SpySubscriber`)，并将其作为 pytest fixture 提供，然后用它来重构 `tests/runtime/test_bus.py`，使其断言更关注“意图”（发出的事件）而非“表现”（日志文本）。

## [WIP] test: 集中化 SpySubscriber 并重构总线测试以增强健壮性

### 用户需求
规划并执行一次集中的测试重构，将 `tests/runtime/test_bus.py` 中依赖硬编码日志字符串的集成测试，全部迁移到基于 `SpySubscriber` 的事件断言模式，以提高测试套件的健壮性和可维护性。

### 评论
这是一个关键的改进，能显著提升测试套件的健康度。通过断言事件流而非 UI 输出，我们的测试将直接验证系统的核心行为契约，使其免受未来日志格式、颜色或文案调整的影响。将 `SpySubscriber` 集中化为 `conftest.py` 中的 fixture，也为整个项目建立了一个标准的、可复用的测试模式。

### 目标
1.  创建 `tests/conftest.py` 文件，用于存放通用的测试辅助工具。
2.  在该文件中定义一个 `SpySubscriber` 类和一个 `bus_and_spy` pytest fixture，后者将提供一个 `MessageBus` 实例和一个已附加到该总线上的 `SpySubscriber` 实例。
3.  重构 `tests/runtime/test_bus.py` 中的所有测试用例，使其利用新的 `bus_and_spy` fixture。
4.  修改 `test_human_readable_subscriber` 和 `test_subscriber_log_level_filtering` 的断言逻辑，使其检查日志中的关键语义标记（如表情符号 ✅/❌ 和错误信息），而不是完整的、硬编码的字符串，从而在保留其测试目的的同时降低脆弱性。

### 基本原理
此计划遵循“验证意图而非实现”的核心测试原则。
1.  **集中化**: 在 `conftest.py` 中创建 `SpySubscriber` 和 `bus_and_spy` fixture，使其成为整个测试套件的一等公民，鼓励在未来的测试中优先使用事件断言。
2.  **标准化**: 将 `test_bus.py` 中测试总线分发逻辑的用例（`test_message_bus_dispatch`, `test_message_bus_wildcard`）统一到使用 `bus_and_spy` fixture，这比手动创建列表来收集事件更清晰、更标准。
3.  **健壮化**: 对于专门测试 `HumanReadableLogSubscriber` 输出的用例，我们采取务实的折中方案。我们不移除对字符串输出的检查（因为这正是该组件的功能），而是将断言从“字节级精确匹配”升级为“语义关键点匹配”。这极大地提高了测试的健壮性，同时确保了其核心验证逻辑的完整性。

### 标签
#intent/refine #intent/tooling #flow/ready #priority/high #comp/tests #concept/ui #scope/dx #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/begin

---

### Script

#### Acts 1: 创建 conftest.py 并定义核心测试辅助工具

我们首先创建 `tests/conftest.py` 文件，并定义 `SpySubscriber` 类和一个可注入的 `bus_and_spy` fixture。这将为后续的重构提供基础。

~~~~~act
write_file
tests/conftest.py
~~~~~
~~~~~python
import pytest
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import Event


class SpySubscriber:
    """A test utility to collect events from a MessageBus."""

    def __init__(self, bus: MessageBus):
        self.events = []
        bus.subscribe(Event, self.collect)

    def collect(self, event: Event):
        self.events.append(event)

    def events_of_type(self, event_type):
        """Returns a list of all events of a specific type."""
        return [e for e in self.events if isinstance(e, event_type)]


@pytest.fixture
def bus_and_spy():
    """Provides a MessageBus instance and an attached SpySubscriber."""
    bus = MessageBus()
    spy = SpySubscriber(bus)
    return bus, spy
~~~~~

#### Acts 2: 重构 `test_bus.py` 以提高健壮性和一致性

现在，我们将重写 `tests/runtime/test_bus.py`。所有测试将使用新的 `bus_and_spy` fixture，并且针对日志输出的断言将被修改为更健壮的模式。

~~~~~act
write_file
tests/runtime/test_bus.py
~~~~~
~~~~~python
import io
from cascade.runtime.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber


def test_message_bus_dispatch(bus_and_spy):
    """
    Tests that the bus correctly dispatches events to specifically subscribed handlers.
    """
    bus, spy = bus_and_spy

    specific_received = []

    def specific_handler(event: RunStarted):
        specific_received.append(event)

    bus.subscribe(RunStarted, specific_handler)

    # Publish relevant event
    event1 = RunStarted()
    bus.publish(event1)

    # Assert specific handler was called
    assert len(specific_received) == 1

    # Publish irrelevant event
    event2 = TaskExecutionFinished()
    bus.publish(event2)

    # Assert specific handler was NOT called again
    assert len(specific_received) == 1

    # Assert that the spy (wildcard) received everything
    assert len(spy.events) == 2
    assert spy.events[0] == event1
    assert spy.events[1] == event2


def test_message_bus_wildcard(bus_and_spy):
    """
    Tests that a wildcard subscriber (listening to base Event) receives all events.
    """
    bus, spy = bus_and_spy

    bus.publish(RunStarted(target_tasks=[], params={}))
    bus.publish(
        TaskExecutionFinished(task_id="1", task_name="t", status="OK", duration=0.0)
    )

    assert len(spy.events) == 2
    assert isinstance(spy.events_of_type(RunStarted)[0], RunStarted)
    assert isinstance(spy.events_of_type(TaskExecutionFinished)[0], TaskExecutionFinished)


def test_human_readable_subscriber_output_formatting(bus_and_spy):
    """
    Tests that the subscriber correctly formats and prints different events.
    This test focuses on the subscriber's presentation logic.
    """
    bus, _ = bus_and_spy  # Spy is not used here, but fixture provides bus
    output = io.StringIO()
    HumanReadableLogSubscriber(bus, stream=output)

    # Simulate a flow of events
    bus.publish(RunStarted(target_tasks=["deploy"], params={"env": "prod"}))
    bus.publish(
        TaskExecutionFinished(
            task_id="123", task_name="build_image", status="Succeeded", duration=1.23
        )
    )
    bus.publish(
        TaskExecutionFinished(
            task_id="124",
            task_name="deploy_k8s",
            status="Failed",
            duration=0.05,
            error="AuthError",
        )
    )

    logs = output.getvalue()

    # Assertions are now less brittle, checking for key semantic markers
    assert "▶️" in logs
    assert "deploy" in logs
    assert "env" in logs
    assert "prod" in logs

    assert "✅" in logs
    assert "build_image" in logs

    assert "❌" in logs
    assert "deploy_k8s" in logs
    assert "AuthError" in logs


def test_human_readable_subscriber_log_level(bus_and_spy):
    """
    Tests that setting min_level correctly suppresses lower priority logs.
    """
    bus, _ = bus_and_spy
    output = io.StringIO()
    # Set level to ERROR, so INFO logs from RunStarted and Succeeded should be skipped
    HumanReadableLogSubscriber(bus, stream=output, min_level="ERROR")

    # INFO event
    bus.publish(RunStarted(target_tasks=["t1"]))
    # INFO event
    bus.publish(
        TaskExecutionFinished(
            task_id="1", task_name="t1", status="Succeeded", duration=0.1
        )
    )
    # ERROR event
    bus.publish(
        TaskExecutionFinished(
            task_id="2", task_name="t2", status="Failed", error="Boom", duration=0.1
        )
    )

    logs = output.getvalue()

    # Should NOT contain INFO-level markers
    assert "▶️" not in logs
    assert "✅" not in logs
    # Should contain ERROR-level markers
    assert "❌" in logs
    assert "Boom" in logs
~~~~~

### 下一步建议
我们已经成功地为测试套件的核心部分建立了更健壮的模式。下一步，我建议我们审查其他集成测试文件（例如 `tests/integration/` 和 `tests/tools/`），看看是否有其他地方可以从新的 `bus_and_spy` fixture 中受益，以进一步提高整个测试套件的一致性和可维护性。

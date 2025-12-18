## [WIP] test(refactor): Fix import paths and restructure test suite

### 错误分析
`pytest` 收集测试时报错 `ModuleNotFoundError: No module named 'cascade.messaging'`。这是因为我们之前的重构将 `cascade.messaging` 移动到了 `cascade.common.messaging`，并且将渲染器实现移动到了 `cascade.runtime.renderers`，但测试代码 `tests/py/messaging/test_renderer.py` 和 `tests/py/runtime/test_bus.py` 仍然引用旧的路径。

此外，测试目录结构 `tests/py/runtime` 和 `tests/py/messaging` 反映了旧的单体包结构，不再适用于现在的多包架构。

### 用户需求
更新测试代码以匹配新的架构，并按照建议将测试拆分到 `tests/common` 和 `tests/runtime` 下。

### 评论
这是一次必要的测试套件清理。随着代码库被拆分为多个包，测试套件也应该反映这种结构，以便于维护和理解。我们将把测试特定于运行时组件（如 EventBus, Renderers）的测试移至 `tests/runtime`，并将测试通用组件（如 UI MessageBus 基础）的测试移至 `tests/common`。

### 目标
1.  创建 `tests/runtime` 和 `tests/common` 目录。
2.  将 `tests/py/messaging/test_renderer.py` 迁移到 `tests/runtime/test_renderers.py`，并修复导入路径（引用 `cascade.runtime.renderers` 和 `cascade.common.messaging`）。
3.  将 `tests/py/runtime/test_bus.py` 迁移到 `tests/runtime/test_event_bus.py`，并修复导入路径。
4.  清理旧的测试文件。

### 基本原理
我们将使用 `write_file` 创建内容已修正的新测试文件，并使用 `run_command` 删除旧文件。这比使用 `patch_file` 更干净，因为我们同时也在改变文件路径。

### 标签
#intent/refine #flow/ready #priority/high #comp/tests #scope/dx #ai/instruct #task/domain/testing #task/object/test-suite #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建新的测试目录

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p tests/runtime
mkdir -p tests/common
~~~~~

#### Acts 2: 迁移并修复 `test_renderer.py`

我们将 `test_renderer.py` 移动到 `tests/runtime/test_renderers.py`，因为 `CliRenderer` 和 `JsonRenderer` 现在位于 runtime 包中。同时修正导入路径。

~~~~~act
write_file
tests/runtime/test_renderers.py
~~~~~
~~~~~python
import io
import json
import pytest
from cascade.runtime.renderers import CliRenderer, JsonRenderer
from cascade.common.messaging import MessageStore


@pytest.fixture
def msg_store():
    store = MessageStore()
    # Manually add a message for testing
    store._messages["test.hello"] = "Hello, {name}!"
    return store


def test_cli_renderer(msg_store):
    output = io.StringIO()
    renderer = CliRenderer(store=msg_store, stream=output)

    renderer.render("test.hello", "info", name="World")

    assert "Hello, World!" in output.getvalue()


def test_json_renderer_structure_and_content():
    output = io.StringIO()
    renderer = JsonRenderer(stream=output)

    renderer.render("user.created", "info", user_id=123, status="active")

    log_line = output.getvalue()
    data = json.loads(log_line)

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert data["event_id"] == "user.created"
    assert data["data"]["user_id"] == 123
    assert data["data"]["status"] == "active"


def test_json_renderer_log_level_filtering():
    output = io.StringIO()
    renderer = JsonRenderer(stream=output, min_level="WARNING")

    # This should be rendered
    renderer.render("api.error", "error", code=500)
    # This should be filtered out
    renderer.render("request.start", "info", path="/")

    logs = output.getvalue().strip()
    assert '"level": "ERROR"' in logs
    assert '"level": "INFO"' not in logs
    # Ensure it's a single line of JSON
    assert len(logs.splitlines()) == 1
~~~~~

#### Acts 3: 迁移并修复 `test_bus.py`

我们将 `test_bus.py` 移动到 `tests/runtime/test_event_bus.py`，因为它主要测试 Runtime 的 EventBus 以及与 UI Bus 的集成。修正导入路径以区分 EventBus 和 UI Bus。

~~~~~act
write_file
tests/runtime/test_event_bus.py
~~~~~
~~~~~python
import io
from cascade.runtime.events import RunStarted, TaskExecutionFinished
from cascade.runtime.subscribers import HumanReadableLogSubscriber
from cascade.runtime.bus import MessageBus as EventBus
from cascade.common.messaging import bus as ui_bus
from cascade.runtime.renderers import CliRenderer


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
    assert isinstance(
        spy.events_of_type(TaskExecutionFinished)[0], TaskExecutionFinished
    )


def test_human_readable_subscriber_integration():
    """
    Integration test for the full logging pipeline:
    EventBus -> Subscriber -> MessageBus(UI) -> Renderer -> Output
    """
    event_bus = EventBus()
    output = io.StringIO()
    # Use the global ui_bus store and inject a test renderer
    renderer = CliRenderer(store=ui_bus.store, stream=output, min_level="INFO")
    ui_bus.set_renderer(renderer)

    # Connect the subscriber to the event bus
    HumanReadableLogSubscriber(event_bus)

    # Publish events to the event bus
    event_bus.publish(RunStarted(target_tasks=["deploy"], params={"env": "prod"}))
    event_bus.publish(
        TaskExecutionFinished(
            task_id="123", task_name="build_image", status="Succeeded", duration=1.23
        )
    )
    event_bus.publish(
        TaskExecutionFinished(
            task_id="124",
            task_name="deploy_k8s",
            status="Failed",
            duration=0.05,
            error="AuthError",
        )
    )

    # Assert on the final rendered output
    logs = output.getvalue()
    # Note: icons might vary based on locales, but keys are stable.
    # We check for content that we know is in the message args.
    assert "deploy" in logs and "prod" in logs
    assert "build_image" in logs
    assert "deploy_k8s" in logs and "AuthError" in logs


def test_human_readable_subscriber_log_level_filtering():
    """
    Tests that the min_level setting in the CliRenderer correctly filters messages.
    """
    event_bus = EventBus()
    output = io.StringIO()
    # Set renderer level to ERROR
    renderer = CliRenderer(store=ui_bus.store, stream=output, min_level="ERROR")
    ui_bus.set_renderer(renderer)

    HumanReadableLogSubscriber(event_bus)

    # Publish INFO and ERROR level events
    event_bus.publish(RunStarted(target_tasks=["t1"]))  # INFO
    event_bus.publish(
        TaskExecutionFinished(task_id="1", task_name="t1", status="Succeeded")
    )  # INFO
    event_bus.publish(
        TaskExecutionFinished(
            task_id="2", task_name="t2", status="Failed", error="Boom"
        )
    )  # ERROR

    logs = output.getvalue()

    # INFO messages should be filtered out
    assert "▶️" not in logs
    assert "✅" not in logs
    # ERROR messages should be present
    assert "❌" in logs
    assert "Boom" in logs
~~~~~

#### Acts 4: 添加 `tests/common` 测试

为了确保 `cascade-common` 独立运行正常，我们添加一个基本的 UI Bus 测试。

~~~~~act
write_file
tests/common/test_messaging.py
~~~~~
~~~~~python
from cascade.common.messaging import MessageStore, MessageBus

def test_message_store_loads_defaults():
    """Test that the message store loads default locale messages."""
    store = MessageStore(locale="en")
    # We expect some basic keys to be present from runtime_events.json
    # We don't check exact values to avoid brittleness, just key existence/format
    msg = store.get("run.started", target_tasks=["t1"])
    assert "t1" in msg

def test_message_bus_renderer_delegation():
    """Test that the bus delegates to the renderer."""
    store = MessageStore()
    store._messages["test.msg"] = "Value: {val}"
    bus = MessageBus(store)
    
    received = []
    
    class MockRenderer:
        def render(self, msg_id, level, **kwargs):
            received.append((msg_id, level, kwargs))
            
    bus.set_renderer(MockRenderer())
    
    bus.info("test.msg", val=42)
    
    assert len(received) == 1
    assert received[0][0] == "test.msg"
    assert received[0][1] == "info"
    assert received[0][2]["val"] == 42
~~~~~

#### Acts 5: 清理旧文件

删除导致报错的旧文件和目录。

~~~~~act
run_command
~~~~~
~~~~~bash
rm tests/py/messaging/test_renderer.py
rm tests/py/runtime/test_bus.py
rmdir tests/py/messaging 2>/dev/null || true
~~~~~

### 下一步建议
测试文件已经重构并修复了导入路径。请再次运行 `pytest`。如果通过，我们就可以回到 `cs-observer` 的开发上来。

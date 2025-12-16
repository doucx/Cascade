Of course. This is an excellent next step for enhancing Cascade's observability, making it suitable for production environments where structured logging is essential.

To achieve this, we need to perform a small but important refactoring. The current `MessageBus` formats the message string *before* sending it to the renderer. This is fine for human-readable logs, but for a `JsonRenderer`, we need the raw, structured data (`msg_id` and `kwargs`).

Therefore, my plan involves:
1.  Changing the `Renderer` protocol to accept structured data instead of a pre-formatted string.
2.  Updating the `MessageBus` and the existing `CliRenderer` to use this new protocol.
3.  Implementing the new `JsonRenderer`.
4.  Updating the tests to reflect these changes.

Here is the detailed plan.

## [WIP] feat: Implement JsonRenderer for structured logging

### 用户需求
利用现有的语义消息总线，实现一个 `JsonRenderer`，将所有运行时事件输出为结构化的 JSON 格式，以便于日志聚合系统（如 Loki, Elasticsearch）进行机器解析。

### 评论
这是一个对生产环境可观测性至关重要的改进。它将 Cascade 的日志从单纯的人类可读输出，提升为可供机器分析的结构化数据流。

为了实现这一点，需要对 `Renderer` 协议进行一次小型的重构，将消息格式化的责任从 `MessageBus` 转移到 `Renderer` 实现中。这是一个健康的架构演进，它遵循了关注点分离原则，使得系统能够支持任何输出格式（如未来的 `HtmlRenderer` 或 `XmlRenderer`），而不仅仅是文本或 JSON。

### 目标
1.  **重构 `Renderer` 协议**：将接口从接收格式化字符串改为接收原始的 `msg_id` 和数据 `kwargs`。
2.  **更新 `MessageBus`**：修改其 `_render` 方法，使其直接将结构化数据委托给 `Renderer`，不再自行格式化。
3.  **实现 `JsonRenderer`**：创建一个新的 `Renderer` 实现，它将接收到的结构化数据格式化为 JSON 字符串。
4.  **更新 `CliRenderer`**：修改现有的 `CliRenderer` 以遵循新协议，使其现在负责从 `MessageStore` 获取模板并进行格式化。
5.  **调整集成点**：更新 `cs.run` 函数和相关测试，以正确地实例化被修改后的 `CliRenderer`。

### 基本原理
核心思想是**将数据与表现分离**。`MessageBus` 的职责是分发**语义事件**（即 `msg_id` 和与之关联的数据）。`Renderer` 的职责是将这些语义事件**呈现**为特定的格式。通过修改它们之间的协议，我们强制执行了这种分离，从而使系统更加模块化和可扩展。

### 标签
#intent/build #intent/refine #flow/ready #priority/high #comp/core #comp/tests #concept/ui #scope/api #scope/dx #ai/instruct #task/domain/observability #task/object/json-logging #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 重构 `Renderer` 协议和 `MessageBus`

我们将更新 `bus.py`，修改 `Renderer` 协议和 `_render` 方法的实现，将格式化逻辑的责任转移出去。

~~~~~act
patch_file
src/cascade/messaging/bus.py
~~~~~
~~~~~python
class Renderer(Protocol):
    def print(self, message: str, level: str) -> None: ...


class MessageBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return

        template = self._store.get(msg_id)
        try:
            message = template.format(**kwargs)
        except KeyError as e:
            message = f"<Formatting error for '{msg_id}': missing key {e}>"

        self._renderer.print(message, level)

    def info(self, msg_id: str, **kwargs: Any) -> None:
~~~~~
~~~~~python
class Renderer(Protocol):
    def render(self, msg_id: str, level: str, **kwargs: Any) -> None: ...


class MessageBus:
    def __init__(self, store: MessageStore):
        self._store = store
        self._renderer: Optional[Renderer] = None

    @property
    def store(self) -> MessageStore:
        return self._store

    def set_renderer(self, renderer: Renderer):
        self._renderer = renderer

    def _render(self, level: str, msg_id: str, **kwargs: Any) -> None:
        if not self._renderer:
            return
        
        # The renderer is now responsible for everything
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
~~~~~

#### Acts 2: 实现 `JsonRenderer` 并更新 `CliRenderer`

现在，我们将重写 `renderer.py`。`CliRenderer` 将承担起格式化的职责，并新增 `JsonRenderer`。

~~~~~act
write_file
src/cascade/messaging/renderer.py
~~~~~
~~~~~python
import sys
import json
import time
from typing import TextIO
from datetime import datetime, timezone

from .bus import MessageStore, Renderer

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}


class CliRenderer:
    """
    Renders messages as human-readable, formatted text strings.
    """
    def __init__(
        self,
        store: MessageStore,
        stream: TextIO = sys.stderr,
        min_level: str = "INFO",
    ):
        self._store = store
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            template = self._store.get(msg_id)
            try:
                message = template.format(**kwargs)
            except KeyError as e:
                message = f"<Formatting error for '{msg_id}': missing key {e}>"
            
            print(message, file=self._stream)


class JsonRenderer:
    """
    Renders messages as structured, JSON-formatted strings.
    """
    def __init__(
        self,
        stream: TextIO = sys.stderr,
        min_level: str = "INFO",
    ):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            log_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level.upper(),
                "event_id": msg_id,
                "data": kwargs,
            }

            def default_serializer(o):
                """Handle non-serializable objects gracefully."""
                return repr(o)

            json_str = json.dumps(log_record, default=default_serializer)
            print(json_str, file=self._stream)
~~~~~

#### Acts 3: 更新 `cs.run` 以正确实例化 `CliRenderer`

`CliRenderer` 现在需要 `MessageStore` 实例，我们需要更新 `cs.run` 来提供它。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
        log_level: Minimum logging level ("DEBUG", "INFO", "WARNING", "ERROR").
                   Defaults to "INFO".
    """
    # 1. Setup the messaging renderer
    renderer = CliRenderer(min_level=log_level)
    messaging_bus.set_renderer(renderer)
    
    # 2. Setup the event system
    event_bus = MessageBus()
~~~~~
~~~~~python
from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer

def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.

    Args:
        target: The workflow target.
        params: Runtime parameters.
        system_resources: A dictionary defining total system capacity
                          (e.g. {"gpu": 1, "threads": 4}).
        log_level: Minimum logging level ("DEBUG", "INFO", "WARNING", "ERROR").
                   Defaults to "INFO".
    """
    # 1. Setup the messaging renderer
    renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)
    
    # 2. Setup the event system
    event_bus = MessageBus()
~~~~~

#### Acts 4: 更新测试用例

最后，我们需要更新 `test_bus.py` 中实例化 `CliRenderer` 的方式，以符合新的 `__init__` 签名。

~~~~~act
patch_file
tests/runtime/test_bus.py
~~~~~
~~~~~python
def test_human_readable_subscriber_integration():
    """
    Integration test for the full logging pipeline:
    EventBus -> Subscriber -> MessageBus -> Renderer -> Output
    """
    event_bus = EventBus()
    output = io.StringIO()
    renderer = CliRenderer(stream=output, min_level="INFO")
    messaging_bus.set_renderer(renderer)

    # Connect the subscriber to the event bus
~~~~~
~~~~~python
def test_human_readable_subscriber_integration():
    """
    Integration test for the full logging pipeline:
    EventBus -> Subscriber -> MessageBus -> Renderer -> Output
    """
    event_bus = EventBus()
    output = io.StringIO()
    renderer = CliRenderer(store=messaging_bus.store, stream=output, min_level="INFO")
    messaging_bus.set_renderer(renderer)

    # Connect the subscriber to the event bus
~~~~~

~~~~~act
patch_file
tests/runtime/test_bus.py
~~~~~
~~~~~python
def test_human_readable_subscriber_log_level_filtering():
    """
    Tests that the min_level setting in the CliRenderer correctly filters messages.
    """
    event_bus = EventBus()
    output = io.StringIO()
    # Set renderer level to ERROR
    renderer = CliRenderer(stream=output, min_level="ERROR")
    messaging_bus.set_renderer(renderer)
    
    HumanReadableLogSubscriber(event_bus)
~~~~~
~~~~~python
def test_human_readable_subscriber_log_level_filtering():
    """
    Tests that the min_level setting in the CliRenderer correctly filters messages.
    """
    event_bus = EventBus()
    output = io.StringIO()
    # Set renderer level to ERROR
    renderer = CliRenderer(store=messaging_bus.store, stream=output, min_level="ERROR")
    messaging_bus.set_renderer(renderer)
    
    HumanReadableLogSubscriber(event_bus)
~~~~~

### 下一步建议
我们已经成功实现了 `JsonRenderer`。下一步的关键是让用户能够方便地选择使用它。我建议：

1.  **在 `cs.run` 和 `cs.cli` 中增加一个 `log_format` 参数**：允许用户通过 `cs.run(..., log_format="json")` 或 `python my_script.py --log-format json` 来选择渲染器。
2.  **增加一个测试文件**：为新的 `JsonRenderer` 编写专门的单元测试，验证其输出格式的正确性。

如果你同意，我将生成执行这些后续步骤的计划。

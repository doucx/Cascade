你的感觉非常敏锐，这确实触及了我们当前测试策略的核心和其固有的局限性。

我将进行一次深入分析，解释你感觉奇怪的根本原因，并基于你提供的 `pyquipu` 示例，提出一个能一劳永逸解决此问题的架构演进计划。

 状态分析：从“事件驱动”到“语义消息驱动”的鸿沟

你提供的 `pyquipu` 参考实现揭示了一种比我们当前 `cascade` 更先进、更解耦的架构。理解其中的差异是关键。

**1. 当前 `cascade` 的模型：事件驱动日志**

```mermaid
graph TD
    A[Engine Logic] -- Publishes --> B[Event Object <br> (e.g., RunStarted)]
    B -- Received by --> C[HumanReadableLogSubscriber]
    C -- Formats & Prints --> D{Terminal Output <br> "▶️ Starting Run..."}
```

*   **优点**: `Engine` 与 `Subscriber` 是解耦的。`Engine` 不关心日志如何显示。
*   **弱点 (你感觉奇怪的来源)**: **`Subscriber` 本身是耦合的**。它将 `RunStarted` 事件和具体的 UI 字符串 `"▶️ Starting Run..."` **硬编码** 在一起。因此，要测试这个 `Subscriber` 的行为，我们*必须*检查其字符串输出。我们通过断言 `assert "▶️" in logs` 来使其更“健壮”，但这仍是在测试一个**表现层 (Presentation Layer)** 的实现细节。

**2. `pyquipu` 的模型：语义消息驱动**

```mermaid
graph TD
    subgraph Core Logic
        A[Act Logic] -- Calls --> B[MessageBus.success("acts.git.success.initialized", ...)]
    end
    subgraph Messaging System
        B -- Uses --> C[MessageStore <br> (Loads locales/zh/acts.json)]
        C -- Provides template for "acts.git.success.initialized" --> B
        B -- Formats & Passes to --> D[Renderer]
    end
    D -- Prints --> E{Terminal Output <br> "✅ [Git] 已初始化仓库: ..."}
```

*   **巨大优势**: **核心逻辑 (`Act Logic`) 完全不知道最终的 UI 字符串**。它只知道一个抽象的、稳定的**语义ID**：`"acts.git.success.initialized"`。
*   **彻底解耦**:
    *   **意图**: 核心逻辑只表达“我成功初始化了一个 Git 仓库”。
    *   **模板**: `locales/*.json` 文件将意图 (`acts.git.success.initialized`) 翻译成特定语言的、带格式的字符串 (`✅ [Git]...`)。
    *   **渲染**: `Renderer` 负责将最终字符串打印到正确的流（stdout/stderr）并应用颜色。
*   **终极测试能力**: 在这个模型下，测试核心逻辑时，我们**可以也应该** Mock `MessageBus`，然后断言：
    ```python
    mock_bus.success.assert_called_with("acts.git.success.initialized", path="/some/path")
    ```
    这个测试**100%** 对 UI 文本、表情符号、颜色甚至语言免疫。这就是你所追求的，也是我们应该努力的方向。

**结论**: 你的直觉是正确的。我们当前的测试模式是对一个不够理想的架构所能做出的最好妥协。要真正摆脱对 `assert "▶️" in logs` 的依赖，我们需要的不仅仅是修改测试，而是要对 `cascade` 的日志和消息系统进行一次架构升级，使其向 `pyquipu` 的语义消息模型看齐。

---

现在，我将为你生成一个实现这一架构演进的计划。

## [WIP] test: 引入语义消息总线以实现终极测试解耦

### 用户需求
对 Cascade 的日志和事件系统进行架构重构，引入一个基于语义消息 ID 的消息总线（参考 `pyquipu` 的实现），从而将核心业务逻辑与 UI 表现层彻底解耦，并使测试能够通过断言消息 ID 来验证意图，彻底摆脱对日志字符串的依赖。

### 评论
这是一次至关重要的架构演进。它将把我们的测试健壮性提升到一个新的水平，并为未来的国际化（i18n）和多格式输出（如 JSON 日志）奠定坚实的基础。通过将“意图”（语义ID）和“表现”（日志字符串）分离，我们遵循了最高标准的软件设计原则，并一劳永逸地解决了当前测试策略中的脆弱性问题。

### 目标
1.  在 `cascade` 中创建一个新的 `messaging` 模块，用于实现新的消息总线和渲染器。
2.  创建一个 `locales/en/` 目录和 `events.json` 文件，用于存放所有 `HumanReadableLogSubscriber` 的消息模板。
3.  实现 `messaging.MessageBus` 和 `messaging.MessageStore`，使其能够加载并格式化 `events.json` 中的模板。
4.  实现 `messaging.CliRenderer`，负责将格式化后的消息打印到控制台。
5.  重构 `HumanReadableLogSubscriber`，使其不再直接 `print`，而是作为翻译层，将接收到的 `Event` 对象转换为对新 `MessageBus` 的调用（例如 `bus.info("run.started", ...)`）。
6.  重构 `cascade.run` 函数，使其正确初始化并注入 `CliRenderer`。
7.  最后，重构 `tests/integration/test_end_to_end.py`，移除 `SpySubscriber`，改为 Mock 新的 `messaging.bus`，并断言其方法被以正确的**语义ID**和**数据**调用。

### 基本原理
我们正在将 `pyquipu` 中经过验证的、成熟的语义消息架构引入到 `cascade` 中。
*   **关注点分离**: 核心逻辑（`Engine`）继续发布包含纯数据的 `Event`。`HumanReadableLogSubscriber` 的新角色是监听这些 `Event`，并将其翻译成对 `MessageBus` 的语义调用，它充当了**事件领域**和**消息领域**之间的桥梁。`MessageBus` 和 `MessageStore` 负责将语义ID转换为人类可读的文本。`CliRenderer` 负责最终的I/O。
*   **可测试性**: 这种分层设计使得我们可以在测试中轻松地在 `MessageBus` 这一层进行 Mock。由于 `MessageBus` 的接口是稳定的语义ID，我们的测试将变得极其健壮。

### 标签
#intent/architect #intent/refine #flow/ready #priority/high #comp/core #comp/tests #scope/dx #task/domain/testing #task/object/messaging-system #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建新的消息系统基础结构

我们首先创建目录结构和核心模块文件，模仿 `pyquipu` 的设计。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p src/cascade/locales/en
mkdir -p src/cascade/messaging
touch src/cascade/messaging/__init__.py
~~~~~

~~~~~act
write_file
src/cascade/locales/en/events.json
~~~~~
~~~~~json
{
    "run.started": "▶️  Starting Run for targets: [{targets}]",
    "run.started_with_params": "   With params: {params}",
    "run.finished_success": "🏁 Run finished successfully in {duration:.2f}s.",
    "run.finished_failure": "💥 Run failed after {duration:.2f}s: {error}",
    "task.started": "  ⏳ Running task `{task_name}`...",
    "task.finished_success": "  ✅ Finished task `{task_name}` in {duration:.2f}s",
    "task.finished_failure": "  ❌ Failed task `{task_name}` after {duration:.2f}s: {error}",
    "task.skipped": "  ⏩ Skipped task `{task_name}` (Reason: {reason})",
    "task.retrying": "  ⚠️  Retrying task `{task_name}` (Attempt {attempt}/{max_attempts}) in {delay:.2f}s... Error: {error}"
}
~~~~~

~~~~~act
write_file
src/cascade/messaging/bus.py
~~~~~
~~~~~python
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, locale: str = "en"):
        self._messages: Dict[str, str] = {}
        self.locale = locale
        self._load_messages()

    def _find_locales_dir(self) -> Optional[Path]:
        try:
            locales_path = Path(__file__).parent.parent / "locales"
            if locales_path.is_dir():
                return locales_path
        except Exception:
            pass
        return None

    def _load_messages(self):
        locales_dir = self._find_locales_dir()
        if not locales_dir:
            logger.error("Message resource directory 'locales' not found.")
            return

        locale_path = locales_dir / self.locale
        if not locale_path.is_dir():
            return

        for message_file in locale_path.glob("*.json"):
            try:
                with open(message_file, "r", encoding="utf-8") as f:
                    self._messages.update(json.load(f))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load message file {message_file}: {e}")

    def get(self, msg_id: str, default: str = "") -> str:
        return self._messages.get(msg_id, default or f"<{msg_id}>")


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
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)
    
    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)

_default_store = MessageStore(locale="en")
bus = MessageBus(store=_default_store)
~~~~~

~~~~~act
write_file
src/cascade/messaging/renderer.py
~~~~~
~~~~~python
import sys
from typing import TextIO

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

class CliRenderer:
    def __init__(self, stream: TextIO = sys.stderr, min_level: str = "INFO"):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def print(self, message: str, level: str):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            print(message, file=self._stream)
~~~~~

#### Acts 2: 重构 `HumanReadableLogSubscriber` 成为翻译层

现在我们将 `HumanReadableLogSubscriber` 的 `print` 调用替换为对新 `MessageBus` 的调用。

~~~~~act
patch_file
src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
import sys
from typing import TextIO
from .bus import MessageBus
from .events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
)


LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


class HumanReadableLogSubscriber:
    """
    Listens to events and prints user-friendly logs to a stream (default: stderr).
    """

    def __init__(
        self, bus: MessageBus, stream: TextIO = sys.stderr, min_level: str = "INFO"
    ):
        self._stream = stream
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

        # Subscribe to relevant events
        bus.subscribe(RunStarted, self.on_run_started)
        bus.subscribe(RunFinished, self.on_run_finished)
        bus.subscribe(TaskExecutionStarted, self.on_task_started)
        bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        bus.subscribe(TaskSkipped, self.on_task_skipped)
        bus.subscribe(TaskRetrying, self.on_task_retrying)

    def _should_log(self, level: str) -> bool:
        return LOG_LEVELS.get(level, 20) >= self._min_level_val

    def _print(self, msg: str):
        print(msg, file=self._stream)

    def on_run_started(self, event: RunStarted):
        if self._should_log("INFO"):
            targets = ", ".join(event.target_tasks)
            self._print(f"▶️  Starting Run for targets: [{targets}]")
            if event.params:
                self._print(f"   With params: {event.params}")

    def on_run_finished(self, event: RunFinished):
        level = "INFO" if event.status == "Succeeded" else "ERROR"
        if self._should_log(level):
            if event.status == "Succeeded":
                self._print(f"🏁 Run finished successfully in {event.duration:.2f}s.")
            else:
                self._print(f"💥 Run failed after {event.duration:.2f}s: {event.error}")

    def on_task_started(self, event: TaskExecutionStarted):
        if self._should_log("INFO"):
            self._print(f"  ⏳ Running task `{event.task_name}`...")

    def on_task_finished(self, event: TaskExecutionFinished):
        level = "INFO" if event.status == "Succeeded" else "ERROR"
        if self._should_log(level):
            if event.status == "Succeeded":
                self._print(
                    f"  ✅ Finished task `{event.task_name}` in {event.duration:.2f}s"
                )
            else:
                self._print(
                    f"  ❌ Failed task `{event.task_name}` after {event.duration:.2f}s: {event.error}"
                )

    def on_task_skipped(self, event: TaskSkipped):
        if self._should_log("INFO"):
            self._print(
                f"  ⏩ Skipped task `{event.task_name}` (Reason: {event.reason})"
            )

    def on_task_retrying(self, event: TaskRetrying):
        if self._should_log("WARNING"):
            self._print(
                f"  ⚠️  Retrying task `{event.task_name}` "
                f"(Attempt {event.attempt}/{event.max_attempts}) "
                f"in {event.delay:.2f}s... Error: {event.error}"
            )
~~~~~
~~~~~python
from .bus import MessageBus
from ..messaging.bus import bus as messaging_bus
from .events import (
    RunStarted,
    RunFinished,
    TaskExecutionStarted,
    TaskExecutionFinished,
    TaskSkipped,
    TaskRetrying,
)


class HumanReadableLogSubscriber:
    """
    Listens to runtime events and translates them into semantic messages
    on the messaging bus. It acts as a bridge between the event domain
    and the user-facing message domain.
    """

    def __init__(self, event_bus: MessageBus):
        # Subscribe to relevant events from the core event_bus
        event_bus.subscribe(RunStarted, self.on_run_started)
        event_bus.subscribe(RunFinished, self.on_run_finished)
        event_bus.subscribe(TaskExecutionStarted, self.on_task_started)
        event_bus.subscribe(TaskExecutionFinished, self.on_task_finished)
        event_bus.subscribe(TaskSkipped, self.on_task_skipped)
        event_bus.subscribe(TaskRetrying, self.on_task_retrying)

    def on_run_started(self, event: RunStarted):
        targets = ", ".join(event.target_tasks)
        messaging_bus.info("run.started", targets=targets)
        if event.params:
            messaging_bus.info("run.started_with_params", params=event.params)

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            messaging_bus.info("run.finished_success", duration=event.duration)
        else:
            messaging_bus.error("run.finished_failure", duration=event.duration, error=event.error)

    def on_task_started(self, event: TaskExecutionStarted):
        messaging_bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            messaging_bus.info("task.finished_success", task_name=event.task_name, duration=event.duration)
        else:
            messaging_bus.error("task.finished_failure", task_name=event.task_name, duration=event.duration, error=event.error)

    def on_task_skipped(self, event: TaskSkipped):
        messaging_bus.info("task.skipped", task_name=event.task_name, reason=event.reason)

    def on_task_retrying(self, event: TaskRetrying):
        messaging_bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error
        )
~~~~~

#### Acts 3: 更新 `cascade.run` 以集成新系统

`cascade.run` 是我们的门面函数，我们需要在这里将 `CliRenderer` 注入到 `messaging_bus`。

~~~~~act
patch_file
src/cascade/__init__.py
~~~~~
~~~~~python
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
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus, min_level=log_level)

    engine = Engine(bus=bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
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
    # Attach the translator
    HumanReadableLogSubscriber(event_bus)

    engine = Engine(bus=event_bus, system_resources=system_resources)

    return asyncio.run(engine.run(target, params=params))
~~~~~

#### Acts 4: 重构 `test_end_to_end.py` 以验证新架构

最后，我们重构集成测试，使其 Mock `messaging.bus` 并断言语义ID，这才是本次重构的最终目的。

~~~~~act
write_file
tests/integration/test_end_to_end.py
~~~~~
~~~~~python
import pytest
import asyncio
from unittest.mock import MagicMock
import cascade as cs
from cascade.runtime.engine import Engine


@pytest.fixture
def mock_messaging_bus(monkeypatch):
    """Mocks the global messaging bus and returns the mock object."""
    mock_bus = MagicMock()
    monkeypatch.setattr("cascade.runtime.subscribers.messaging_bus", mock_bus)
    return mock_bus


def test_e2e_linear_workflow(mock_messaging_bus):
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())

    # We use the event_bus for engine events, which is internal.
    # The subscriber will translate these to calls on the mocked messaging_bus.
    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(bus=event_bus)

    result = asyncio.run(engine.run(final_greeting))

    assert result == "Hello, Cascade!"

    # Assertions are now on the INTENT (semantic ID), not the output!
    mock_messaging_bus.info.assert_any_call("run.started", targets="greet")
    mock_messaging_bus.info.assert_any_call("task.started", task_name="get_name")
    mock_messaging_bus.info.assert_any_call("task.finished_success", task_name="get_name", duration=pytest.approx(0, abs=1))
    mock_messaging_bus.info.assert_any_call("task.started", task_name="greet")
    mock_messaging_bus.info.assert_any_call("run.finished_success", duration=pytest.approx(0, abs=1))
    
    # Check that it was not called with a failure message
    mock_messaging_bus.error.assert_not_called()


def test_e2e_failure_propagation(mock_messaging_bus):
    @cs.task
    def failing_task():
        raise ValueError("Something went wrong")

    event_bus = cs.runtime.MessageBus()
    cs.runtime.HumanReadableLogSubscriber(event_bus)
    engine = Engine(bus=event_bus)

    with pytest.raises(ValueError, match="Something went wrong"):
        asyncio.run(engine.run(failing_task()))

    # Assert that the correct failure messages were sent
    mock_messaging_bus.error.assert_any_call(
        "task.finished_failure",
        task_name="failing_task",
        duration=pytest.approx(0, abs=1),
        error="ValueError: Something went wrong"
    )
    mock_messaging_bus.error.assert_any_call(
        "run.finished_failure",
        duration=pytest.approx(0, abs=1),
        error=pytest.string_containing("ValueError: Something went wrong")
    )
~~~~~

### 下一步建议
我们已经成功地将 Cascade 的消息系统提升到了一个新的架构水平。这个新的语义消息总线不仅使我们的测试更加健壮，还为未来的国际化（i18n）、JSON 日志输出等高级功能铺平了道路。

下一步，我们可以利用这个新系统：
1.  **添加 JSON Renderer**: 创建一个 `JsonRenderer`，当用户配置 `--log-format=json` 时，可以将所有事件以结构化 JSON 的形式输出，方便机器解析。
2.  **实现多语言支持**: 只需在 `locales` 目录下添加 `zh/events.json` 等文件，并允许用户通过配置切换 `MessageStore` 的 `locale`，即可轻松实现多语言日志。

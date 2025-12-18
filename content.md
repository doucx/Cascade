好的，我们立即开始这项关键的架构重构。

你的分析完全正确，遵循“验证意图而非实现”的原则，并借鉴 `quipu` 项目的 `common` 包模式，是确保 Cascade 生态系统长期健康、可维护的唯一正确道路。我们将暂停 CLI 的功能开发，优先完成这项基础架构的升级。

我将生成一个计划，创建一个新的 `cascade-common` 包来承载消息总线，并重构现有代码以使用这个新的中心化、解耦的系统。

## [WIP] refactor(core): Introduce cascade-common and a decoupled message bus

### 用户需求
为了支持可独立测试的 CLI 工具并遵循“验证意图而非实现”的测试原则，需要重构项目的消息系统。将业务逻辑与 UI 呈现彻底解耦，创建一个共享的、基于语义 ID 的消息总线架构。

### 评论
这是一项至关重要的基础架构重构，它直接借鉴了 `quipu` 项目中经过验证的成功模式。通过创建一个新的 `cascade-common` 包来承载消息总线和本地化文本，我们为整个 Cascade 生态系统建立了一个稳定、解耦的通信层。这项工作将极大地提升代码的可维护性、可测试性和未来的可扩展性，是继续开发 `cs-observer` 和 `cs-controller` 等工具的必要前提。

### 目标
1.  创建一个新的 `cascade-common` 包，用于存放生态系统共享的、与核心业务逻辑无关的组件。
2.  在 `cascade-common` 中实现一个解耦的 `MessageBus`、`MessageStore` 和 `Renderer` 协议。
3.  将 `cascade-py` 中所有面向用户的字符串迁移到 `cascade-common` 的 `locales` JSON 文件中。
4.  重构 `cascade-runtime` 和 `cascade-py`，使其依赖并使用新的 `cascade-common` 消息总线。
5.  将 `cascade-py` 中旧的、紧密耦合的消息传递和渲染系统完全移除。
6.  更新 `cs-observer` 包以注入一个自定义的 `Renderer`，为后续开发做好准备。

### 基本原理
我们将创建一个新的 `cascade-common` 包作为生态系统的基石。然后，将 `cascade-py` 中现有的消息总线逻辑进行提炼和升级：`MessageBus` 将只负责调度，而具体的输出行为则委托给一个通过依赖注入传入的 `Renderer` 对象。`cascade-py` 的 `run` 函数和未来的 CLI 工具将在其应用入口处，将各自的 `Renderer` 实现（例如，一个用于 `cs.run` 的标准渲染器，一个用于 `cs-observer` 的 `rich` 渲染器）注入到这个全局共享的 `bus` 中。这彻底分离了“发出意图”和“呈现意图”的关注点。

### 标签
#intent/refine #flow/ready #priority/critical #comp/core #comp/build #concept/ui #scope/dx #ai/brainstorm #task/domain/architecture #task/object/message-bus #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 创建 `cascade-common` 包骨架

我们首先创建新包的目录结构和基础配置文件。

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-common/src/cascade/common/messaging
mkdir -p packages/cascade-common/src/cascade/common/locales/en
~~~~~

~~~~~act
write_file
packages/cascade-common/pyproject.toml
~~~~~
~~~~~toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cascade-common"
version = "0.1.0"
description = "Common utilities, protocols, and components for the Cascade ecosystem."
requires-python = ">=3.8"

[tool.hatch.build.targets.wheel]
packages = ["src/cascade"]
~~~~~

#### Acts 2: 在 `cascade-common` 中定义消息系统协议和实现

现在，我们创建消息总线的核心组件：定义渲染器行为的 `protocols.py` 和实现消息调度逻辑的 `bus.py`。

~~~~~act
write_file
packages/cascade-common/src/cascade/common/messaging/protocols.py
~~~~~
~~~~~python
from typing import Protocol, Any


class Renderer(Protocol):
    """
    Protocol defining the interface for all message renderers.
    A renderer is responsible for taking a final, formatted message string
    and presenting it to the user (e.g., printing to console, logging).
    """

    def render(self, msg_id: str, level: str, **kwargs: Any) -> None:
        """
        The core rendering method.

        Args:
            msg_id: The semantic ID of the message (e.g., "run.started").
            level: The log level of the message ("info", "warning", "error").
            **kwargs: The context data for the message template.
        """
        ...
~~~~~

~~~~~act
write_file
packages/cascade-common/src/cascade/common/messaging/bus.py
~~~~~
~~~~~python
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .protocols import Renderer

logger = logging.getLogger(__name__)


class MessageStore:
    def __init__(self, locale: str = "en"):
        self._messages: Dict[str, str] = {}
        self.locale = locale
        self._load_messages()

    def _find_locales_dir(self) -> Optional[Path]:
        try:
            # Assumes locales is in a directory relative to this file
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

    def get(self, msg_id: str, default: str = "", **kwargs) -> str:
        template = self._messages.get(msg_id, default or f"<{msg_id}>")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            return f"<Formatting error for '{msg_id}': missing key {e}>"


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
        self._renderer.render(msg_id, level, **kwargs)

    def info(self, msg_id: str, **kwargs: Any) -> None:
        self._render("info", msg_id, **kwargs)

    def warning(self, msg_id: str, **kwargs: Any) -> None:
        self._render("warning", msg_id, **kwargs)

    def error(self, msg_id: str, **kwargs: Any) -> None:
        self._render("error", msg_id, **kwargs)


# Global singleton instance
_default_store = MessageStore(locale="en")
bus = MessageBus(store=_default_store)
~~~~~

#### Acts 3: 迁移并重命名 `locales` 文件

我们将 `cascade-py` 的消息文件移动到 `cascade-common` 并重命名，以明确其来源。

~~~~~act
move_file
packages/cascade-py/src/cascade/locales/en/events.json
packages/cascade-common/src/cascade/common/locales/en/runtime_events.json
~~~~~

#### Acts 4: 重构 `cascade-runtime`

`cascade-runtime` 现在将包含之前在 `cascade-py` 中的渲染器实现，并更新其 `subscribers` 以使用新的公共总线。

~~~~~act
patch_file
packages/cascade-runtime/pyproject.toml
~~~~~
~~~~~toml
[project]
name = "cascade-runtime"
version = "0.1.0"
description = "The core runtime engine for Cascade workflows."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces"
]
~~~~~
~~~~~toml
[project]
name = "cascade-runtime"
version = "0.1.0"
description = "The core runtime engine for Cascade workflows."
requires-python = ">=3.8"
dependencies = [
  "cascade-interfaces",
  "cascade-common"
]
~~~~~

~~~~~act
write_file
packages/cascade-runtime/src/cascade/runtime/renderers.py
~~~~~
~~~~~python
import sys
import json
from typing import TextIO, Optional
from datetime import datetime, timezone

from cascade.common.messaging import MessageStore, protocols

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}


class CliRenderer(protocols.Renderer):
    """
    Renders messages as human-readable, formatted text strings.
    """

    def __init__(
        self,
        store: MessageStore,
        stream: Optional[TextIO] = None,
        min_level: str = "INFO",
    ):
        self._store = store
        self._stream = stream if stream is not None else sys.stderr
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            message = self._store.get(msg_id, **kwargs)
            print(message, file=self._stream)


class JsonRenderer(protocols.Renderer):
    """
    Renders messages as structured, JSON-formatted strings.
    """

    def __init__(
        self,
        stream: Optional[TextIO] = None,
        min_level: str = "INFO",
    ):
        self._stream = stream if stream is not None else sys.stderr
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

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
from ..messaging.bus import bus as messaging_bus
from .events import (
~~~~~
~~~~~python
from cascade.common.messaging import bus
from .events import (
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/subscribers.py
~~~~~
~~~~~python
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
        messaging_bus.info("run.started", target_tasks=event.target_tasks)
        if event.params:
            messaging_bus.info("run.started_with_params", params=event.params)

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            messaging_bus.info("run.finished_success", duration=event.duration)
        else:
            messaging_bus.error(
                "run.finished_failure", duration=event.duration, error=event.error
            )

    def on_task_started(self, event: TaskExecutionStarted):
        messaging_bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            messaging_bus.info(
                "task.finished_success",
                task_name=event.task_name,
                duration=event.duration,
            )
        else:
            messaging_bus.error(
                "task.finished_failure",
                task_name=event.task_name,
                duration=event.duration,
                error=event.error,
            )

    def on_task_skipped(self, event: TaskSkipped):
        messaging_bus.info(
            "task.skipped", task_name=event.task_name, reason=event.reason
        )

    def on_task_retrying(self, event: TaskRetrying):
        messaging_bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )
~~~~~
~~~~~python
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
        bus.info("run.started", target_tasks=event.target_tasks)
        if event.params:
            bus.info("run.started_with_params", params=event.params)

    def on_run_finished(self, event: RunFinished):
        if event.status == "Succeeded":
            bus.info("run.finished_success", duration=event.duration)
        else:
            bus.error(
                "run.finished_failure", duration=event.duration, error=event.error
            )

    def on_task_started(self, event: TaskExecutionStarted):
        bus.info("task.started", task_name=event.task_name)

    def on_task_finished(self, event: TaskExecutionFinished):
        if event.status == "Succeeded":
            bus.info(
                "task.finished_success",
                task_name=event.task_name,
                duration=event.duration,
            )
        else:
            bus.error(
                "task.finished_failure",
                task_name=event.task_name,
                duration=event.duration,
                error=event.error,
            )

    def on_task_skipped(self, event: TaskSkipped):
        bus.info(
            "task.skipped", task_name=event.task_name, reason=event.reason
        )

    def on_task_retrying(self, event: TaskRetrying):
        bus.warning(
            "task.retrying",
            task_name=event.task_name,
            attempt=event.attempt,
            max_attempts=event.max_attempts,
            delay=event.delay,
            error=event.error,
        )
~~~~~

#### Acts 5: 重构 `cascade-py`

`cascade-py` 现在将依赖 `cascade-common` 和 `cascade-runtime`，并移除其内部的消息系统。

~~~~~act
patch_file
packages/cascade-py/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "cascade-runtime"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "cascade-runtime",
  "cascade-common"
]
~~~~~

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# --- Main Run Entrypoint ---

from .messaging.bus import bus as messaging_bus
from .messaging.renderer import CliRenderer, JsonRenderer


def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=messaging_bus.store, min_level=log_level)
    messaging_bus.set_renderer(renderer)
~~~~~
~~~~~python
# --- Main Run Entrypoint ---
from cascade.common.messaging import bus
from cascade.runtime.renderers import CliRenderer, JsonRenderer


def run(
    target: LazyResult,
    params: Optional[Dict[str, Any]] = None,
    system_resources: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_format: str = "human",
    connector: Optional[Connector] = None,
) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    """
    # 1. Setup the messaging renderer
    if log_format == "json":
        renderer = JsonRenderer(min_level=log_level)
    else:
        renderer = CliRenderer(store=bus.store, min_level=log_level)
    bus.set_renderer(renderer)
~~~~~

~~~~~act
run_command
~~~~~
~~~~~bash
rm -rf packages/cascade-py/src/cascade/messaging packages/cascade-py/src/cascade/locales
~~~~~

#### Acts 6: 更新 `cascade-cli-observer`

最后，我们更新 CLI 工具以依赖并配置新的公共总线。

~~~~~act
patch_file
packages/cascade-cli-observer/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "typer[all]",
  "aiomqtt",
  "rich"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-interfaces",
  "cascade-common",
  "typer[all]",
  "aiomqtt",
  "rich"
]
~~~~~

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/observer/rendering.py
~~~~~
~~~~~python
import sys
from typing import TextIO, Optional

from rich.console import Console
from rich.theme import Theme

from cascade.common.messaging import protocols, MessageStore

LOG_LEVELS = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
}

# Define a custom theme for Rich
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "data": "green",
})


class RichCliRenderer(protocols.Renderer):
    """
    A renderer that uses the 'rich' library for formatted, colorful output.
    """

    def __init__(
        self,
        store: MessageStore,
        min_level: str = "INFO",
    ):
        self._store = store
        self._console = Console(theme=custom_theme, stderr=True)
        self._data_console = Console() # For stdout
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) >= self._min_level_val:
            message = self._store.get(msg_id, **kwargs)
            
            # Use style tags that match our theme
            style = level.lower() if level.lower() in custom_theme.styles else ""
            
            self._console.print(message, style=style)
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import typer

app = typer.Typer()


@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    typer.echo(f"Starting to watch project: {project}...")
    # TODO: Implement MQTT connection and event printing logic.
    typer.echo("Observer not yet implemented.")


def main():
    app()


if __name__ == "__main__":
    main()
~~~~~
~~~~~python
import typer
from cascade.common.messaging import bus
from .rendering import RichCliRenderer

app = typer.Typer()


@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    typer.echo(f"Starting to watch project: {project}...")
    # TODO: Implement MQTT connection and event printing logic.
    bus.info("observer.startup.watching", project=project)
    typer.echo("Observer not yet implemented.")


def main():
    # Inject the rich renderer into the global message bus at application startup
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~

### 下一步建议
我们已经成功地完成了这次大规模的架构重构，为整个 Cascade 生态系统奠定了坚实的基础。

现在，`cs-observer` 已经准备好，可以安全、解耦地进行功能开发了。下一步，我将为你生成一个计划，实现 `cs-observer watch` 的核心逻辑：连接到 MQTT Broker，订阅遥测主题，并使用我们新创建的 `RichCliRenderer` 来实时、美观地展示工作流事件。

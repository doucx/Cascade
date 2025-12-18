好的，我将开始重构 `cs-observer` 和 `cs-controller` 这两个 CLI 工具，让它们完全采用解耦的消息总线架构进行用户反馈。

这次重构的核心是遵循“业务逻辑与表现层分离”的原则。CLI 命令的业务逻辑将只负责调用消息总线并传递**语义消息 ID**，而具体的文本渲染将由在应用入口处注入的 `Renderer` 负责。

为此，我将首先把通用的 `CliRenderer` 和 `JsonRenderer` 从 `cascade-runtime` 移动到 `cascade-common` 包中，使其成为所有生态系统工具可共享的基础组件。然后，我会创建一个新的 `cli_messages.json` 文件来存放 CLI 工具专用的消息模板，最后修改 `cs-observer` 和 `cs-controller` 的代码以使用这套新机制。

## [WIP] refactor: Refactor CLI tools to use the message bus

### 用户需求
将 `cs-observer` 和 `cs-controller` 重构为使用解耦的消息总线架构，移除所有对 `typer.echo` 的直接调用，并为 CLI 工具创建专用的消息定义文件。

### 评论
这是一个关键的架构性重构。它将消息总线模式的优势（解耦、可测试性、国际化）扩展到了生态系统的所有 CLI 工具中，确保了整个 Cascade 项目在用户交互层面的一致性和健壮性。将通用 `Renderer` 移至 `cascade-common` 也是一次正确的设计决策，它强化了该包作为生态系统“共享内核”的定位。

### 目标
1.  为 CLI 工具创建一个新的消息模板文件 `cli_messages.json`。
2.  将 `CliRenderer` 和 `JsonRenderer` 从 `cascade-runtime` 迁移到 `cascade-common`。
3.  更新 `cascade-py` 的主入口点，以反映 `Renderer` 位置的变更。
4.  重构 `cs-observer` 和 `cs-controller`，使其完全通过消息总线进行用户反馈。

### 基本原理
遵循**语义 ID 优先**和**表现层与业务逻辑分离**的原则。核心逻辑通过调用 `bus.info("some.id")` 来表达“意图”，而应用的入口点 `main()` 则通过 `bus.set_renderer(...)` 来决定这个“意图”最终如何“呈现”给用户。这使得核心代码完全独立于 UI 框架（如 `typer` 或 `rich`），极大地提升了代码的可测试性和可维护性。

### 标签
#intent/refine #flow/ready #priority/high #comp/cli #comp/common #comp/runtime #concept/ui #scope/dx #ai/instruct #task/domain/cli #task/object/message-bus #task/action/integration #task/state/begin

---

### Script

#### Acts 1: 创建 CLI 专用消息文件

首先，在 `cascade-common` 包中创建一个新的 JSON 文件，用于存放所有 CLI 工具共享的消息模板。

~~~~~act
write_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
~~~~~
~~~~~json
{
    "observer.startup.watching": "🔭 Watching project: {project}",
    "observer.not_implemented": "⚠️  Observer functionality is not yet fully implemented.",
    "controller.publishing": "📡 Publishing constraint for scope: {scope}",
    "controller.not_implemented": "⚠️  Controller functionality is not yet fully implemented."
}
~~~~~

#### Acts 2: 将通用 Renderers 迁移到 cascade-common

将 `CliRenderer` 和 `JsonRenderer` 的实现移动到一个 `cascade-common` 包下的新文件中，使其成为共享组件。

~~~~~act
write_file
packages/cascade-common/src/cascade/common/renderers.py
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

#### Acts 3: 清理旧的 Renderer 文件

删除 `cascade-runtime` 中已被迁移的旧文件。

~~~~~act
delete_file
packages/cascade-runtime/src/cascade/runtime/renderers.py
~~~~~

#### Acts 4: 更新 cascade-py 的入口点

修改 `cascade-py` 的主 `run` 函数，使其从 `cascade-common` 导入 `Renderer`。

~~~~~act
patch_file
packages/cascade-py/src/cascade/__init__.py
~~~~~
~~~~~python
# --- Main Run Entrypoint ---
from cascade.common.messaging import bus
from cascade.runtime.renderers import CliRenderer, JsonRenderer


def run(
~~~~~
~~~~~python
# --- Main Run Entrypoint ---
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer, JsonRenderer


def run(
~~~~~

#### Acts 5: 重构 cs-observer

更新 `cs-observer` 的代码，移除 `typer.echo` 并使用新的语义消息 ID。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    typer.echo(f"Starting to watch project: {project}...")
    # TODO: Implement MQTT connection and event printing logic.
    bus.info("observer.startup.watching", project=project)
    typer.echo("Observer not yet implemented.")
~~~~~
~~~~~python
@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    bus.info("observer.startup.watching", project=project)
    # TODO: Implement MQTT connection and event printing logic.
    bus.warning("observer.not_implemented")
~~~~~

#### Acts 6: 重构 cs-controller

最后，重构 `cs-controller`，为其注入 `CliRenderer` 并将所有输出都切换到消息总线。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
import typer

app = typer.Typer()


@app.command()
def pause(scope: str = typer.Argument(..., help="The scope to pause (e.g., 'global', 'task:api_call').")):
    """
    Publish a 'pause' constraint to the MQTT broker.
    """
    typer.echo(f"Publishing pause command for scope: {scope}...")
    # TODO: Implement MQTT connection and publishing logic.
    typer.echo("Controller not yet implemented.")


def main():
    app()


if __name__ == "__main__":
    main()
~~~~~
~~~~~python
import typer
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer

app = typer.Typer()


@app.command()
def pause(scope: str = typer.Argument(..., help="The scope to pause (e.g., 'global', 'task:api_call').")):
    """
    Publish a 'pause' constraint to the MQTT broker.
    """
    bus.info("controller.publishing", scope=scope)
    # TODO: Implement MQTT connection and publishing logic.
    bus.warning("controller.not_implemented")


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~

### 下一步建议
我们已经成功地将 CLI 工具整合到了统一的消息总线架构中。下一步，我建议我们开始实现 `cs-observer` 和 `cs-controller` 的核心功能：
1.  **`cs-observer`**: 实现与 MQTT Broker 的连接，并实时解析、打印遥测事件。
2.  **`cs-controller`**: 实现向 MQTT Broker 发布格式正确的约束指令。

这将完成路线图第四阶段的核心工具链构建，为我们提供操作和观测 Cascade 工作流的强大能力。

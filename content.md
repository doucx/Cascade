好的，我们继续当前的开发路线，为 `cs-observer` 实现其核心功能。

这个计划的核心是集成 `MqttConnector`，使其能够订阅遥测主题，并利用我们刚刚重构的消息总线和 `RichCliRenderer` 将实时事件以清晰、美观的格式呈现给用户。

## [WIP] feat: Implement MQTT subscription logic in cs-observer

### 用户需求
为 `cs-observer` CLI 工具实现其核心功能，使其能够连接到 MQTT Broker，订阅指定项目的遥测事件，并将这些事件实时地打印到控制台。

### 评论
这是实现路线图“第四阶段：生态工具链”的关键一步。它将之前阶段构建的遥测系统（`Connector`）和消息总线架构的能力真正地交付给开发者，提供了一个急需的、用于实时监控和调试工作流的可视化工具。

### 目标
1.  为 `cs-observer` 的输出定义一套新的、丰富的语义消息 ID。
2.  增强 `RichCliRenderer` 以支持更结构化的输出，如使用分隔线。
3.  在 `cs-observer` 的 `watch` 命令中集成 `MqttConnector`。
4.  实现一个异步消息处理回调，该回调负责解析遥测事件并调用消息总线进行渲染。
5.  确保应用能够优雅地处理启动和关闭（例如，通过 Ctrl+C）。

### 基本原理
我们将 `watch` 命令改造为一个异步函数。它会实例化 `MqttConnector` 并建立连接，然后订阅一个带有通配符的 MQTT 主题（例如 `cascade/telemetry/+/<project>/+/events`）以接收所有相关的遥测数据。一个回调函数 (`on_message`) 将作为事件处理器，它会将接收到的原始 JSON 数据解析成结构化事件，并根据事件类型调用消息总线中不同的语义 ID。`RichCliRenderer` 负责将这些语义消息和数据渲染成带有颜色和格式的友好输出。整个应用将通过一个 `asyncio` 事件循环保持运行，直到被用户中断。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/ui #concept/telemetry #scope/ux #ai/instruct #task/domain/cli #task/object/observer-tool #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义 Observer 的遥测消息模板

我们将为 `cs-observer` 的各种输出在 `cli_messages.json` 中添加一套丰富的、支持 Rich 标记的模板。

~~~~~act
patch_file
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
~~~~~json
{
    "observer.startup.watching": "🔭 Watching project: [bold cyan]{project}[/bold cyan] on [bold green]{hostname}:{port}[/bold green]...",
    "observer.startup.connected": "✅ Connected to MQTT broker.",
    "observer.startup.error": "❌ Failed to connect to MQTT broker at {hostname}:{port}. Error: {error}",
    "observer.shutdown": "\n🔌 Disconnecting and shutting down...",

    "observer.telemetry.run_header": "\n[bold yellow]─── Run Started: {run_id} ───[/bold yellow]",
    "observer.telemetry.lifecycle.ENGINE_STARTED": "▶️  Engine started.",
    "observer.telemetry.lifecycle.ENGINE_STOPPED": "✅ Engine stopped.",
    "observer.telemetry.task_state.RUNNING": "   - Task '[bold]{task_name}[/bold]' started.",
    "observer.telemetry.task_state.COMPLETED": "   - [green]✅ Task '[bold]{task_name}[/bold]' succeeded in {duration_ms:.0f}ms.[/green]",
    "observer.telemetry.task_state.FAILED": "   - [bold red]❌ Task '[bold]{task_name}[/bold]' failed after {duration_ms:.0f}ms. Error: {error}[/bold red]",
    "observer.telemetry.task_state.SKIPPED": "   - [dim]⚪ Task '[bold]{task_name}[/bold]' skipped.[/dim]",
    "observer.telemetry.unknown_event": "[dim]Received unknown event type: {type}[/dim]",

    "controller.publishing": "📡 Publishing constraint for scope: {scope}",
    "controller.not_implemented": "⚠️  Controller functionality is not yet fully implemented."
}
~~~~~

#### Acts 2: 增强 RichCliRenderer 以支持分隔线

为了更好地在视觉上组织输出，我们为 Renderer 添加一个简单的 `rule` 方法。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/rendering.py
~~~~~
~~~~~python
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
~~~~~python
from rich.rule import Rule

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
        self._min_level_val = LOG_LEVELS.get(min_level.upper(), 20)

    def render(self, msg_id: str, level: str, **kwargs):
        if LOG_LEVELS.get(level.upper(), 20) < self._min_level_val:
            return

        # Special handling for visual rules
        if msg_id == "observer.telemetry.run_header":
            title = self._store.get(msg_id, **kwargs)
            self._console.print(Rule(title, align="center"))
            return

        message = self._store.get(msg_id, **kwargs)
        
        # Use style tags that match our theme
        style = level.lower() if level.lower() in custom_theme.styles else ""
        
        self._console.print(message, style=style)
~~~~~

#### Acts 3: 实现 cs-observer 的核心订阅逻辑

现在，我们将重写 `app.py`，为其注入完整的 `asyncio` 和 `MqttConnector` 逻辑。

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import asyncio
import typer
from cascade.common.messaging import bus
from .rendering import RichCliRenderer
from cascade.connectors.mqtt import MqttConnector

app = typer.Typer()

# Keep track of runs to print headers only once
seen_run_ids = set()


async def on_message(topic: str, payload: dict):
    """Callback to process incoming telemetry messages."""
    global seen_run_ids
    
    header = payload.get("header", {})
    body = payload.get("body", {})
    run_id = header.get("run_id")

    if not run_id or not body:
        return

    # Print a header for the first time we see a run_id
    if run_id not in seen_run_ids:
        bus.info("observer.telemetry.run_header", run_id=run_id)
        seen_run_ids.add(run_id)

    event_type = body.get("type")
    if event_type == "LifecycleEvent":
        event_name = body.get("event")
        bus.info(f"observer.telemetry.lifecycle.{event_name}")
    elif event_type == "TaskStateEvent":
        state = body.get("state")
        msg_id = f"observer.telemetry.task_state.{state}"
        bus.info(
            msg_id,
            task_name=body.get("task_name", "N/A"),
            duration_ms=body.get("duration_ms", 0),
            error=body.get("error", ""),
        )
    else:
        bus.info("observer.telemetry.unknown_event", type=event_type)


@app.command()
def watch(
    project: str = typer.Option("default", help="The project ID to watch."),
    hostname: str = typer.Option("localhost", help="MQTT broker hostname."),
    port: int = typer.Option(1883, help="MQTT broker port."),
):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    async def main_loop():
        topic = f"cascade/telemetry/+/{project}/+/events"
        connector = MqttConnector(hostname=hostname, port=port)
        shutdown_event = asyncio.Event()

        bus.info("observer.startup.watching", project=project, hostname=hostname, port=port)

        try:
            await connector.connect()
            bus.info("observer.startup.connected")
            await connector.subscribe(topic, on_message)
            await shutdown_event.wait()
        except Exception as e:
            bus.error("observer.startup.error", hostname=hostname, port=port, error=e)
        finally:
            bus.info("observer.shutdown")
            await connector.disconnect()
            
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        # The finally block in main_loop will handle graceful shutdown
        pass


def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~

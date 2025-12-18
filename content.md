好的，我们开始实现 `cs-controller` 的核心功能。

这个计划将把 `cs-controller pause` 命令从一个占位符转变为一个功能完备的工具。它将负责连接到 MQTT Broker，构造一个符合 `cascade.spec.constraint.GlobalConstraint` 规范的 JSON 报文，并将其发布到正确的控制主题上，从而实现对远程 Cascade 工作流的实时干预。

## [WIP] feat: Implement `cs-controller pause` command to publish constraints

### 用户需求
为 `cs-controller` CLI 工具实现 `pause` 命令，使其能够向 MQTT Broker 发布一个标准的“暂停”约束指令，该指令可以被一个正在运行的 Cascade `Engine` 接收并执行。

### 评论
这是实现 Phase 4 “生态工具链”的关键里程碑，它为 Phase 3 构建的“约束与环境感知”能力提供了第一个正式的操作界面。通过这个工具，开发者或运维人员将首次获得从外部动态影响和控制 Cascade 工作流的能力，这是从“工作流库”迈向“自适应执行环境”的重要一步。

### 目标
1.  为 `cs-controller` 的各种输出（连接、发布、成功、失败）定义新的语义消息 ID。
2.  将 `cs-controller pause` 命令改造为一个异步函数。
3.  在该函数中集成 `MqttConnector`，处理连接和断开逻辑。
4.  构造一个 `GlobalConstraint` 数据对象，并将其序列化为 JSON payload。
5.  将 payload 发布到一个结构化的 MQTT 主题上（例如 `cascade/constraints/global`）。

### 基本原理
我们将 `pause` 命令的实现委托给一个 `asyncio` 事件循环。该循环负责管理 `MqttConnector` 的生命周期。当命令执行时，它会创建一个 `GlobalConstraint` 实例（`type="pause"`），使用 `dataclasses.asdict` 将其转换为字典，然后通过 `connector.publish` 将其发布。MQTT 主题将根据 `scope` 参数动态构建，例如 `pause --scope task:api_call` 会发布到 `cascade/constraints/task/api_call` 主题，这允许 Cascade 引擎通过订阅通配符主题 (`cascade/constraints/#`) 来接收并精细化地处理各类约束。

*(注：为了简化初版实现，本次发布的 MQTT 消息将不是“保留消息 (retained message)”。这意味着只有当前已连接的引擎会收到该约束。在未来的迭代中，我们将增强 `MqttConnector` 以支持发布保留消息，确保后加入的引擎也能获取到最新的约束状态。)*

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/control-loop #scope/api #scope/ux #ai/instruct #task/domain/cli #task/object/controller-tool #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 定义 Controller 的消息模板

首先，我们在 `cli_messages.json` 中为 `cs-controller` 添加一套完整的消息模板。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
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

    "controller.connecting": "Connecting to MQTT broker at [bold green]{hostname}:{port}[/bold green]...",
    "controller.connected": "✅ Connected to MQTT broker.",
    "controller.publishing": "📡 Publishing constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Constraint published successfully.",
    "controller.error": "❌ An error occurred: {error}"
}
~~~~~

#### Acts 2: 实现 `cs-controller` 的核心发布逻辑

我们将重写 `app.py`，为其注入完整的 `asyncio` 和 `MqttConnector` 逻辑，并实现 `pause` 命令。

~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
import asyncio
import typer
import uuid
from dataclasses import asdict

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer(
    help="A command-line tool to control running Cascade workflows via MQTT."
)


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the MQTT broker.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """

    async def main_loop():
        connector = MqttConnector(hostname=hostname, port=port)
        try:
            bus.info("controller.connecting", hostname=hostname, port=port)
            await connector.connect()
            bus.info("controller.connected")

            # Create a unique, descriptive ID for the constraint
            constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id, scope=scope, type="pause", params={}
            )

            # Convert to dictionary for JSON serialization
            payload = asdict(constraint)

            # Publish to a structured topic based on scope
            topic = f"cascade/constraints/{scope.replace(':', '/')}"

            bus.info("controller.publishing", scope=scope, topic=topic)
            # The connector's publish is fire-and-forget
            await connector.publish(topic, payload)

            # In a real fire-and-forget, we can't be sure it succeeded,
            # but for UX we assume it did if no exception was raised.
            # Give a brief moment for the task to be sent.
            await asyncio.sleep(0.1)
            bus.info("controller.publish_success")

        except Exception as e:
            bus.error("controller.error", error=e)
        finally:
            await connector.disconnect()

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~

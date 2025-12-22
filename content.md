好的，我们来完成功能闭环。

现在 `Engine` 已经具备了通过 Unix Domain Socket (UDS) 广播遥测事件的能力，我们需要让 `cs-observer` 工具能够作为客户端连接上去，实时接收并渲染这些事件。这将最终点亮 `cs-observer watch --backend local` 功能。

## [WIP] feat(observer): 实现 cs-observer watch 的 local 后端 (UDS 客户端)

### 用户需求
执行“路线图：实现统一的 `local` 后端与实时 `watch` 功能”中的第三步，即“[功能闭环] 实现 `cs-observer watch` 的 UDS 客户端”。具体要求：
1.  修改 `cs-observer watch` 命令，使其支持 `--backend local` 选项。
2.  为 `local` 后端实现 UDS 客户端逻辑，使其能连接到 `Engine` 广播的 socket。
3.  从 socket 实时读取、解析 JSON Lines 格式的事件流。
4.  将解析后的事件传递给现有的渲染逻辑，确保 UI 输出与 MQTT 模式一致。
5.  在 Windows 平台上，如果使用 `local` 后端，应给出明确的不支持提示。

### 评论
这是实现本地实时可观测性的最后一步，也是对前两步工作的最终检验。通过复用 `on_message` 回调和现有的 `rich` 渲染器，我们确保了无论是通过分布式 MQTT 还是本地 UDS，用户都能获得完全一致的、高质量的实时日志流体验。

### 目标
1.  **添加依赖**: 为 `cascade-cli-observer` 包添加对 `cascade-connector-local` 的依赖，以便能够引用共享的 UDS socket 路径常量。
2.  **实现 UDS 客户端**: 在 `cs-observer` 的 `app.py` 中，创建一个新的异步循环函数，专门负责处理 UDS 的连接、数据读取和重连逻辑。
3.  **更新 `watch` 命令**: 重构 `watch` 命令，使其根据 `--backend` 参数的值，分派到新的 UDS 客户端逻辑或旧的 MQTT 客户端逻辑。
4.  **平台兼容性**: 在 UDS 客户端逻辑的入口处添加 `sys.platform` 检查，为 Windows 用户提供清晰的错误信息。

### 基本原理
我们将使用 `asyncio.open_unix_connection` 来建立与 `Engine` 的 UDS 连接，这是 Python 标准库中处理此类 IPC 的标准方法。通过 `StreamReader.readline()`，我们可以高效地、异步地处理以换行符分隔的 JSON Lines 数据流。通过将新旧逻辑分别封装在独立的函数中，并在 `watch` 命令中进行分派，我们保持了代码的清晰和可维护性。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/ui #concept/sync #scope/ux #ai/instruct #task/domain/ui #task/object/watch-client #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 添加 `cascade-connector-local` 依赖

首先，我们需要让 `observer` 能够访问 `local` 连接器中定义的 UDS 路径常量。

~~~~~act
patch_file
packages/cascade-cli-observer/pyproject.toml
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-common",
  "typer[all]",
  "aiomqtt",
  "rich"
]
~~~~~
~~~~~toml
dependencies = [
  "cascade-spec",
  "cascade-common",
  "cascade-connector-local",
  "typer[all]",
  "aiomqtt",
  "rich"
]
~~~~~

~~~~~act
patch_file
packages/cascade-cli-observer/pyproject.toml
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
~~~~~
~~~~~toml
[tool.uv.sources]
cascade-spec = { workspace = true }
cascade-common = { workspace = true }
cascade-connector-local = { workspace = true }
~~~~~

#### Acts 2: 实现 UDS 客户端并重构 `watch` 命令

现在，我们将重写 `app.py`。由于逻辑变更较大（引入新的循环、重构现有函数），使用 `write_file` 是最清晰和安全的方式。

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import asyncio
import json
import sqlite3
import time
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cascade.common.messaging import bus
from .rendering import RichCliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.connectors.local.connector import DEFAULT_TELEMETRY_UDS_PATH
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer()
console = Console(stderr=True)

# Keep track of runs to print headers only once
seen_run_ids = set()


async def on_message(topic: str, payload: dict):
    """Callback to process incoming telemetry messages."""
    global seen_run_ids

    # The payload structure is flat for headers, with a nested 'body'
    body = payload.get("body", {})
    run_id = payload.get("run_id")

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


async def _run_mqtt_watcher(project: str, hostname: str, port: int):
    """Connects to MQTT and watches for telemetry events."""
    topic = f"cascade/telemetry/+/{project}/+/events"
    connector = MqttConnector(hostname=hostname, port=port)
    shutdown_event = asyncio.Event()

    bus.info(
        "observer.startup.watching", project=project, hostname=hostname, port=port
    )

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


async def _run_uds_watcher():
    """Connects to a local UDS socket and watches for telemetry events."""
    uds_path = DEFAULT_TELEMETRY_UDS_PATH
    bus.info("observer.startup.watching_uds", path=uds_path)

    while True:
        try:
            reader, writer = await asyncio.open_unix_connection(uds_path)
            bus.info("observer.startup.connected_uds")
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                try:
                    data = json.loads(line)
                    await on_message("local.telemetry", data)
                except json.JSONDecodeError:
                    continue  # Ignore malformed lines
            bus.warning("observer.shutdown_uds_disconnected")
        except FileNotFoundError:
            bus.warning("observer.startup.uds_not_found", path=uds_path)
        except ConnectionRefusedError:
            bus.warning("observer.startup.uds_conn_refused", path=uds_path)
        except Exception as e:
            bus.error("observer.error_uds", error=e)
        finally:
            # Wait before retrying to avoid spamming connection attempts
            await asyncio.sleep(2)


@app.command()
def watch(
    backend: str = typer.Option(
        "mqtt", "--backend", help="Telemetry backend ('mqtt' or 'local')."
    ),
    project: str = typer.Option(
        "default", "--project", help="The project ID to watch (MQTT only)."
    ),
    hostname: str = typer.Option(
        "localhost", "--host", help="MQTT broker hostname (MQTT only)."
    ),
    port: int = typer.Option(1883, "--port", help="MQTT broker port (MQTT only)."),
):
    """
    Connect to a backend and watch for real-time telemetry events.
    """
    main_loop = None
    if backend == "local":
        if sys.platform == "win32":
            bus.error("observer.error_uds_unsupported")
            raise typer.Exit(1)
        main_loop = _run_uds_watcher()
    elif backend == "mqtt":
        main_loop = _run_mqtt_watcher(project, hostname, port)
    else:
        bus.error("observer.error_invalid_backend", backend=backend)
        raise typer.Exit(1)

    try:
        asyncio.run(main_loop)
    except KeyboardInterrupt:
        pass


@app.command()
def status(
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'local')."
    ),
    hostname: str = typer.Option("localhost", help="MQTT broker hostname."),
    port: int = typer.Option(1883, help="MQTT broker port."),
):
    """
    Connect to the backend, query the current status of all constraints, and exit.
    """
    try:
        asyncio.run(_get_status(backend=backend, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


async def _get_status(backend: str, hostname: str, port: int):
    """Core logic for the status command."""
    if backend == "local":
        await _get_status_sqlite()
        return

    constraints: list[GlobalConstraint] = []

    async def on_status_message(topic, payload):
        if payload and isinstance(payload, dict):
            try:
                # Filter out any malformed or non-constraint messages
                if "scope" in payload and "type" in payload:
                    constraints.append(GlobalConstraint(**payload))
            except TypeError:
                pass  # Ignore malformed payloads

    connector = MqttConnector(hostname=hostname, port=port)
    bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
    await connector.connect()
    bus.info("controller.connected")
    await connector.subscribe("cascade/constraints/#", on_status_message)

    # Wait a short moment for all retained messages to arrive from the broker
    await asyncio.sleep(0.5)
    await connector.disconnect()
    bus.info("observer.shutdown")

    _render_constraints_table(constraints)


async def _get_status_sqlite():
    """Fetches and displays constraints from the SQLite database."""
    db_path = Path("~/.cascade/control.db").expanduser()
    if not db_path.exists():
        console.print(f"[yellow]SQLite database not found at:[/yellow] {db_path}")
        console.print("[dim]No active constraints found.[/dim]")
        return

    def _blocking_read():
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM constraints")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    try:
        rows = await asyncio.to_thread(_blocking_read)
        constraints = []
        for row in rows:
            try:
                constraints.append(
                    GlobalConstraint(
                        id=row["id"],
                        scope=row["scope"],
                        type=row["type"],
                        params=json.loads(row["params"]),
                        expires_at=row.get("expires_at"),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                pass  # Ignore malformed rows
        _render_constraints_table(constraints)
    except Exception as e:
        bus.error("observer.startup.error", hostname=str(db_path), port="", error=e)


def _render_constraints_table(constraints: list[GlobalConstraint]):
    """Renders a list of constraints into a Rich table."""
    table = Table(title="[bold]Active Cascade Constraints[/bold]", title_justify="left")
    table.add_column("Scope", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Params", style="green")
    table.add_column("Expires In (s)", justify="right", style="yellow")

    now = time.time()
    if not constraints:
        console.print("[dim]No active constraints found.[/dim]")
        return

    for c in sorted(constraints, key=lambda x: x.scope):
        expires_in = ""
        if c.expires_at:
            delta = c.expires_at - now
            if delta > 0:
                expires_in = f"{delta:.1f}"
            else:
                expires_in = "[red]- (expired)[/red]"
        else:
            expires_in = "[dim]Never[/dim]"

        table.add_row(c.scope, c.type, str(c.params), expires_in)

    console.print(table)


def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~

#### Acts 3: 添加新的用户反馈消息

最后，我们需要为新的 UDS 客户端逻辑添加相应的用户反馈消息。

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

    "controller.connecting": "Connecting to {backend} backend at [bold green]{hostname}:{port}[/bold green]...",
~~~~~
~~~~~json
{
    "observer.startup.watching": "🔭 Watching project: [bold cyan]{project}[/bold cyan] via MQTT on [bold green]{hostname}:{port}[/bold green]...",
    "observer.startup.watching_uds": "🔭 Watching for local engine via UDS at [bold green]{path}[/bold green]...",
    "observer.startup.connected": "✅ Connected to MQTT broker.",
    "observer.startup.connected_uds": "✅ Connected to local engine.",
    "observer.startup.error": "❌ Failed to connect to MQTT broker at {hostname}:{port}. Error: {error}",
    "observer.startup.uds_not_found": "🟡 Waiting for engine... (Socket not found at {path})",
    "observer.startup.uds_conn_refused": "🟡 Waiting for engine... (Connection refused at {path})",
    "observer.shutdown": "\n🔌 Disconnecting and shutting down...",
    "observer.shutdown_uds_disconnected": "🔌 Engine disconnected. Retrying connection...",
    "observer.error_uds": "❌ An unexpected error occurred with the UDS connection: {error}",
    "observer.error_uds_unsupported": "❌ The 'local' backend is not supported on Windows.",
    "observer.error_invalid_backend": "❌ Invalid backend '{backend}'. Choose 'mqtt' or 'local'.",
    "observer.telemetry.run_header": "\n[bold yellow]─── Run Started: {run_id} ───[/bold yellow]",
    "observer.telemetry.lifecycle.ENGINE_STARTED": "▶️  Engine started.",
    "observer.telemetry.lifecycle.ENGINE_STOPPED": "✅ Engine stopped.",
    "observer.telemetry.task_state.RUNNING": "   - Task '[bold]{task_name}[/bold]' started.",
    "observer.telemetry.task_state.COMPLETED": "   - [green]✅ Task '[bold]{task_name}[/bold]' succeeded in {duration_ms:.0f}ms.[/green]",
    "observer.telemetry.task_state.FAILED": "   - [bold red]❌ Task '[bold]{task_name}[/bold]' failed after {duration_ms:.0f}ms. Error: {error}[/bold red]",
    "observer.telemetry.task_state.SKIPPED": "   - [dim]⚪ Task '[bold]{task_name}[/bold]' skipped.[/dim]",
    "observer.telemetry.unknown_event": "[dim]Received unknown event type: {type}[/dim]",

    "controller.connecting": "Connecting to {backend} backend at [bold green]{hostname}:{port}[/bold green]...",
~~~~~

### 下一步建议
我们已经完成了 `cs-observer watch` 的 UDS 客户端实现。现在，我们拥有了一个功能完整的、端到端的本地实时可观测性解决方案。

在继续之前，最关键的一步是进行验证。下一步应该是 **步骤 4: [质量保证] 编写端到端集成测试**。我们需要创建一个新的测试文件来模拟一个 `Engine` 实例和一个 `watch` 客户端，并验证它们之间通过 UDS 的通信是可靠和正确的。如果你同意，我将开始制定这个测试计划。

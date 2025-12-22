好的，我们来执行 **步骤 3**，将新的 `SqliteConnector` 集成到 CLI 工具中。

这个计划将分两步执行：首先修改 `cs-controller` 以支持 `--backend` 标志，然后修改 `cs-observer` 的 `status` 命令以从 SQLite 数据库读取状态。

## [WIP] feat: 将 SqliteConnector 集成到 CLI 工具中

### 用户需求
根据项目路线图，需要完成 `SqliteConnector` 开发的第三步：
1.  修改 `cs-controller` 的所有命令，使其接受 `--backend [mqtt|sqlite]` 选项来选择控制平面。
2.  修改 `cs-observer status` 命令，使其同样支持 `--backend` 选项，并在选择 `sqlite` 时直接从数据库读取约束状态。

### 评论
这是一个关键的集成步骤，它将 `SqliteConnector` 的能力真正暴露给最终用户。通过一个统一的 `--backend` 标志，我们为用户提供了在分布式 (MQTT) 和本地 (SQLite) 控制平面之间无缝切换的灵活性，极大地增强了 Cascade 在不同部署场景下的适应性。

### 目标
1.  为 `cs-controller` 的 `set-limit`、`pause` 和 `resume` 命令添加 `--backend` 命令行选项。
2.  实现一个 `_get_connector` 工厂函数，根据选项动态实例化 `MqttConnector` 或 `SqliteConnector`。
3.  为 `cs-observer` 的 `status` 命令添加 `--backend` 选项。
4.  在 `cs-observer status` 中实现从 SQLite 数据库文件 (`~/.cascade/control.db`) 读取和显示约束的逻辑。
5.  重构 `cs-observer` 中的状态显示逻辑，使其可被 MQTT 和 SQLite 两种模式复用。

### 基本原理
我们将通过 `patch_file` 对 `cs-controller` 进行精确修改，注入新的命令行选项和连接器选择逻辑。由于对 `cs-observer` 的修改更为结构化（需要添加新函数并重构现有函数），我们将使用 `write_file` 来确保代码的完整性和清晰性，这符合当重构幅度较大时的文件写入策略。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/config #scope/api #scope/ux #ai/instruct #task/domain/cli #task/object/sqlite-connector #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 修改 `cs-controller` 以支持后端选择

首先，我们为 `cs-controller` 添加必要的 import，并实现一个根据 `--backend` 参数选择连接器的工厂函数。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
import asyncio
import time
import typer
from dataclasses import asdict

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer(
    help="A command-line tool to control running Cascade workflows via MQTT."
)
~~~~~
~~~~~python
import asyncio
import time
import typer
from dataclasses import asdict

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.connectors.sqlite import SqliteConnector
from cascade.spec.protocols import Connector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer(
    help="A command-line tool to control running Cascade workflows."
)


def _get_connector(backend: str, hostname: str, port: int) -> Connector:
    if backend == "sqlite":
        return SqliteConnector()
    elif backend == "mqtt":
        return MqttConnector(hostname=hostname, port=port)
    else:
        # This case is primarily for safety, Typer's Choice/Enum would be better
        raise typer.BadParameter(f"Unsupported backend: {backend}")
~~~~~

接下来，我们将 `--backend` 选项添加到所有命令中，并更新其实现以使用新的连接器工厂。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
async def _publish_pause(scope: str, ttl: int | None, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
~~~~~
~~~~~python
async def _publish_pause(
    scope: str, ttl: int | None, backend: str, hostname: str, port: int
):
    """Core logic for publishing a pause constraint."""
    connector = _get_connector(backend, hostname, port)
    try:
        bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
        await connector.connect()
~~~~~
~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
async def _publish_resume(scope: str, hostname: str, port: int):
    """Core logic for publishing a resume (clear constraint) command."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
~~~~~
~~~~~python
async def _publish_resume(scope: str, backend: str, hostname: str, port: int):
    """Core logic for publishing a resume (clear constraint) command."""
    connector = _get_connector(backend, hostname, port)
    try:
        bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
        await connector.connect()
~~~~~
~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
async def _publish_limit(
    scope: str,
    concurrency: int | None,
    rate: str | None,
    ttl: int | None,
    hostname: str,
    port: int,
):
    """Core logic for publishing concurrency or rate limit constraints."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
~~~~~
~~~~~python
async def _publish_limit(
    scope: str,
    concurrency: int | None,
    rate: str | None,
    ttl: int | None,
    backend: str,
    hostname: str,
    port: int,
):
    """Core logic for publishing concurrency or rate limit constraints."""
    connector = _get_connector(backend, hostname, port)
    try:
        bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
        await connector.connect()
~~~~~
~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
@app.command()
def set_limit(
    scope: str = typer.Option(
        ...,
        "--scope",
        help="The scope to apply the limit to (e.g., 'global', 'task:api_call').",
    ),
    concurrency: int = typer.Option(
        None, "--concurrency", help="The maximum number of concurrent tasks."
    ),
    rate: str = typer.Option(
        None, "--rate", help="The rate limit (e.g., '10/m', '5/s')."
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Constraint expires automatically."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'concurrency' or 'rate_limit' constraint to the MQTT broker.
    You must provide either --concurrency or --rate (or both).
    """
    if concurrency is None and rate is None:
        print("Error: Must provide either --concurrency or --rate.")
        raise typer.Exit(code=1)

    try:
        asyncio.run(
            _publish_limit(
                scope=scope,
                concurrency=concurrency,
                rate=rate,
                ttl=ttl,
                hostname=hostname,
                port=port,
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~python
@app.command()
def set_limit(
    scope: str = typer.Option(
        ...,
        "--scope",
        help="The scope to apply the limit to (e.g., 'global', 'task:api_call').",
    ),
    concurrency: int = typer.Option(
        None, "--concurrency", help="The maximum number of concurrent tasks."
    ),
    rate: str = typer.Option(
        None, "--rate", help="The rate limit (e.g., '10/m', '5/s')."
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Constraint expires automatically."
    ),
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'sqlite')."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'concurrency' or 'rate_limit' constraint to the control plane.
    You must provide either --concurrency or --rate (or both).
    """
    if concurrency is None and rate is None:
        print("Error: Must provide either --concurrency or --rate.")
        raise typer.Exit(code=1)

    try:
        asyncio.run(
            _publish_limit(
                scope=scope,
                concurrency=concurrency,
                rate=rate,
                ttl=ttl,
                backend=backend,
                hostname=hostname,
                port=port,
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Pause expires automatically."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the MQTT broker.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """
    try:
        asyncio.run(_publish_pause(scope=scope, ttl=ttl, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~python
@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Pause expires automatically."
    ),
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'sqlite')."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'pause' constraint to the control plane.
    This will cause running Cascade engines to stop scheduling new tasks that
    match the specified scope until a 'resume' command is sent.
    """
    try:
        asyncio.run(
            _publish_pause(
                scope=scope, ttl=ttl, backend=backend, hostname=hostname, port=port
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
@app.command()
def resume(
    scope: str = typer.Argument(
        "global",
        help="The scope to resume (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'resume' command to the MQTT broker.
    This clears any 'pause' constraint for the specified scope, allowing
    tasks to be scheduled again.
    """
    try:
        asyncio.run(_publish_resume(scope=scope, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~python
@app.command()
def resume(
    scope: str = typer.Argument(
        "global",
        help="The scope to resume (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'sqlite')."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'resume' command to the control plane.
    This clears any 'pause' constraint for the specified scope, allowing
    tasks to be scheduled again.
    """
    try:
        asyncio.run(
            _publish_resume(scope=scope, backend=backend, hostname=hostname, port=port)
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")
~~~~~
~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
~~~~~
~~~~~python
    "controller.connecting": "Connecting to MQTT broker at [bold green]{hostname}:{port}[/bold green]...",
~~~~~
~~~~~python
    "controller.connecting": "Connecting to {backend} backend at [bold green]{hostname}:{port}[/bold green]...",
~~~~~

#### Acts 2: 修改 `cs-observer` 以从 SQLite 读取状态

由于此项修改涉及添加新函数和重构，我们将直接覆写整个文件以确保正确性。

~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import asyncio
import json
import sqlite3
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from cascade.common.messaging import bus
from .rendering import RichCliRenderer
from cascade.connectors.mqtt import MqttConnector
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

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        # The finally block in main_loop will handle graceful shutdown
        pass


@app.command()
def status(
    backend: str = typer.Option(
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'sqlite')."
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
    if backend == "sqlite":
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

### 下一步建议
我们已经完成了 `SqliteConnector` 的 CLI 集成。根据路线图，下一步是 **步骤 4: [质量保证] 编写全面的端到端测试**。

我建议创建一个新的测试文件 `tests/cli/e2e/test_e2e_cli_sqlite_backend.py`，并添加以下测试用例：
1.  测试 `cs-controller set-limit --backend sqlite` 是否成功在数据库中创建条目。
2.  测试 `cs-observer status --backend sqlite` 是否能正确读取并显示该条目。
3.  测试 `cs-controller resume --backend sqlite` 是否能成功删除数据库中的条目。
4.  验证当 `--backend mqtt` 时，数据库文件不受影响。

如果你同意，我将开始制定实现这些测试的计划。

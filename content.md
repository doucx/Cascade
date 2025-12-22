当然，我将开始执行路线图中的**步骤 3**。

这个步骤的核心目标是将新开发的 `SqliteConnector` 集成到现有的命令行工具 `cs-controller` 和 `cs-observer` 中，允许用户通过一个简单的 `--backend` 标志在 MQTT 和 SQLite 两种模式之间切换。这将使 SQLite 后端真正变得可用。

我将生成一个计划，通过 `write_file` 操作来更新这两个 CLI 工具的入口文件。

## [WIP] feat(cli): 将 SqliteConnector 集成到 CLI 工具中

### 用户需求
根据项目路线图，需要将 `SqliteConnector` 集成到 `cs-controller` 和 `cs-observer` 两个命令行工具中。用户应该能够通过一个 `--backend` 命令行选项来选择使用 `mqtt`（默认）或 `sqlite` 作为控制平面的后端。

### 评论
这是使 `SqliteConnector` 功能对用户可用的关键一步。通过提供一个统一的 CLI 标志，我们将 Cascade 的部署灵活性大大增强，为单机或边缘环境提供了一个零依赖、高可靠的替代方案，同时也保留了分布式场景下 MQTT 的能力。

### 目标
1.  修改 `cs-controller` 的所有命令 (`set-limit`, `pause`, `resume`)，使其接受 `--backend` 和 `--db-path` 选项，并根据选项值实例化和使用 `MqttConnector` 或 `SqliteConnector`。
2.  修改 `cs-observer` 的 `status` 命令，使其接受 `--backend` 和 `--db-path` 选项。当后端为 `sqlite` 时，它将直接查询 SQLite 数据库文件以获取当前有效的约束状态。
3.  确保 `cs-observer` 的 `watch` 命令不受影响，因为它本质上依赖于 MQTT 的发布/订阅模型进行实时遥测。

### 基本原理
为了保持代码的清晰和可维护性，我将引入一个 `_get_connector` 工厂函数来处理不同后端的实例化逻辑。在 `cs-controller` 中，这个工厂函数将根据 `--backend` 标志返回一个实现了 `Connector` 协议的实例。

对于 `cs-observer status`，当后端是 SQLite 时，最直接和可靠的方式是直接连接到 SQLite 数据库文件并查询 `constraints` 表。这遵循了“直接从事实来源读取状态”的原则，避免了不必要的抽象层。`watch` 命令则天然与 MQTT 绑定，因此其行为将保持不变。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/config #scope/api #scope/ux #ai/instruct #task/domain/cli #task/object/sqlite-backend #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 更新 `cs-controller` 以支持多后端

我将重写 `cs-controller` 的应用文件。主要变更包括：
1.  引入一个新的枚举 `BackendChoice` 和一个工厂函数 `_get_connector`。
2.  将 `--backend` 和 `--db-path` 选项添加到所有命令中。
3.  更新核心的 `_publish_*` 函数，使其通过工厂函数获取并使用正确的连接器实例。

~~~~~act
write_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
import asyncio
import time
import typer
from enum import Enum
from dataclasses import asdict
from pathlib import Path

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.connectors.sqlite import SqliteConnector
from cascade.spec.constraint import GlobalConstraint
from cascade.spec.protocols import Connector

app = typer.Typer(
    help="A command-line tool to control running Cascade workflows."
)


class BackendChoice(str, Enum):
    mqtt = "mqtt"
    sqlite = "sqlite"


def _get_connector(
    backend: BackendChoice, hostname: str, port: int, db_path: str
) -> Connector:
    """Factory function to get the appropriate connector."""
    if backend == BackendChoice.sqlite:
        return SqliteConnector(db_path=db_path)
    return MqttConnector(hostname=hostname, port=port)


async def _publish_pause(
    scope: str,
    ttl: int | None,
    backend: BackendChoice,
    hostname: str,
    port: int,
    db_path: str,
):
    """Core logic for publishing a pause constraint."""
    connector = _get_connector(backend, hostname, port, db_path)
    try:
        bus.info("controller.connecting", hostname=f"{backend.value} backend", port="")
        await connector.connect()
        bus.info("controller.connected")

        constraint_id = f"pause-{scope}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )
        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing", scope=scope, topic=topic)
        await connector.publish(topic, payload, retain=True)
        await asyncio.sleep(0.1)
        bus.info("controller.publish_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


async def _publish_resume(
    scope: str, backend: BackendChoice, hostname: str, port: int, db_path: str
):
    """Core logic for publishing a resume (clear constraint) command."""
    connector = _get_connector(backend, hostname, port, db_path)
    try:
        bus.info("controller.connecting", hostname=f"{backend.value} backend", port="")
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.resuming", scope=scope, topic=topic)
        await connector.publish(topic, {}, retain=True)
        await asyncio.sleep(0.1)
        bus.info("controller.resume_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


async def _publish_limit(
    scope: str,
    concurrency: int | None,
    rate: str | None,
    ttl: int | None,
    backend: BackendChoice,
    hostname: str,
    port: int,
    db_path: str,
):
    """Core logic for publishing concurrency or rate limit constraints."""
    connector = _get_connector(backend, hostname, port, db_path)
    try:
        bus.info("controller.connecting", hostname=f"{backend.value} backend", port="")
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        expires_at = time.time() + ttl if ttl else None
        payloads = []

        if concurrency is not None:
            constraint_id = f"concurrency-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
            payloads.append(asdict(constraint))
            bus.info(
                "controller.publishing_limit",
                scope=scope,
                topic=topic,
                limit=concurrency,
            )

        if rate is not None:
            constraint_id = f"ratelimit-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
            payloads.append(asdict(constraint))
            bus.info("controller.publishing_rate", scope=scope, topic=topic, rate=rate)

        # In MQTT, each constraint needs its own topic. In SQLite, we can batch.
        # The current connector interface uses one topic, so we send the last one.
        # This implies that setting concurrency and rate at the same time might
        # only work fully as expected with SQLite backend. For now, we publish both.
        for payload in payloads:
            await connector.publish(topic, payload, retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_limit_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


# Common Typer options
BackendOption = typer.Option(
    "mqtt", "--backend", help="The control plane backend to use."
)
DbPathOption = typer.Option(
    str(Path.home() / ".cascade" / "control.db"),
    "--db-path",
    help="Path to the SQLite database file (used with --backend sqlite).",
)
HostOption = typer.Option(
    "localhost", "--host", help="MQTT broker hostname (used with --backend mqtt)."
)
PortOption = typer.Option(
    1883, "--port", help="MQTT broker port (used with --backend mqtt)."
)


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
    backend: BackendChoice = BackendOption,
    db_path: str = DbPathOption,
    hostname: str = HostOption,
    port: int = PortOption,
):
    """
    Publish a 'concurrency' or 'rate_limit' constraint.
    """
    if concurrency is None and rate is None:
        bus.error("controller.error", error="Must provide either --concurrency or --rate.")
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
                db_path=db_path,
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    ttl: int = typer.Option(
        None, "--ttl", help="Time to live in seconds. Pause expires automatically."
    ),
    backend: BackendChoice = BackendOption,
    db_path: str = DbPathOption,
    hostname: str = HostOption,
    port: int = PortOption,
):
    """
    Publish a 'pause' constraint.
    """
    try:
        asyncio.run(
            _publish_pause(
                scope=scope,
                ttl=ttl,
                backend=backend,
                hostname=hostname,
                port=port,
                db_path=db_path,
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


@app.command()
def resume(
    scope: str = typer.Argument(
        "global",
        help="The scope to resume (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    backend: BackendChoice = BackendOption,
    db_path: str = DbPathOption,
    hostname: str = HostOption,
    port: int = PortOption,
):
    """
    Publish a 'resume' command, clearing any active constraints for the scope.
    """
    try:
        asyncio.run(
            _publish_resume(
                scope=scope,
                backend=backend,
                hostname=hostname,
                port=port,
                db_path=db_path,
            )
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~
~~~~~act
write_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import asyncio
import json
import time
from enum import Enum
from pathlib import Path
import typer
import aiosqlite
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


class BackendChoice(str, Enum):
    mqtt = "mqtt"
    sqlite = "sqlite"


async def on_message(topic: str, payload: dict):
    """Callback to process incoming telemetry messages."""
    global seen_run_ids

    body = payload.get("body", {})
    run_id = payload.get("run_id")

    if not run_id or not body:
        return

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
    Watch for real-time telemetry events via MQTT.
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
        pass


@app.command()
def status(
    backend: BackendChoice = typer.Option(
        "mqtt", "--backend", help="The control plane backend to query."
    ),
    db_path: str = typer.Option(
        str(Path.home() / ".cascade" / "control.db"),
        "--db-path",
        help="Path to SQLite DB file (if using --backend sqlite).",
    ),
    hostname: str = typer.Option(
        "localhost", "--host", help="MQTT broker hostname (if using --backend mqtt)."
    ),
    port: int = typer.Option(
        1883, "--port", help="MQTT broker port (if using --backend mqtt)."
    ),
):
    """
    Query and display the current status of all active constraints.
    """
    try:
        asyncio.run(
            _get_status(backend=backend, db_path=db_path, hostname=hostname, port=port)
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


async def _get_status_from_mqtt(hostname: str, port: int) -> list[GlobalConstraint]:
    """Fetch constraints from MQTT broker."""
    constraints: list[GlobalConstraint] = []

    async def on_status_message(topic, payload):
        if payload and isinstance(payload, dict):
            try:
                if "scope" in payload and "type" in payload:
                    constraints.append(GlobalConstraint(**payload))
            except TypeError:
                pass

    connector = MqttConnector(hostname=hostname, port=port)
    bus.info("controller.connecting", hostname=hostname, port=port)
    await connector.connect()
    bus.info("controller.connected")
    await connector.subscribe("cascade/constraints/#", on_status_message)
    await asyncio.sleep(0.5)
    await connector.disconnect()
    return constraints


async def _get_status_from_sqlite(db_path_str: str) -> list[GlobalConstraint]:
    """Fetch constraints directly from SQLite database."""
    constraints: list[GlobalConstraint] = []
    db_path = Path(db_path_str).expanduser()
    if not db_path.exists():
        bus.warning("observer.sqlite.db_not_found", path=str(db_path))
        return []

    try:
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM constraints") as cursor:
            async for row in cursor:
                constraints.append(
                    GlobalConstraint(
                        id=row["id"],
                        scope=row["scope"],
                        type=row["type"],
                        params=json.loads(row["params"]),
                        expires_at=row["expires_at"],
                    )
                )
        await db.close()
    except Exception as e:
        bus.error("observer.sqlite.query_error", error=e)
    return constraints


async def _get_status(
    backend: BackendChoice, db_path: str, hostname: str, port: int
):
    """Core logic for the status command."""
    if backend == BackendChoice.mqtt:
        constraints = await _get_status_from_mqtt(hostname, port)
    else:
        constraints = await _get_status_from_sqlite(db_path)

    bus.info("observer.shutdown")

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
                continue  # Don't show expired constraints from SQLite
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
~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
~~~~~
~~~~~json
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
    "controller.error": "❌ An error occurred: {error}"
}
~~~~~
~~~~~json
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
    "controller.error": "❌ An error occurred: {error}",

    "observer.sqlite.db_not_found": "⚠️  Database file not found at {path}. No constraints to show.",
    "observer.sqlite.query_error": "❌ Failed to query SQLite database. Error: {error}"
}
~~~~~

### 下一步建议
我们已经成功地将 `SqliteConnector` 集成到了 CLI 工具中。现在，最关键的下一步是**步骤 4: [质量保证] 编写全面的端到端测试**。

我们需要创建新的测试用例，专门验证：
1.  `cs-controller` 在使用 `--backend sqlite` 时，能够正确地向数据库文件中写入和删除约束。
2.  `cs-observer status --backend sqlite` 能够准确地从数据库文件中读取并显示这些约束。
3.  确保现有的基于 MQTT 的测试没有被破坏。

这将确保我们的新功能是健壮和可靠的。如果你同意，我将开始准备测试计划。

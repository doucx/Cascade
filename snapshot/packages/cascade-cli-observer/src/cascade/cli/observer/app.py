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
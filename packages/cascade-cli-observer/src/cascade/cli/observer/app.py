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


async def _run_uds_watcher():
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
    try:
        asyncio.run(_get_status(backend=backend, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


async def _get_status(backend: str, hostname: str, port: int):
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

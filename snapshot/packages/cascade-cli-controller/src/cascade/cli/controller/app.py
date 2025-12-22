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
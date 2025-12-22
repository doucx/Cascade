import asyncio
import time
import typer
from dataclasses import asdict

from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.connectors.local import LocalConnector
from cascade.spec.protocols import Connector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer(help="A command-line tool to control running Cascade workflows.")


def _get_connector(backend: str, hostname: str, port: int) -> Connector:
    if backend == "local":
        return LocalConnector()
    elif backend == "mqtt":
        return MqttConnector(hostname=hostname, port=port)
    else:
        # This case is primarily for safety, Typer's Choice/Enum would be better
        raise typer.BadParameter(f"Unsupported backend: {backend}")


async def _publish_pause(
    scope: str, ttl: int | None, backend: str, hostname: str, port: int
):
    """Core logic for publishing a pause constraint."""
    connector = _get_connector(backend, hostname, port)
    try:
        bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        # Create a deterministic ID for idempotency (Last-Write-Wins)
        constraint_id = f"pause-{scope}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )

        # Convert to dictionary for JSON serialization
        payload = asdict(constraint)

        # Publish to a structured topic based on scope
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing", scope=scope, topic=topic)
        # The connector's publish is fire-and-forget, now with retain=True
        await connector.publish(topic, payload, retain=True)

        # In a real fire-and-forget, we can't be sure it succeeded,
        # but for UX we assume it did if no exception was raised.
        # Give a brief moment for the task to be sent.
        await asyncio.sleep(0.1)
        bus.info("controller.publish_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


async def _publish_resume(scope: str, backend: str, hostname: str, port: int):
    """Core logic for publishing a resume (clear constraint) command."""
    connector = _get_connector(backend, hostname, port)
    try:
        bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.resuming", scope=scope, topic=topic)
        # Publishing an empty retained message clears the previous one
        await connector.publish(topic, "", retain=True)

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
    backend: str,
    hostname: str,
    port: int,
):
    """Core logic for publishing concurrency or rate limit constraints."""
    connector = _get_connector(backend, hostname, port)
    try:
        bus.info("controller.connecting", backend=backend, hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        expires_at = time.time() + ttl if ttl else None

        if concurrency is not None:
            constraint_id = f"concurrency-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
            bus.info(
                "controller.publishing_limit",
                scope=scope,
                topic=topic,
                limit=concurrency,
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        if rate is not None:
            constraint_id = f"ratelimit-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
            bus.info("controller.publishing_rate", scope=scope, topic=topic, rate=rate)
            await connector.publish(topic, asdict(constraint), retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_limit_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


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
        "mqtt", "--backend", help="Control plane backend ('mqtt' or 'local')."
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


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()

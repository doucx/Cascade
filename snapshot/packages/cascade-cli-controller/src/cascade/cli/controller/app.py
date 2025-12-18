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


async def _publish_pause(scope: str, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
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
    try:
        asyncio.run(_publish_pause(scope=scope, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
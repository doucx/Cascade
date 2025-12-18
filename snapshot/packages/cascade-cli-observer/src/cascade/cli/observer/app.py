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


def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()

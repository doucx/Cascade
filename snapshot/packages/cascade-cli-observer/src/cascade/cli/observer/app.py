import typer
from cascade.common.messaging import bus
from .rendering import RichCliRenderer

app = typer.Typer()


@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    bus.info("observer.startup.watching", project=project)
    # TODO: Implement MQTT connection and event printing logic.
    bus.warning("observer.not_implemented")


def main():
    # Inject the rich renderer into the global message bus at application startup
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
import typer
from cascade.common.messaging import bus
from cascade.common.renderers import CliRenderer

app = typer.Typer()


@app.command()
def pause(scope: str = typer.Argument(..., help="The scope to pause (e.g., 'global', 'task:api_call').")):
    """
    Publish a 'pause' constraint to the MQTT broker.
    """
    bus.info("controller.publishing", scope=scope)
    # TODO: Implement MQTT connection and publishing logic.
    bus.warning("controller.not_implemented")


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
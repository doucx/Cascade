import typer

app = typer.Typer()


@app.command()
def watch(project: str = typer.Option("default", help="The project ID to watch.")):
    """
    Connect to the MQTT broker and watch for real-time telemetry events.
    """
    typer.echo(f"Starting to watch project: {project}...")
    # TODO: Implement MQTT connection and event printing logic.
    typer.echo("Observer not yet implemented.")


def main():
    app()


if __name__ == "__main__":
    main()
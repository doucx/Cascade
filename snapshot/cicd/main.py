import sys
import cascade as cs
import typer
from .workflows import pr_check_workflow, release_workflow

app = typer.Typer()

@app.command()
def main(event: str = typer.Option(..., "--event", help="The GitHub event name.")):
    """
    Cascade CI/CD Pipeline Entrypoint.
    """
    print(f"Received GitHub event: {event}")

    target = None
    if event in ["pull_request", "push", "workflow_dispatch"]:
        print("Triggering PR Check Workflow...")
        target = pr_check_workflow()
    # A push event on a tag looks like 'push' but github.ref starts with 'refs/tags/'
    # GHA doesn't have a simple 'tag' event name, so a more robust check is needed.
    # For now, we assume a separate trigger or manual dispatch for releases.
    # A simple approach for a future iteration would be to pass ${{ github.ref_type }}
    # elif event == "tag":
    #    print("Triggering Release Workflow...")
    #    target = release_workflow()
    else:
        print(f"No workflow defined for event '{event}'. Exiting.")
        sys.exit(0)

    if target:
        # The log level is configured in the GHA workflow file
        cs.run(target, log_level="DEBUG")

if __name__ == "__main__":
    app()
import inspect
from typing import Any, Callable

try:
    import typer
except ImportError:
    typer = None

from ..spec.task import LazyResult
from ..graph.build import build_graph
from ..spec.common import Param


def cli(target: LazyResult[Any]) -> Callable[[], None]:
    """
    A factory that generates a Typer-based command-line interface for a Cascade workflow.
    It inspects the workflow for `cs.Param` dependencies and converts them into
    CLI options.

    Args:
        target: The final LazyResult of the Cascade workflow.

    Returns:
        A function that, when called, will run the Typer CLI application.
    """
    if typer is None:
        raise ImportError(
            "The 'typer' library is required to use the cli tool. "
            "Please install it with: pip install cascade-py[cli]"
        )

    app = typer.Typer()
    graph = build_graph(target)

    # Find all unique parameter definitions in the graph
    params: dict[str, Param] = {
        node.param_spec.name: node.param_spec
        for node in graph.nodes
        if node.node_type == "param"
    }

    def main(**kwargs):
        """The actual function that Typer will wrap."""
        from .. import run as cascade_run

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        cascade_run(target, params=run_params)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []
    for p in params.values():
        # Determine the default value for Typer
        # If no default, it's a required CLI argument (or option if -- is used)
        default = p.default if p.default is not None else ...

        # Create the Typer Option with all relevant info
        option = typer.Option(
            default,
            f"--{p.name}",
            help=p.description,
        )

        # Default to str if no type is provided, as CLI args are inherently strings
        annotation = p.type if p.type is not None else str

        sig_param = inspect.Parameter(
            name=p.name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=option,
            annotation=annotation,
        )
        sig_params.append(sig_param)

    # Set the dynamic signature on the main function
    main.__signature__ = inspect.Signature(parameters=sig_params)
    # Give it a docstring for better --help
    main.__doc__ = "Runs the Cascade workflow."

    # Register the dynamically created function with Typer
    app.command()(main)

    return app
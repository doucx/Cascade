import inspect
from typing import Any, Callable

try:
    import typer
except ImportError:
    typer = None

from cascade.spec.lazy_types import LazyResult
from cascade.context import get_current_context
from cascade.spec.input import ParamSpec


def create_cli(target: "LazyResult[Any]") -> Callable[[], None]:
    if typer is None:
        raise ImportError(
            "The 'typer' library is required to use the cli tool. "
            "Please install it with: pip install cascade-py[cli]"
        )

    app = typer.Typer()

    # In v1.3, we retrieve specs from the global context, populated when
    # the workflow was defined (e.g. when `cs.Param()` was called).
    context = get_current_context()
    all_specs = context.get_all_specs()

    # Filter for ParamSpec
    params: dict[str, ParamSpec] = {
        spec.name: spec for spec in all_specs if isinstance(spec, ParamSpec)
    }

    def main(**kwargs):
        from cascade import run as cascade_run

        # Extract log_level explicitly since it's injected by Typer via the dynamic signature
        log_level = kwargs.pop("log_level", "INFO")
        log_format = kwargs.pop("log_format", "human")

        # Filter out None values so they don't override defaults in cs.run
        run_params = {k: v for k, v in kwargs.items() if v is not None}
        result = cascade_run(
            target, params=run_params, log_level=log_level, log_format=log_format
        )
        if result is not None:
            print(result)

    # --- Metaprogramming to create the dynamic signature ---
    sig_params = []

    # 1. Add standard CLI options
    log_level_param = inspect.Parameter(
        name="log_level",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=typer.Option(
            "INFO",
            "--log-level",
            help="Minimum level for console logging (DEBUG, INFO, WARNING, ERROR).",
        ),
        annotation=str,
    )
    log_format_param = inspect.Parameter(
        name="log_format",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=typer.Option(
            "human",
            "--log-format",
            help="Format for logging ('human' or 'json').",
        ),
        annotation=str,
    )
    sig_params.extend([log_level_param, log_format_param])

    # 2. Add user-defined parameters
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

from typing import Any
from cascade.spec.task import task

@task(name="_internal_gather", pure=True)
def _internal_gather(*args: Any) -> Any:
    """Internal task to collect multiple LazyResults into a list."""
    return list(args)

@task(name="_get_param_value", pure=True)
def _get_param_value(name: str, params_context: Any = None) -> Any:
    """Internal task to retrieve a parameter from the execution context."""
    if params_context is None:
        return None
    return params_context.get(name)

@task(name="_get_env_var", pure=True)
def _get_env_var(name: str) -> Any:
    """Internal task to retrieve an environment variable."""
    import os
    return os.environ.get(name)
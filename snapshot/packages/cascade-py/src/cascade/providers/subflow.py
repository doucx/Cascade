import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
from cascade.runtime.engine import Engine
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor
from cascade.runtime.bus import MessageBus


class SubflowProvider(Provider):
    name = "subflow"

    def create_factory(self) -> LazyFactory:
        return _subflow_task


@task(name="subflow")
async def _subflow_task(
    path: str, target: str, params: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Dynamically loads a workflow from a file and executes it in an isolated engine.

    Args:
        path: Path to the Python file containing the workflow definition.
        target: The variable name in the module that holds the LazyResult (or callable).
        params: Parameters to inject into the sub-workflow.
    """
    # 1. Validate and Load Module
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Subflow file not found: {file_path}")

    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for subflow file: {file_path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"Error executing subflow definition file '{file_path}': {e}")

    # 2. Extract Target
    target_obj = getattr(module, target, None)
    if target_obj is None:
        raise ValueError(f"Target '{target}' not found in {file_path}")

    # 3. Create Isolated Engine
    # Note: The subflow runs in isolation. It does not share the parent's
    # resource manager or event bus.
    # For now, subflow logs are not forwarded to the parent bus to keep things clean.
    # Errors will propagate as exceptions.
    sub_bus = MessageBus()
    sub_engine = Engine(
        solver=NativeSolver(),
        executor=LocalExecutor(),
        bus=sub_bus,
        # TODO: Consider passing system_resources from parent?
        # For now, use default (unlimited) or let OS handle resource contention.
    )

    # 4. Execute
    return await sub_engine.run(target_obj, params=params)
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from cascade.spec.dsl.task import task
from cascade.spec.runtime.interfaces import LazyFactory, Provider
from cascade.runtime.host import create_engine


class SubflowProvider(Provider):
    name = "subflow"

    def create_factory(self) -> LazyFactory:
        return _subflow_task


@task(name="subflow")
async def _subflow_task(
    path: str, target: str, params: Optional[Dict[str, Any]] = None
) -> Any:
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
        raise RuntimeError(
            f"Error executing subflow definition file '{file_path}': {e}"
        )

    # 2. Extract Target
    target_obj = getattr(module, target, None)
    if target_obj is None:
        raise ValueError(f"Target '{target}' not found in {file_path}")

    # 3. Create Isolated Engine using the central factory
    # Note: The subflow runs in isolation. It does not share the parent's
    # resource manager or event bus. Errors will propagate as exceptions.
    sub_engine = create_engine()

    # 4. Execute
    return await sub_engine.run(target_obj, params=params)
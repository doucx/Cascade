from typing import Any, Dict

try:
    import yaml
except ImportError:
    yaml = None

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider
import asyncio


@task(name="load_yaml")
async def _read_yaml_task(path: str) -> Dict[str, Any]:
    if yaml is None:
        raise ImportError(
            "The 'PyYAML' library is required to use the YAML loader. "
            "Please install it with: pip install cascade-py[config]"
        )

    def blocking_read():
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    return await asyncio.to_thread(blocking_read)


@task(name="lookup")
def _lookup_task(source: Dict[str, Any], key: str) -> Any:
    parts = key.split(".")
    current = source

    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                raise KeyError(
                    f"Configuration key segment '{part}' not found in path: {key}"
                )
        elif isinstance(current, list):
            try:
                index = int(part)
                current = current[index]
            except (ValueError, IndexError):
                raise KeyError(
                    f"Configuration key segment '{part}' is not a valid list index or list is exhausted in path: {key}"
                )
        else:
            raise TypeError(
                f"Cannot access segment '{part}' on non-container type '{type(current).__name__}' at path: {key}"
            )

    return current


class YamlLoaderProvider(Provider):
    name = "load_yaml"

    def create_factory(self) -> LazyFactory:
        return _read_yaml_task


class LookupProvider(Provider):
    name = "lookup"

    def create_factory(self) -> LazyFactory:
        return _lookup_task

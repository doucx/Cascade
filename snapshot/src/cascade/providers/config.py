from typing import Any, Dict, Union

try:
    import yaml
except ImportError:
    yaml = None

from cascade.spec.task import task, LazyResult
from cascade.spec.resource import inject
from cascade.providers import LazyFactory


class ConfigProvider:
    name = "config"

    def create_factory(self) -> LazyFactory:
        if yaml is None:
            # We enforce yaml as the standard for configuration lookup due to common usage
            raise ImportError(
                "The 'PyYAML' library is required to use the config provider. "
                "Please install it with: pip install cascade-py[config]"
            )
        return _config_factory


def _config_factory(key: Union[str, LazyResult]) -> LazyResult[Any]:
    """
    Factory function exposed as cs.config.

    Args:
        key: The dot-separated configuration key string, or a LazyResult
             that resolves to the key string.
    
    Returns:
        A LazyResult that resolves to the configuration value.
    """
    # The actual config data (the dict) is assumed to be registered as a resource.
    # This task depends on an injected resource named 'config_data'.
    return _config_lookup_task(key=key, config=inject("config_data"))


@task(name="config_lookup")
def _config_lookup_task(key: str, config: Dict[str, Any]) -> Any:
    """
    Executes a dot-separated lookup in the provided configuration dictionary.
    """
    parts = key.split(".")
    current = config
    
    for part in parts:
        if isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                raise KeyError(f"Configuration key segment '{part}' not found in path: {key}")
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
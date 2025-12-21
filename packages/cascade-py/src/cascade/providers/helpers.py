from typing import Dict, Any, Optional

from cascade.spec.task import task
from cascade.providers import LazyFactory, Provider


# --- Tasks ---

@task(name="dict")
def _dict_task(**kwargs) -> Dict[str, Any]:
    """
    Creates a dictionary from keyword arguments.
    Useful for composing dynamic contexts in the graph.
    """
    return kwargs


@task(name="format")
def _format_task(template: str, *args, **kwargs) -> str:
    """
    Formats a string using Python's str.format syntax.
    
    Usage:
        cs.format("Hello, {name}!", name=cs.Param("name"))
    """
    return template.format(*args, **kwargs)


# --- Providers ---

class DictProvider(Provider):
    name = "dict"

    def create_factory(self) -> LazyFactory:
        return _dict_task


class FormatProvider(Provider):
    name = "format"

    def create_factory(self) -> LazyFactory:
        return _format_task
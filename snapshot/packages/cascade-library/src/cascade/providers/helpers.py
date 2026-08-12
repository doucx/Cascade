from __future__ import annotations

from typing import Any

from cascade.spec.dsl.task import task
from cascade.spec.runtime.interfaces import LazyFactory, Provider

# --- Tasks ---


@task(name="dict")
def _dict_task(**kwargs) -> dict[str, Any]:
    return kwargs


@task(name="format")
def _format_task(template: str, *args, **kwargs) -> str:
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

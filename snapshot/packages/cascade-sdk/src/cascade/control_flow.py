from __future__ import annotations

from typing import Any

from cascade.spec.dsl.fluent import LazyResult
from cascade.spec.dsl.jump import JumpSelector


def select_jump(routes: dict[str, LazyResult | None]) -> JumpSelector:
    return JumpSelector(routes=routes)


def bind(source: LazyResult, target: Any):
    source._jump_selector = target

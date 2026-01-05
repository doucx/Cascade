from typing import Dict, Optional, Any
from cascade.spec.dsl.fluent import LazyResult
from cascade.spec.dsl.jump import JumpSelector


def select_jump(routes: Dict[str, Optional[LazyResult]]) -> JumpSelector:
    return JumpSelector(routes=routes)


def bind(source: LazyResult, target: Any):
    source._jump_selector = target

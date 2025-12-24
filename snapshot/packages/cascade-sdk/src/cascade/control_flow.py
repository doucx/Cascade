from typing import Dict, Optional, Any
from cascade.spec.lazy_types import LazyResult
from cascade.spec.jump import JumpSelector


def select_jump(routes: Dict[str, Optional[LazyResult]]) -> JumpSelector:
    """
    Creates a JumpSelector for explicit control flow.
    """
    return JumpSelector(routes=routes)


def bind(source: LazyResult, target: Any):
    """
    Statically binds a source task to a control flow target (e.g. JumpSelector).
    This creates a structural edge in the graph.
    """
    source._jump_selector = target
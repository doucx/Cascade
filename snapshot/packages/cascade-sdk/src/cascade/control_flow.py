from typing import Dict, Optional, Any
from cascade.spec.lazy_types import LazyResult
from cascade.spec.jump import Jump, JumpSelector
from cascade.graph.binding import bind as _register_bind


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
    _register_bind(source._uuid, target)
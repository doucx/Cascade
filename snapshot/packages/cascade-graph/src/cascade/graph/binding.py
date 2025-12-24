from contextvars import ContextVar
from typing import Dict, Any, List, Tuple

# Stores a list of (source_uuid, target_selector) tuples
_pending_bindings: ContextVar[List[Tuple[str, Any]]] = ContextVar(
    "pending_bindings", default=[]
)


def bind(source_uuid: str, target: Any):
    """Registers a binding intent in the current context."""
    bindings = _pending_bindings.get().copy()
    bindings.append((source_uuid, target))
    _pending_bindings.set(bindings)


def consume_bindings() -> List[Tuple[str, Any]]:
    """Retrieves and clears the pending bindings."""
    b = _pending_bindings.get()
    _pending_bindings.set([])
    return b
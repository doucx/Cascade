from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class Ref:
    """
    A physical reference to a data object stored in an external ObjectStore.
    This is the fundamental particle of the v3.1 Physics Layer.

    The Physics Layer (Reactor) only operates on Ref objects, never on the actual
    heavyweight payloads.
    """

    uri: str
    """The Uniform Resource Identifier for the data (e.g., mem://uuid, redis://key)."""

    meta: Dict[str, Any] = field(default_factory=dict)
    """
    Lightweight metadata hoisted from the payload to allow routing decisions
    without I/O (e.g., {'type': 'Tensor', 'size': 1024, 'is_error': False}).
    """
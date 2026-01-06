from dataclasses import dataclass, field
from typing import Dict, Any

from cascade.spec.physical.object import Ref


@dataclass(frozen=True)
class ComputeRequest:
    """
    A standard data structure to define a computation request dispatched
    from the Physics Layer to the Data Plane.
    """

    code_hash: str
    """The canonical hash of the code to execute."""

    input_refs: Dict[str, Ref]
    """A dictionary mapping argument names to input References."""

    reply_to_nid: str
    """
    The "reply-to" address. After computation, the result Token should be
    injected into the DataNode with this ID.
    """

    trace: Dict[str, Any] = field(default_factory=dict)
    """The physical trace inherited from the original Token, for context propagation."""
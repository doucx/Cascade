from typing import Dict, Any, Literal
from dataclasses import dataclass, field
from queue import Queue

from cascade.spec.physics import Token


@dataclass
class ObservedEvent:
    """A structured event produced by an Observer node for external consumption."""

    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)


def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:
    """
    The standard implementation for an Observability Node (F_obs).

    It consumes a Token from a lifecycle data node (D_life), converts its
    trace information into a structured ObservedEvent, and puts it onto an
    external queue for telemetry systems.

    This function does not return anything; its purpose is to create a side-effect.

    Args:
        inputs: A dictionary mapping input port names to their corresponding Tokens.
                Expected port: 'event_token'.
        queue: The external queue to which the ObservedEvent will be sent.
    """
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    queue.put(event)

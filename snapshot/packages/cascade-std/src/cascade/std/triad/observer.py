from typing import Dict, Any, Literal
from dataclasses import dataclass, field
from asyncio import Queue

from cascade.spec.physics import Token


@dataclass
class ObservedEvent:
    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)


async def standard_observer(inputs: Dict[str, Token], queue: Queue) -> None:
    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)

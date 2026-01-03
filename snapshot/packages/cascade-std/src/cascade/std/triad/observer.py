from typing import Dict, Any, Literal
from dataclasses import dataclass, field
from asyncio import Queue

from cascade.spec.physics import Token, PhysicsNode


@dataclass
class ObservedEvent:
    event_type: Literal["start", "end"]
    trace_data: Dict[str, Any] = field(default_factory=dict)




async def standard_observer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # 1. Get queue from the resource registry
    # In a real run, this would be a proper ResourceRegistry instance.
    # In tests, it might be a mock or a simple dict-like object.
    queue = resources.get("system.observer.queue")

    event_token = inputs["event_token"]
    trace = event_token.trace

    # Determine event type based on the presence of 'end_ts', which is only
    # added by the Stainer node at the end of a lifecycle.
    event_type = "end" if "end_ts" in trace else "start"

    event = ObservedEvent(event_type=event_type, trace_data=trace)
    await queue.put(event)

    # Observers do not return tokens into the graph
    return {}

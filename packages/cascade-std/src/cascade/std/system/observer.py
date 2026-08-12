from __future__ import annotations

from typing import Any

from cascade.spec import EventIR
from cascade.spec.physical.nodes import PhysicsNode, Token


def standard_observer(
    inputs: dict[str, Token], node: PhysicsNode, resources: Any
) -> dict[str, Token]:
    # The Observer is now a "Dumb Relay".
    # It blindly forwards the IR payload to the system EventBus.

    # 1. Get the EventBus from resources
    # This must be injected by the runtime/harness.
    bus = resources.get("system.event_bus")

    # 2. Extract IR
    token = inputs["event_token"]
    ir: EventIR = token.payload

    # 3. Publish
    if bus and ir:
        # We assume the bus supports the 'publish_ir' protocol
        bus.publish_ir(ir)

    # Observers do not return tokens into the graph
    return {}

from typing import Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.std.specs import ResourceRequestorSpec
from cascade.std.kernel_tools import implements


@implements(ResourceRequestorSpec)
def resource_requestor(
    io: ResourceRequestorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    amount_token = io.amount
    assert amount_token is not None, "Amount token missing"

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    io.req_out = Token(payload=amount_token.payload, trace=trace)

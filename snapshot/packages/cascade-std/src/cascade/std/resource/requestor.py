from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode


async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # Sovereignty Update: We inject the requestor's ID into the trace.
    # The Allocator will use this to route the Grant to the correct dedicated port.
    trace = amount_token.trace.copy()
    trace["requestor_id"] = node.id

    return {"req_out": Token(payload=amount_token.payload, trace=trace)}

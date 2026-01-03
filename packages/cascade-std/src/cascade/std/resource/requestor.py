from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    amount_token = inputs["amount"]

    # We use the node's own ID as the routing tag.
    # The Builder is responsible for ensuring the Distributor downstream
    # knows how to route 'node.id' back to the correct Bleacher.
    return {"req_out": Token(payload=amount_token.payload, tag=node.id)}

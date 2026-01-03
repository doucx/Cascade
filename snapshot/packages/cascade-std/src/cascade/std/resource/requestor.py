from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def resource_requestor(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    """
    Acts as a Tag Injector.
    Takes a raw amount (from a Const Probe) and wraps it in a Token
    tagged with this node's ID (or a configured tag).

    In the Builder, we will map this node's ID to something that correlates
    with the Task ID, so the Broker can route the Grant back.
    """
    amount_token = inputs["amount"]
    
    # We use the node's own ID as the routing tag.
    # The Builder is responsible for ensuring the Distributor downstream
    # knows how to route 'node.id' back to the correct Bleacher.
    return {"req_out": Token(payload=amount_token.payload, tag=node.id)}
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def const_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    A simple Identity Probe.
    It takes a value from a DataNode (which holds a constant payload)
    and passes it forward.
    In a more complex setup, this could wait for a Trigger.
    """
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    return {"out": Token(payload=val_token.payload, trace=val_token.trace)}
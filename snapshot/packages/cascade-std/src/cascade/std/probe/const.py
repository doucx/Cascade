from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    return {"out": Token(payload=val_token.payload, trace=val_token.trace)}

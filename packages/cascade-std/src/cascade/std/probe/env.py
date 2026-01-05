import os
from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode


async def env_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    name = inputs["name"].payload
    val = os.environ.get(name)
    return {"out": Token(payload=val)}

import os
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def env_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    name = inputs["name"].payload
    val = os.environ.get(name)
    return {"out": Token(payload=val)}

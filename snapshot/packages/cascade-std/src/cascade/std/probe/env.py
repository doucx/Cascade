import os
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode

def env_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Samples a value from the OS environment variables based on the 'name' input.
    """
    name = inputs["name"].payload
    val = os.environ.get(name)
    return {"out": Token(payload=val)}
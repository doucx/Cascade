from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


async def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}

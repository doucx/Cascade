from typing import Dict, Any
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


async def halt_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command="HALT")
    return {"out": Token(payload=control_token)}

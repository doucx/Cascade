from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken


def drain_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}

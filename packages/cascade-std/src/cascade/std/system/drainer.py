from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.runtime.system import SystemControlToken


def drain_signal(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}

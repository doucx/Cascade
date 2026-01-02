from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken

def drain_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Receives a trigger and emits a SIG_DRAIN system control token.
    This signals that a branch of the graph will produce no new data,
    aiding in graceful shutdown detection.
    """
    control_token = SystemControlToken(command="DRAIN")
    return {"out": Token(payload=control_token)}
from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.spec.system import SystemControlToken

def halt_signal(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Receives a trigger token and emits a SIG_HALT system control token.
    This requests an immediate, hard shutdown of the Reactor.
    """
    # The output token is a special system type, not a standard data Token.
    # The VM will need to have a special port/handler for these.
    # We wrap it in a standard token for transport through a standard channel.
    control_token = SystemControlToken(command="HALT")
    return {"out": Token(payload=control_token)}
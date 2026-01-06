from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def pulse_generator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    trigger_token = inputs["trigger"]
    # We pass the trigger's payload and trace forward to maintain context
    return {"out": Token(payload=trigger_token.payload, trace=trigger_token.trace)}

from typing import Dict
from cascade.spec.physics import Token, PhysicsNode


async def pulse_generator(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    trigger_token = inputs["trigger"]
    # We pass the trigger's payload and trace forward to maintain context
    return {"out": Token(payload=trigger_token.payload, trace=trigger_token.trace)}

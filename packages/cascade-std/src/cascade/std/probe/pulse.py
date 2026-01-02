from typing import Dict
from cascade.spec.physics import Token, PhysicsNode

def pulse_generator(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    Acts as an energy multiplier. Takes a trigger and emits a sync pulse.
    The actual 'broadcasting' to multiple ports is defined by the graph channels
    wired to the 'out' port.
    """
    trigger_token = inputs["trigger"]
    # We pass the trigger's payload and trace forward to maintain context
    return {"out": Token(payload=trigger_token.payload, trace=trigger_token.trace)}
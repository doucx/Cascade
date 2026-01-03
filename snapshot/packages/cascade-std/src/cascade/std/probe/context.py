from typing import Dict
from cascade.spec.physics import Token, PhysicsNode
from cascade.common.context import get_current_context


async def param_probe(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    name = inputs["name"].payload
    # In a real run, values are resolved by the Context/Engine.
    # Here we interface with the common context.
    ctx = get_current_context()

    # We assume context has a method to get values by spec name.
    # If not found, it returns None (as a payload).
    val = ctx.get_value(name) if hasattr(ctx, "get_value") else None

    return {"out": Token(payload=val)}

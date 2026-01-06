from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


async def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    raw_value = val_token.payload

    # Ref-Based Architecture:
    # Probes are responsible for materializing external/static data into Refs.
    store = resources.get("system.object_store")

    # Metadata Hoisting: Lift scalars to metadata for Kernel access
    meta = {}
    if isinstance(raw_value, (int, float, bool, str)) and len(str(raw_value)) < 64:
        meta["value"] = raw_value

    ref = store.put(raw_value, metadata=meta)

    return {"out": Token(payload=ref, trace=val_token.trace)}

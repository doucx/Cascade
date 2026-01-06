from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def const_probe(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # Assuming the input port is named 'value'
    val_token = inputs["value"]
    raw_value = val_token.payload

    # Ref-Based Architecture:
    # Probes are responsible for materializing external/static data into Refs.
    store = resources.get("system.object_store")

    # Scalar Hoisting:
    # If the value is a scalar, we hoist it into metadata so Kernel ICs (Allocator)
    # can read it without I/O.
    meta = {}
    if isinstance(raw_value, (int, float, bool, str)) and len(str(raw_value)) < 1024:
        meta["scalar_value"] = raw_value

    ref = store.put(raw_value, metadata=meta)

    return {"out": Token(payload=ref, trace=val_token.trace)}

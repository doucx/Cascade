from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def gate_passthrough(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # We expect 'req_in' and 'signal_in' ports
    req_token = inputs.get("req_in")
    signal_token = inputs.get("signal_in")

    if req_token and signal_token:
        # The gate is open, pass the request token through
        return {"req_out": req_token}

    # Should not happen if wired correctly, but return empty if not fully triggered
    return {}

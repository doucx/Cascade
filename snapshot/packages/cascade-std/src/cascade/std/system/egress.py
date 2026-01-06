from typing import Dict, Any
from cascade.spec.physical.nodes import Token, PhysicsNode


def standard_egress(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    """
    Standard Egress IC (Physical Exit).
    
    This node acts as a 'Black Hole' in the physical graph. It consumes a Token
    and teleports it to the 'system.egress_queue', allowing the Strategy layer
    to observe the result.
    
    Ports:
        - in: The token to export.
    """
    # 1. Get the Egress Queue from system resources
    # This must be registered by the Strategy during startup.
    queue = resources.get("system.egress_queue")
    
    # 2. Consume the token
    # Phase 3.3 of the roadmap defines the input port as 'in'.
    token = inputs.get("in")
    
    if token:
        # 3. Export
        # We wrap the token with the node ID so the Strategy knows which egress node it came from.
        # This allows handling multiple egress points (e.g. for different task results).
        queue.put_nowait((node.id, token))
    
    # 4. Return empty (Evaporate)
    # No tokens are returned to the graph. The energy leaves the system here.
    return {}
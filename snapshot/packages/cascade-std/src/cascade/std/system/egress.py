from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import EgressSpec
from cascade.std.kernel_tools import implements


@implements(EgressSpec)
def standard_egress(
    io: EgressSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    # 1. Get the Egress Queue
    queue = resources.get("system.egress_queue")

    # 2. Consume the token
    # Spec mapping: io.input_token -> inputs["in"]
    token = io.input_token

    if token:
        # 3. Export
        queue.put_nowait((node.id, token))
    
    # 4. Return empty (Evaporate)
    # Implicitly returns the empty 'outputs' dict created by @implements

from typing import Any
from cascade.spec.physical.nodes import PhysicsNode
from cascade.std.specs import GateSpec
from cascade.spec.physics.binding import implements


@implements(GateSpec)
def gate_passthrough(io: GateSpec.IO, node: PhysicsNode, resources: Any) -> None:
    # Access inputs via Spec-defined attributes
    # The IO wrapper maps 'io.req_in' -> inputs["req_in"]
    if io.req_in and io.signal_in:
        # The gate is open, pass the request token through
        # The IO wrapper maps 'io.req_out' -> outputs["req_out"]
        io.req_out = io.req_in

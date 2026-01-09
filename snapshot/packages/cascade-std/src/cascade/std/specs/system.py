from typing import Protocol, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class EgressSpec(PhysicsSpec):
    # The physical port name is "in" (reserved keyword in Python).
    # We map it to the attribute 'input_token'.
    input_token = Port.Input("in", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        input_token: Optional[Token]


class GateSpec(PhysicsSpec):
    req_in = Port.Input("req_in", role=PortRole.DATA)
    signal_in = Port.Input("signal_in", role=PortRole.SIGNAL)

    req_out = Port.Output("req_out", role=PortRole.DATA)

    class IO(Protocol):
        req_in: Optional[Token]
        signal_in: Optional[Token]

        req_out: Token


class SleepSpec(PhysicsSpec):
    delay_in = Port.Input("delay_in", role=PortRole.DATA, type="float")
    data_in = Port.Input("data_in", role=PortRole.DATA, type=PortType.Token)
    # No outputs (Void) - flow resumes via ChronosService injection

    class IO(Protocol):
        delay_in: Optional[Token]
        data_in: Optional[Token]

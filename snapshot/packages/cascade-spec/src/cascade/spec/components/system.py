from typing import Protocol, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class ObservabilitySpec(PhysicsSpec):
    event_token = Port.Input("event_token", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        event_token: Optional[Token]


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


class RetrySpec(PhysicsSpec):
    error_in = Port.Input("error_in", role=PortRole.DATA)
    context_in = Port.Input("context_in", role=PortRole.DATA)

    retry_out = Port.Output("retry_out", role=PortRole.DATA)
    fail_out = Port.Output("fail_out", role=PortRole.DATA)

    class IO(Protocol):
        error_in: Optional[Token]
        context_in: Optional[Token]
        retry_out: Token
        fail_out: Token


class TerminatorSpec(PhysicsSpec):
    # Typically triggerless, but can have an optional input
    trigger = Port.Input("in", role=PortRole.SIGNAL)
    out = Port.Output("out", role=PortRole.DATA)

    class IO(Protocol):
        trigger: Optional[Token]
        out: Token


class DrainerSpec(PhysicsSpec):
    trigger = Port.Input("in", role=PortRole.SIGNAL)
    out = Port.Output("out", role=PortRole.DATA)

    class IO(Protocol):
        trigger: Optional[Token]
        out: Token

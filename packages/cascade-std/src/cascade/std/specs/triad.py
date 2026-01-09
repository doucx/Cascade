from typing import Protocol, Dict, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class BleacherSpec(PhysicsSpec):
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Conditional Execution
    condition = Port.Input("condition", role=PortRole.SIGNAL, type="Bool")
    # Startup Pulse
    pulse = Port.Input("__pulse__", role=PortRole.SIGNAL)

    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
    trace_output = Port.Output("trace_output", role=PortRole.DATA, type="TraceCtx")
    context_output = Port.Output("context_output", role=PortRole.DATA, type="Dict")
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        # Inputs
        args: Dict[str, Token]
        condition: Optional[Token]
        pulse: Optional[Token]

        # Outputs
        worker_input: Token
        trace_output: Token
        context_output: Token
        obs_output: Token


class ObservabilitySpec(PhysicsSpec):
    event_token = Port.Input("event_token", role=PortRole.OBSERVABILITY, type="Event")

    class IO(Protocol):
        event_token: Optional[Token]


class WorkerSpec(PhysicsSpec):
    # Inputs
    worker_input = Port.Input("worker_input", role=PortRole.DATA, type="Dict")

    # Outputs
    worker_result = Port.Output("worker_result", role=PortRole.DATA, type=PortType.Any)

    class IO(Protocol):
        # Inputs
        worker_input: Optional[Token]

        # Outputs
        worker_result: Token


class StainerSpec(PhysicsSpec):
    # Inputs
    worker_result = Port.Input("worker_result", role=PortRole.DATA, type=PortType.Any)
    trace_input = Port.Input("trace_input", role=PortRole.DATA, type="TraceCtx")
    context_input = Port.Input("context_input", role=PortRole.DATA, type="Dict")

    # Outputs
    output_default = Port.Output(
        "output_default", role=PortRole.DATA, type=PortType.Token
    )
    output_error = Port.Output("output_error", role=PortRole.DATA, type=PortType.Token)
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")
    # Resource returns are dynamic

    class IO(Protocol):
        # Inputs
        worker_result: Optional[Token]
        trace_input: Optional[Token]
        context_input: Optional[Token]

        # Outputs
        output_default: Token
        output_error: Token
        obs_output: Token

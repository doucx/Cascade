from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


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


class ObservabilitySpec(PhysicsSpec):
    event_token = Port.Input("event_token", role=PortRole.OBSERVABILITY, type="Event")


class WorkerSpec(PhysicsSpec):
    # Inputs
    worker_input = Port.Input("worker_input", role=PortRole.DATA, type="Dict")

    # Outputs
    worker_result = Port.Output("worker_result", role=PortRole.DATA, type=PortType.Any)


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

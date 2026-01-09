from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


class BleacherSpec(PhysicsSpec):
    """
    Contract for the Pre-process Node (F_pre).
    Inputs are dynamic (based on Task arguments), so they are not exhaustively listed here.
    """
    # Inputs (Dynamic)
    # Collects all inputs not matched by other static input definitions.
    args = Port.MapInput(role=PortRole.DATA)

    # Outputs
    worker_input = Port.Output("worker_input", role=PortRole.DATA, type="Dict")
    trace_output = Port.Output("trace_output", role=PortRole.DATA, type="TraceCtx")
    context_output = Port.Output("context_output", role=PortRole.DATA, type="Dict")
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")


class WorkerSpec(PhysicsSpec):
    """
    Contract for the Execution Node (F_exec).
    Pure business logic execution.
    """
    # Inputs
    worker_input = Port.Input("worker_input", role=PortRole.DATA, type="Dict")

    # Outputs
    worker_result = Port.Output("worker_result", role=PortRole.DATA, type=PortType.Any)


class StainerSpec(PhysicsSpec):
    """
    Contract for the Post-process Node (F_post).
    Wraps results and handles routing.
    """
    # Inputs
    worker_result = Port.Input("worker_result", role=PortRole.DATA, type=PortType.Any)
    trace_input = Port.Input("trace_input", role=PortRole.DATA, type="TraceCtx")
    context_input = Port.Input("context_input", role=PortRole.DATA, type="Dict")

    # Outputs
    output_default = Port.Output("output_default", role=PortRole.DATA, type=PortType.Token)
    output_error = Port.Output("output_error", role=PortRole.DATA, type=PortType.Token)
    obs_output = Port.Output("obs_output", role=PortRole.OBSERVABILITY, type="Event")
    # Resource returns are dynamic
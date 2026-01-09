from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


class DiscreteAllocatorSpec(PhysicsSpec):
    """
    Contract for a Discrete Resource Allocator.
    Manages the distribution of countable resource units from a ledger.
    """
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    req_in = Port.Input("req_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Note: The main grant output. Dynamic dedicated ports (gnt_for_X) may also exist.
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE, type=PortType.Token)
    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)


class DiscreteReclaimerSpec(PhysicsSpec):
    """
    Contract for a Discrete Resource Reclaimer.
    Handles the return of resource units to the ledger.
    """
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    rel_in = Port.Input("rel_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Signal emitted to wake up parked requests
    signal_out = Port.Output("signal_out", role=PortRole.SIGNAL, type=PortType.Token)
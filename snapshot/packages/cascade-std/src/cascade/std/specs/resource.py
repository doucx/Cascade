from typing import Protocol, MutableMapping, Optional
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType
from cascade.spec.physical.nodes import Token


class DiscreteAllocatorSpec(PhysicsSpec):
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    req_in = Port.Input("req_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Note: The main grant output. Dynamic dedicated ports (gnt_for_X) may also exist.
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE, type=PortType.Token)

    # Dynamic Grant Outputs
    # Allows writing to 'gnt_for_{requestor_id}'
    grants = Port.MapOutput(
        prefix="gnt_for_", role=PortRole.RESOURCE, type=PortType.Token
    )

    # Output for requests that cannot be satisfied immediately
    req_parked = Port.Output("req_parked", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        # Inputs
        ledger_in: Optional[Token]
        req_in: Optional[Token]

        # Outputs
        ledger_out: Token
        gnt_out: Token
        grants: MutableMapping[str, Token]
        req_parked: Token


class ResourceRequestorSpec(PhysicsSpec):
    amount = Port.Input("amount", role=PortRole.DATA, type="int")
    req_out = Port.Output("req_out", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        amount: Optional[Token]
        req_out: Token


class DiscreteReclaimerSpec(PhysicsSpec):
    # Inputs
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    rel_in = Port.Input("rel_in", role=PortRole.DATA, type=PortType.Token)

    # Outputs
    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    # Signal emitted to wake up parked requests
    signal_out = Port.Output("signal_out", role=PortRole.SIGNAL, type=PortType.Token)

    class IO(Protocol):
        # Inputs
        ledger_in: Optional[Token]
        rel_in: Optional[Token]

        # Outputs
        ledger_out: Token
        signal_out: Token
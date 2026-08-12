from __future__ import annotations

from typing import MutableMapping, Protocol

from cascade.spec.physical.nodes import Token
from cascade.spec.physics import PhysicsSpec, Port, PortRole, PortType


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
        ledger_in: Token | None
        req_in: Token | None

        # Outputs
        ledger_out: Token
        gnt_out: Token
        grants: MutableMapping[str, Token]
        req_parked: Token


class ResourceRequestorSpec(PhysicsSpec):
    amount = Port.Input("amount", role=PortRole.DATA, type="int")
    req_out = Port.Output("req_out", role=PortRole.DATA, type=PortType.Token)

    class IO(Protocol):
        amount: Token | None
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
        ledger_in: Token | None
        rel_in: Token | None

        # Outputs
        ledger_out: Token
        signal_out: Token


class ContinuousAllocatorSpec(PhysicsSpec):
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    req_in = Port.Input("req_in", role=PortRole.DATA)

    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)
    gnt_out = Port.Output("gnt_out", role=PortRole.RESOURCE)
    req_out = Port.Output("req_out", role=PortRole.DATA)  # For failed/parked requests

    class IO(Protocol):
        ledger_in: Token | None
        req_in: Token | None
        ledger_out: Token
        gnt_out: Token
        req_out: Token


class ContinuousReclaimerSpec(PhysicsSpec):
    ledger_in = Port.Input("ledger_in", role=PortRole.DATA, type=PortType.Ledger)
    rel_in = Port.Input("rel_in", role=PortRole.DATA)

    ledger_out = Port.Output("ledger_out", role=PortRole.DATA, type=PortType.Ledger)

    class IO(Protocol):
        ledger_in: Token | None
        rel_in: Token | None
        ledger_out: Token

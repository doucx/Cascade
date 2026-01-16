from typing import Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.components import ContinuousAllocatorSpec, ContinuousReclaimerSpec
from cascade.spec.physics.binding import implements


@dataclass
class ContinuousLedger:
    total: float
    available: float


@implements(ContinuousAllocatorSpec)
def continuous_allocator(
    io: ContinuousAllocatorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    req_token = io.req_in

    assert ledger_token is not None, "Ledger token for allocator is missing"
    assert req_token is not None, "Request token for allocator is missing"

    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_amount = float(req_token.payload)

    if ledger.available >= req_amount:
        ledger.available -= req_amount
        # Sovereignty: In the future, we should use trace-based routing here like discrete.py
        # For now, just remove the tag to fix the crash.
        io.gnt_out = Token(payload=req_amount, trace=req_token.trace)
    else:
        io.req_out = req_token

    io.ledger_out = Token(payload=ledger)


@implements(ContinuousReclaimerSpec)
def continuous_reclaimer(
    io: ContinuousReclaimerSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    rel_token = io.rel_in

    assert ledger_token is not None, "Ledger token for reclaimer is missing"
    assert rel_token is not None, "Release token for reclaimer is missing"

    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data

    release_amount = float(rel_token.payload)
    ledger.available = min(ledger.total, ledger.available + release_amount)

    io.ledger_out = Token(payload=ledger)

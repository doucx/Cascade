from typing import Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.std.specs import DiscreteAllocatorSpec, DiscreteReclaimerSpec
from cascade.std.kernel_tools import implements


@dataclass
class DiscreteLedger:
    total: int
    available: int


def _extract_scalar(payload: Any) -> Union[int, float]:
    if isinstance(payload, Ref):
        # v3.1: Try to get hoisted scalar
        if "scalar_value" in payload.meta:
            return payload.meta["scalar_value"]
        # If not hoisted, we technically can't read it in Kernel.
        # But for now we fail gracefully or return 0?
        # Raising error is better to catch missing hoisting.
        raise ValueError(
            f"Ref {payload.uri} missing 'scalar_value' metadata for Kernel access."
        )
    return payload


@implements(DiscreteAllocatorSpec)
def discrete_allocator(
    io: DiscreteAllocatorSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    assert ledger_token is not None, "Ledger token missing"
    ledger_data = ledger_token.payload

    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = io.req_in
    assert req_token is not None, "Request token missing"
    req_amount = int(_extract_scalar(req_token.payload))

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            # Use dynamic output map
            io.grants[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing
            io.gnt_out = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Park
        io.req_parked = req_token

    io.ledger_out = Token(payload=ledger)


@implements(DiscreteReclaimerSpec)
def discrete_reclaimer(
    io: DiscreteReclaimerSpec.IO, node: PhysicsNode, resources: Any
) -> None:
    ledger_token = io.ledger_in
    assert ledger_token is not None, "Ledger token missing"
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = io.rel_in
    assert rel_token is not None, "Release token missing"
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    io.ledger_out = Token(payload=ledger)
    # Emit wake-up signal
    io.signal_out = Token(payload=None, trace=rel_token.trace)

from typing import Dict, Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode


@dataclass
class DiscreteLedger:
    total: int
    available: int


async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    # Ideally we should clone or re-instantiate if immutable, but for now we mutate in place for perf
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = req_token.payload

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount

        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            # The Builder constructs the port name as f"gnt_for_{requestor_id}"
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            # Fallback for legacy/testing (should generally not happen in valid graph)
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = rel_token.payload

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}

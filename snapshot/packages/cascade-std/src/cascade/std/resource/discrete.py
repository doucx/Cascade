from typing import Dict
from dataclasses import dataclass
from cascade.spec.physics import Token, PhysicsNode


@dataclass
class DiscreteLedger:
    total: int
    available: int


async def discrete_broker(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    # Reconstruct ledger object from payload (assuming it's a dict or dataclass)
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    outputs: Dict[str, Token] = {}

    # 1. Process Release (Replenish first)
    if "rel_in" in inputs:
        release_amount = inputs["rel_in"].payload
        # Cap at total to prevent overflow logic errors, though in a closed system this shouldn't happen
        ledger.available = min(ledger.total, ledger.available + release_amount)

    # 2. Process Request
    if "req_in" in inputs:
        req_token = inputs["req_in"]
        req_amount = req_token.payload

        if ledger.available >= req_amount:
            # Grant
            ledger.available -= req_amount
            # Emit Grant Token (Payload can be the amount granted)
            # CRITICAL: Propagate the tag from the request to the grant
            # so the distributor can route it back to the correct worker.
            outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
        else:
            # Reject & Recirculate
            # We emit the original request token back to a recirculation loop
            outputs["req_out"] = req_token

    # 3. Emit Updated Ledger
    # We pass the object back. In a real persistence scenario, this would be serialized.
    outputs["ledger_out"] = Token(payload=ledger)

    return outputs

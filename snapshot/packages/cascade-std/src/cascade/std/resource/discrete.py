from typing import Dict
from dataclasses import dataclass
from cascade.spec.physics import Token, PhysicsNode


@dataclass
class DiscreteLedger:
    total: int
    available: int


async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    outputs: Dict[str, Token] = {}
    
    # Process Request
    req_token = inputs["req_in"]
    req_amount = req_token.payload

    if ledger.available >= req_amount:
        # Grant
        ledger.available -= req_amount
        outputs["gnt_out"] = Token(payload=req_amount, tag=req_token.tag)
    else:
        # Reject & Recirculate
        outputs["req_out"] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    # Process Release
    release_amount = inputs["rel_in"].payload
    ledger.available = min(ledger.total, ledger.available + release_amount)

    return {"ledger_out": Token(payload=ledger)}

from typing import Dict, Any, Optional
from dataclasses import dataclass
from cascade.spec.physics import Token, PhysicsNode

@dataclass
class DiscreteLedger:
    total: int
    available: int

def discrete_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    A Discrete Resource Broker using the Self-Loop Ledger pattern.
    
    Inputs:
        ledger_in: Token containing DiscreteLedger(total, available)
        req_in: (Optional) Token requesting N units. Payload: int
        rel_in: (Optional) Token releasing N units. Payload: int
        
    Outputs:
        ledger_out: Updated ledger
        gnt_out: (Conditional) Grant token if request succeeded
        req_out: (Conditional) Original request token if failed (Recirculation)
    """
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
            outputs["gnt_out"] = Token(payload=req_amount)
        else:
            # Reject & Recirculate
            # We emit the original request token back to a recirculation loop
            outputs["req_out"] = req_token
            
    # 3. Emit Updated Ledger
    # We pass the object back. In a real persistence scenario, this would be serialized.
    outputs["ledger_out"] = Token(payload=ledger)
    
    return outputs
from typing import Dict, Any
from dataclasses import dataclass
from cascade.spec.physics import Token, PhysicsNode

@dataclass
class ContinuousLedger:
    total: float
    available: float

async def continuous_broker(inputs: Dict[str, Token], node: PhysicsNode) -> Dict[str, Token]:
    """
    A Continuous Resource Broker using the Self-Loop Ledger pattern.
    Handles floating-point resources (e.g., memory, disk space).
    
    Inputs:
        ledger_in: Token containing ContinuousLedger
        req_in: (Optional) Token requesting N units. Payload: float
        rel_in: (Optional) Token releasing N units. Payload: float
        
    Outputs:
        ledger_out: Updated ledger
        gnt_out: (Conditional) Grant token
        req_out: (Conditional) Recirculated request token
    """
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = ContinuousLedger(**ledger_data)
    else:
        ledger = ledger_data
    
    outputs: Dict[str, Token] = {}
    
    # 1. Process Release
    if "rel_in" in inputs:
        release_amount = float(inputs["rel_in"].payload)
        # Simple clamp to avoid floating point drift exceeding total
        ledger.available = min(ledger.total, ledger.available + release_amount)
    
    # 2. Process Request
    if "req_in" in inputs:
        req_token = inputs["req_in"]
        req_amount = float(req_token.payload)
        
        # Use a small epsilon for float comparison if needed, but >= usually suffices
        if ledger.available >= req_amount:
            ledger.available -= req_amount
            outputs["gnt_out"] = Token(payload=req_amount)
        else:
            # Recirculate
            outputs["req_out"] = req_token
            
    # 3. Emit Updated Ledger
    outputs["ledger_out"] = Token(payload=ledger)
    
    return outputs
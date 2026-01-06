from typing import Dict, Any
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref


@dataclass
class DiscreteLedger:
    total: int
    available: int


async def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    # 1. Access Store (Kernel Capability)
    store = resources.get("system.object_store")

    # 2. Dereference Ledger (Stateful)
    ledger_ref: Ref = inputs["ledger_in"].payload
    # Note: For state, we allow get() in kernel because it's typically in-memory
    ledger_data = store.get(ledger_ref)
    
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    elif isinstance(ledger_data, DiscreteLedger):
        ledger = ledger_data
    else:
        # It might be a Ref if we have nested refs (should not happen in clean state)
        # Or it might be the Raw object if Reactor.prime didn't wrap it.
        # Assuming Reactor.prime wraps initial state, this should be the object.
        raise TypeError(f"Unknown ledger type: {type(ledger_data)}")

    # 3. Read Request (Metadata Hoisted)
    req_token = inputs["req_in"]
    req_ref: Ref = req_token.payload
    
    # Try to get value from metadata first (Fast Path)
    if "value" in req_ref.meta:
        req_amount = req_ref.meta["value"]
    else:
        # Slow Path (Should be avoided by const_probe hoisting)
        req_amount = store.get(req_ref)

    outputs: Dict[str, Token] = {}

    if ledger.available >= req_amount:
        # Grant
        # We mutate the ledger object. Since it's a dataclass, we can clone or mutate.
        # For Ref architecture, we should treat it as immutable and put a new version.
        new_ledger = DiscreteLedger(total=ledger.total, available=ledger.available - req_amount)
        
        # Sovereignty Routing: Determine output port based on requestor_id in trace
        requestor_id = req_token.trace.get("requestor_id")
        if requestor_id:
            out_port = f"gnt_for_{requestor_id}"
            outputs[out_port] = Token(payload=req_amount, trace=req_token.trace)
        else:
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Recirculate
        # Ledger remains unchanged (but we still need to emit it back)
        new_ledger = ledger
        outputs["req_out"] = req_token

    # 4. Commit New State
    # We put the new ledger state back to store and get a NEW Ref
    new_ledger_ref = store.put(new_ledger, metadata={"type": "DiscreteLedger"})
    outputs["ledger_out"] = Token(payload=new_ledger_ref)
    
    return outputs


async def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    store = resources.get("system.object_store")

    # 1. Dereference Ledger
    ledger_ref: Ref = inputs["ledger_in"].payload
    ledger_data = store.get(ledger_ref)
    
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    # 2. Get Release Amount
    rel_token = inputs["rel_in"]
    # Rel payload might be raw int (if coming from Stainer output) or Ref
    # Currently Stainer outputting raw int for resources.
    # TODO: Stainer should probably output Ref too? 
    # For now, let's handle both.
    release_amount = rel_token.payload
    if isinstance(release_amount, Ref):
         # If it's a Ref, try meta
        if "value" in release_amount.meta:
            release_amount = release_amount.meta["value"]
        else:
            release_amount = store.get(release_amount)

    # 3. Update
    new_available = min(ledger.total, ledger.available + release_amount)
    new_ledger = DiscreteLedger(total=ledger.total, available=new_available)

    # 4. Commit
    new_ledger_ref = store.put(new_ledger, metadata={"type": "DiscreteLedger"})

    return {"ledger_out": Token(payload=new_ledger_ref)}
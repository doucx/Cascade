from typing import Dict, Any, Union
from dataclasses import dataclass
from cascade.spec.physical.nodes import Token, PhysicsNode
from cascade.spec.physical.object import Ref
from cascade.spec.physical.ports import PortName


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


def discrete_allocator(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload

    # Extract Ledger (Handle Ref if ledger itself is ref-based in future, currently payload is obj)
    # For now ledger payload is passed as-is (PhysicsDataNode initial_payload)
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    req_token = inputs["req_in"]
    req_amount = int(_extract_scalar(req_token.payload))

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
            # Fallback for legacy/testing
            outputs["gnt_out"] = Token(payload=req_amount, trace=req_token.trace)
    else:
        # Reject & Park
        outputs[PortName.REQ_PARKED] = req_token

    outputs["ledger_out"] = Token(payload=ledger)
    return outputs


def discrete_reclaimer(
    inputs: Dict[str, Token], node: PhysicsNode, resources: Any
) -> Dict[str, Token]:
    ledger_token = inputs["ledger_in"]
    ledger_data = ledger_token.payload
    if isinstance(ledger_data, dict):
        ledger = DiscreteLedger(**ledger_data)
    else:
        ledger = ledger_data

    rel_token = inputs["rel_in"]
    release_amount = int(_extract_scalar(rel_token.payload))

    # Replenish
    ledger.available = min(ledger.total, ledger.available + release_amount)

    outputs = {"ledger_out": Token(payload=ledger)}
    # Emit wake-up signal
    outputs[PortName.SIGNAL_OUT] = Token(payload=None, trace=rel_token.trace)

    return outputs

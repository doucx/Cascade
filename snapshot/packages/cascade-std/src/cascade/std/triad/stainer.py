from typing import Dict, Any
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import StainNode
from cascade.spec.physical.ports import PortRole


async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_mono = time.monotonic()
    now_wall = time.time()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_ref = worker_result_token.payload

    # Merge traces
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

    # 2. Calculate duration
    start_mono = trace_payload.get("start_ts", end_mono)
    duration = end_mono - start_mono
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_mono

    # 3. Construct EventIR
    logical_id = node.id.replace(".stain", "")

    # Heuristic: Extract task_name from physical name "Stain(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Stain(") and node.name.endswith(")"):
        task_name = node.name[6:-1]

    # Determine Status using Metadata
    from cascade.spec.physical.object import Ref
    state = EventState.SUCCEEDED
    error_msg = None
    
    if isinstance(result_ref, Ref) and result_ref.meta.get("is_error"):
        state = EventState.FAILED
        error_msg = result_ref.meta.get("error_msg", "Unknown error")
        # For telemetry, we might want the error type
    elif isinstance(result_ref, Exception):
        # Fallback for legacy raw exception payloads
        state = EventState.FAILED
        error_msg = str(result_ref)

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Handle preview generation
    preview = None
    if isinstance(result_ref, Ref):
        preview = result_ref
    else:
        preview = str(result_ref)[:100]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": now_wall,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": state,
            "task_id": logical_id,
            "task_name": task_name,
            "duration_ms": duration * 1000,
            "error": error_msg,
            "result_preview": preview,
        },
    }

    # 4. Create output tokens
    outputs = {}

    # 4.1 The main result
    outputs["output_default"] = Token(payload=result_payload, trace=trace_payload)

    # 4.2 Observability Event
    outputs["obs_output"] = Token(payload=ir, trace=trace_payload)

    # 4.3 Resource Return
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            amount = 1
            resource_amounts = trace_payload.get("resource_amounts", {})
            if port_name in resource_amounts:
                amount = resource_amounts[port_name]
            outputs[port_name] = Token(payload=amount)

    return outputs

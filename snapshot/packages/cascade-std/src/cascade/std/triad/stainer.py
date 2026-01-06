from typing import Dict, Any
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import StainNode
from cascade.spec.physical.ports import PortRole


def standard_stainer(
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

    task_name = "unknown"
    if node.name.startswith("Stain(") and node.name.endswith(")"):
        task_name = node.name[6:-1]

    # --- Ref-Based Logic ---
    # The result_ref is expected to be a Ref object.
    # We decide state based on its metadata, not its payload.
    state = EventState.SUCCEEDED
    error_msg = None
    output_port = "output_default"
    result_preview = None

    if isinstance(result_ref, Ref):
        is_error = result_ref.meta.get("is_error", False)
        if is_error:
            state = EventState.FAILED
            # The actual error object is in the remote store,
            # we can only preview what's in the meta.
            error_msg = result_ref.meta.get("error_str", "Error flag set in Ref meta")
            output_port = "output_error"
        else:
             result_preview = result_ref.meta.get("preview", str(result_ref))
    elif isinstance(result_ref, Exception):
        # Fallback for systems where an exception might still be passed directly
        state = EventState.FAILED
        error_msg = str(result_ref)
        output_port = "output_error"

    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

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
            "result_preview": result_preview,
        },
    }

    # 4. Create output tokens
    outputs = {}

    # 4.1 The main result (routed via sovereign port)
    outputs[output_port] = Token(payload=result_ref, trace=trace_payload)

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
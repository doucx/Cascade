from typing import Dict
import time

from cascade.spec.physics import Token
from cascade.spec.triad import StainNode
from cascade.spec.ports import PortRole


def standard_stainer(inputs: Dict[str, Token], node: StainNode) -> Dict[str, Token]:
    end_ts = time.monotonic()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_payload = worker_result_token.payload
    # Use a copy to avoid mutating the original trace dict
    trace_payload = trace_input_token.payload.copy()

    # 2. Determine tag based on result (error or success)
    tag = "error" if isinstance(result_payload, Exception) else "default"

    # 3. Calculate duration and update trace
    start_ts = trace_payload.get("start_ts", end_ts)  # Default to end_ts for duration=0
    duration = end_ts - start_ts
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_ts

    # 4. Create output tokens
    outputs = {}

    # 4.1 The main result
    outputs["output"] = Token(payload=result_payload, tag=tag, trace=trace_payload)

    # 4.2 Resource Return (The Loop)
    # We iterate over the node's output ports to find all RESOURCE ports.
    # This is a static guarantee: if the node has a resource output port, we MUST emit to it.
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            # Emit a generic token to the resource port to "refill" the slot
            outputs[port_name] = Token(payload=None)

    return outputs

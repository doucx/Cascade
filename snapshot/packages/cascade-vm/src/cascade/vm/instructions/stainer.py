from typing import Dict
import time

from cascade.spec.physics import Token


def standard_stainer(inputs: Dict[str, Token]) -> Dict[str, Token]:
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
    # Check if we are holding any resources that need to be returned
    held_resources = trace_payload.get("held_resources", [])
    for resource_port in held_resources:
        # Emit a generic token to the resource port to "refill" the slot
        outputs[resource_port] = Token(payload=None)

    return outputs

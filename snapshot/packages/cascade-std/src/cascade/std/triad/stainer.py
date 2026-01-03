from typing import Dict
import time

from cascade.spec.physics import Token
from cascade.spec.triad import StainNode
from cascade.spec.ports import PortRole


from typing import Any


async def standard_stainer(
    inputs: Dict[str, Token], node: StainNode, resources: Any
) -> Dict[str, Token]:
    end_ts = time.monotonic()

    # 1. Extract inputs
    worker_result_token = inputs["worker_result"]
    trace_input_token = inputs["trace_input"]

    result_payload = worker_result_token.payload

    # The trace from the worker token might have been augmented by the worker.
    # The trace_input_token is the one from the "wormhole" D_trace.
    # The most up-to-date trace is the one that came through the worker.
    trace_payload = worker_result_token.trace.copy()
    trace_payload.update(trace_input_token.payload)

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
    for port_name, port_def in node.output_ports.items():
        if port_def.role == PortRole.RESOURCE:
            # Look up the amount to release from trace data
            # The Bleacher stored it under 'resource_amounts' -> 'res_{name}'
            # But the Stainer's output port might be named differently (e.g. 'rel_{name}' or just 'res_{name}')
            # Convention: If Stainer output is 'res_gpu', Bleacher input was 'res_gpu'.
            amount = 1  # Default fallback

            # Try to find the specific amount
            resource_amounts = trace_payload.get("resource_amounts", {})
            if port_name in resource_amounts:
                amount = resource_amounts[port_name]

            # Emit token with the correct amount to replenish the broker
            outputs[port_name] = Token(payload=amount)

    return outputs

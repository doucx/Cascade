from typing import Dict
import time

from cascade.spec.physics import Token


from typing import List, Optional


def standard_bleacher(
    inputs: Dict[str, Token], expected_args: Optional[List[str]] = None
) -> Dict[str, Token]:
    worker_payload: Dict[str, any] = {}
    trace_payload: Dict[str, any] = {}
    held_resources: List[str] = []

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        # Only pass expected data args to the worker
        if expected_args is None or port_name in expected_args:
            worker_payload[port_name] = input_token.payload
        else:
            # It's a resource or signal. We record it to trace.
            # We assume the port_name matches the resource name (e.g. 'resource_gpu')
            held_resources.append(port_name)

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    trace_payload["start_ts"] = time.monotonic()
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Create the output tokens
    worker_token = Token(payload=worker_payload)
    trace_token = Token(payload=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
    }

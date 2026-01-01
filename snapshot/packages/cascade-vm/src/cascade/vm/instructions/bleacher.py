from typing import Dict
import time

from cascade.spec.physics import Token


def standard_bleacher(inputs: Dict[str, Token]) -> Dict[str, Token]:
    """
    The standard implementation for a Pre-process Node (F_pre).

    It "bleaches" input tokens by stripping metadata to create a pure payload
    for the worker, and it prepares trace information for the post-processor.

    Args:
        inputs: A dictionary mapping input port names to their corresponding Tokens.

    Returns:
        A dictionary mapping output port names to newly created Tokens.
        Expected ports:
        - 'worker_input': A Token whose payload is a kwargs dict for F_exec.
        - 'trace_output': A Token whose payload contains merged trace info
                          and a new 'start_ts'.
    """
    worker_payload: Dict[str, any] = {}
    trace_payload: Dict[str, any] = {}

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        worker_payload[port_name] = input_token.payload
        trace_payload.update(input_token.trace)

    # 2. Capture the start timestamp and add it to the trace
    trace_payload["start_ts"] = time.monotonic()

    # 3. Create the output tokens
    worker_token = Token(payload=worker_payload)
    trace_token = Token(payload=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
    }

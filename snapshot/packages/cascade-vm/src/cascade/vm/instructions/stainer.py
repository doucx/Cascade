from typing import Dict
import time

from cascade.spec.physics import Token


def standard_stainer(inputs: Dict[str, Token]) -> Dict[str, Token]:
    """
    The standard implementation for a Post-process Node (F_post).

    It "stains" a pure result from a worker by wrapping it in a new Token
    with appropriate tags and updated trace information (like duration).

    Args:
        inputs: A dictionary mapping input port names to their corresponding Tokens.
                Expected ports:
                - 'worker_result': Token containing the pure result from F_exec.
                - 'trace_input': Token from F_pre containing 'start_ts' and other
                                 initial trace data.

    Returns:
        A dictionary mapping the output port name ('output') to the final
        stained Token.
    """
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

    # 4. Create the final "stained" token
    output_token = Token(payload=result_payload, tag=tag, trace=trace_payload)

    return {"output": output_token}

from typing import Dict, Any, List
import time

from cascade.spec.physics import Token
from cascade.spec.triad import BleachNode
from cascade.spec.ports import PortRole


def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode
) -> Dict[str, Token]:
    worker_payload: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # 1. Extract payloads and merge traces from all inputs
    for port_name, input_token in inputs.items():
        port_def = node.input_ports[port_name]

        if port_def.role == PortRole.DATA:
            worker_payload[port_name] = input_token.payload
        elif port_def.role == PortRole.RESOURCE:
            # It's a resource. We record it to trace.
            held_resources.append(port_name)
        # Observability and Signals are processed for trace but not passed to worker

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

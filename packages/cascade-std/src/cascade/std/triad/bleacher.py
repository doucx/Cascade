from typing import Dict, Any, List
import time

from cascade.spec import EventIR, EventType, EventState
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import BleachNode
from cascade.spec.physical.ports import PortRole


def standard_bleacher(
    inputs: Dict[str, Token], node: BleachNode, resources: Any
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
            # It's a GNT token.
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    start_ts = time.time()  # Use wall clock for IR
    mono_ts = time.monotonic()  # Use monotonic for internal duration calc

    logical_id = node.id.replace(".bleach", "")

    # Heuristic: Extract task_name from physical name "Bleach(MyTask)"
    task_name = "unknown"
    if node.name.startswith("Bleach(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (The Hologram)
    ctx = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    ir: EventIR = {
        "v": "1.0",
        "t": EventType.LIFECYCLE,
        "ts": start_ts,
        "ctx": ctx,
        "phy": {"nid": node.id},
        "data": {
            "state": EventState.RUNNING,
            "task_id": logical_id,
            "task_name": task_name,
        },
    }

    # 4. Create the output tokens
    worker_token = Token(payload=worker_payload, trace=trace_payload)
    trace_token = Token(payload=trace_payload)
    # obs_output now carries the IR as payload
    obs_token = Token(payload=ir, trace=trace_payload)

    return {
        "worker_input": worker_token,
        "trace_output": trace_token,
        "obs_output": obs_token,
    }

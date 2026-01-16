from typing import Any, Dict
import time

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.dyad import LanderNode
from cascade.spec.specs.dyad import LanderSpec
from cascade.spec.physics.binding import implements


@implements(LanderSpec)
def standard_lander(io: LanderSpec.IO, node: LanderNode, resources: Any) -> None:
    end_mono = time.monotonic()
    now_wall = time.time()

    # 1. Extract Result & Recover Trace
    result_token = io.result_token
    if not result_token:
        # Should technically not happen if activated, but safety first
        return

    result_payload = result_token.payload
    trace_payload = result_token.trace.copy()  # Recovered from Tunnel

    # 2. Calculate Duration
    # The start_ts was injected by the Launcher into the trace
    start_mono = trace_payload.get("start_ts", end_mono)
    duration = end_mono - start_mono
    trace_payload["duration"] = duration
    trace_payload["end_ts"] = end_mono

    # 3. Construct EventIR (FINISHED)
    logical_id = node.id.split(".")[0]
    
    task_name = "unknown"
    if node.name.startswith("Land(") and node.name.endswith(")"):
        task_name = node.name[5:-1]

    # Determine Status
    state = EventState.SUCCEEDED
    error_msg = None

    if isinstance(result_payload, Exception):
        state = EventState.FAILED
        error_msg = str(result_payload)

    ctx: EventContext = {}
    if "rid" in trace_payload:
        ctx["rid"] = trace_payload["rid"]

    # Preview Logic
    preview = None
    if state == EventState.SUCCEEDED:
        # Check for Ref-like object by duck typing or explicit import
        # For simplicity in stdlib, we just str() it if not explicit Ref check
        # Ideally we check against cascade.spec.physical.object.Ref
        if hasattr(result_payload, "uri") and hasattr(result_payload, "meta"):
             preview = result_payload
        else:
             preview = str(result_payload)[:100]

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

    # 4. Emit Observability Event
    io.obs_output = Token(payload=ir, trace=trace_payload)

    # 5. Routing (Default vs Error)
    if state == EventState.FAILED and "output_error" in node.output_ports:
        io.output_error = Token(payload=result_payload, trace=trace_payload)
    else:
        io.output_default = Token(payload=result_payload, trace=trace_payload)

    # 6. Resource Return
    # We iterate over the dynamic resource return ports defined on the Node
    # and match them against what we claimed in the trace.
    resource_amounts = trace_payload.get("resource_amounts", {})
    
    # We can't iterate io.resource_returns directly as it's an output map.
    # We must look at the Node's output ports definition.
    for port_name in node.output_ports:
        # The Spec defines resource returns as a map, so physical ports will have names.
        # We need a way to identify which ports are resource returns.
        # The Spec defines them with role=RESOURCE.
        port_def = node.output_ports[port_name]
        if port_def.role == "RESOURCE": # String match or import PortRole
            # Found a resource return port
            amount = resource_amounts.get(port_name, 1) # Default to 1 if not tracked
            io.resource_returns[port_name] = Token(payload=amount)
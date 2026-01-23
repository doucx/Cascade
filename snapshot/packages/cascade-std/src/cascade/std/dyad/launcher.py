from typing import Any, Dict, List
import time
import logging

from cascade.spec import EventIR, EventType, EventState, EventContext
from cascade.spec.physical.nodes import Token
from cascade.spec.physical.dyad import LauncherNode
from cascade.spec.physical.ports import PortRole
from cascade.spec.physical.object import Ref
from cascade.spec.specs.dyad import LauncherSpec
from cascade.spec.physics.binding import implements
from cascade.spec.runtime import ComputeRequest

logger = logging.getLogger(__name__)


@implements(LauncherSpec)
def standard_launcher(io: LauncherSpec.IO, node: LauncherNode, resources: Any) -> None:
    # 1. Prepare Inputs & Trace
    input_args: List[Any] = []
    input_kwargs: Dict[str, Any] = {}
    trace_payload: Dict[str, Any] = {}
    held_resources: List[str] = []

    # Use the metadata from the LauncherNode to reconstruct args and kwargs
    for port_name in node.arg_port_names:
        token = io.args.get(port_name)
        if token:
            input_args.append(token.payload)
            trace_payload.update(token.trace)

    for port_name in node.kwarg_port_names:
        token = io.args.get(port_name)
        if token:
            input_kwargs[port_name] = token.payload
            trace_payload.update(token.trace)

    # Handle other non-data ports like resources
    for port_name, input_token in io.args.items():
        if not input_token or port_name in node.arg_port_names or port_name in node.kwarg_port_names:
            continue

        port_def = node.input_ports[port_name]
        trace_payload.update(input_token.trace)

        if port_def.role == PortRole.RESOURCE:
            held_resources.append(port_name)
            if "resource_amounts" not in trace_payload:
                trace_payload["resource_amounts"] = {}
            trace_payload["resource_amounts"][port_name] = input_token.payload


    start_ts = time.time()  # Wall clock for IR
    mono_ts = time.monotonic()  # Monotonic for internal duration

    # Extract logical ID and Task Name
    # Convention: logical_id is the prefix of the physical ID
    logical_id = node.id.split(".")[0]

    task_name = "unknown"
    if node.name.startswith("Launch(") and node.name.endswith(")"):
        task_name = node.name[7:-1]

    # Update Trace
    trace_payload["start_ts"] = mono_ts
    trace_payload["id"] = logical_id
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Construct EventIR (STARTED)
    ctx: EventContext = {}
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

    # 4. Emit Observability Event
    # The Launcher emits the STARTED event directly.
    io.obs_output = Token(payload=ir, trace=trace_payload)

    # 5. Dispatch Compute Request
    if not node.reply_to_nid:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'reply_to_nid'. "
            "Determinism violation: Cannot dispatch without explicit return address."
        )

    if not node.canonical_code_structure_hash:
        raise ValueError(
            f"LauncherNode '{node.id}' is missing 'canonical_code_structure_hash'."
        )

    request = ComputeRequest(
        code_hash=node.canonical_code_structure_hash,
        input_args=input_args,
        input_kwargs=input_kwargs,
        reply_to_nid=node.reply_to_nid,
        trace=trace_payload,  # Trace Tunneling happens here
    )

    try:
        compute_queue = resources.get("system.compute_queue")
        compute_queue.put_nowait(request)
    except KeyError:
        logger.error("Resource 'system.compute_queue' not found.")
        raise
    except Exception:
        logger.exception(f"Failed to dispatch compute request for node {node.id}")
        raise

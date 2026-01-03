from typing import Dict, Any, List
import time

from cascade.spec.physics import Token
from cascade.spec.triad import BleachNode
from cascade.spec.ports import PortRole


async def standard_bleacher(
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
        elif port_def.role == PortRole.RESOURCE_REQUEST:
            # New logic: This input defines a resource requirement amount.
            # We don't pass it to the worker, but we use it to emit a request token.
            # The 'port_name' here is expected to be something like 'req_amount_gpu'.
            # We need to map it to an output port.
            pass
        elif port_def.role == PortRole.RESOURCE:
            # Legacy/Fallback
            held_resources.append(port_name)

        trace_payload.update(input_token.trace)

    # 2. Capture metadata
    trace_payload["start_ts"] = time.monotonic()
    if held_resources:
        trace_payload["held_resources"] = held_resources

    # 3. Create the output tokens
    outputs = {
        "worker_input": Token(payload=worker_payload),
        "trace_output": Token(payload=trace_payload),
    }

    # 4. Handle Active Resource Requests
    # We iterate over INPUT ports to find request amounts.
    # Convention: Input port 'req_amount_{res}' corresponds to Output port 'req_{res}'
    for port_name, input_token in inputs.items():
        port_def = node.input_ports[port_name]
        if port_def.role == PortRole.RESOURCE_REQUEST:
            # Identify the resource name.
            # Assuming port name format: "req_amount_<resource_name>"
            if port_name.startswith("req_amount_"):
                res_name = port_name[11:]
                out_port_name = f"req_{res_name}"

                # Check if this output port exists
                if out_port_name in node.output_ports:
                    amount = input_token.payload
                    # Emit request token with tag = node.id (The Bleacher's ID)
                    # This allows the Grant to be routed back to the worker associated with this Bleacher.
                    # Note: We use the Bleacher's ID as the routing tag. The Distributor
                    # must route to the Worker based on this tag (or a derived one).
                    # Actually, let's use the Logical Node ID if possible.
                    # But node.id is physical (e.g. "node_1.bleach").
                    # Using "node_1.bleach" as tag is fine, as long as Builder knows this.
                    outputs[out_port_name] = Token(payload=amount, tag=node.id)

    return outputs

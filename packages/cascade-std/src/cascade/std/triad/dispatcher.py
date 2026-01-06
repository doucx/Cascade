import logging
from typing import Dict, Any

from cascade.spec.physical.nodes import Token
from cascade.spec.physical.triad import WorkerNode
from cascade.spec.physical.object import Ref
from cascade.vm.compute import ComputeRequest
from cascade.reflection import PhysicalIdGenerator

logger = logging.getLogger(__name__)


def standard_dispatcher(
    inputs: Dict[str, Token], node: WorkerNode, resources: Any
) -> Dict[str, Token]:
    # 1. Extract input refs from the token prepared by the Bleacher.
    # The payload of the 'worker_input' token is expected to be a Dict[str, Ref].
    worker_input_token = inputs["worker_input"]
    input_refs: Dict[str, Ref] = worker_input_token.payload

    # 2. Deterministically calculate the reply-to address (the downstream DataNode).
    base_id = node.id.replace(".worker", "")
    reply_to_nid = PhysicalIdGenerator.worker_out_data(base_id)

    # 3. Get the code hash from the node's metadata.
    code_hash = node.canonical_code_structure_hash
    if not code_hash:
        raise ValueError(
            f"WorkerNode '{node.id}' is missing canonical_code_structure_hash. "
            "The compiler must populate this field."
        )

    # 4. Propagate the trace from the input token.
    trace = worker_input_token.trace

    # 5. Assemble the computation request.
    request = ComputeRequest(
        code_hash=code_hash,
        input_refs=input_refs,
        reply_to_nid=reply_to_nid,
        trace=trace,
    )

    # 6. Get the compute queue from the resource registry and dispatch.
    try:
        compute_queue = resources.get("system.compute_queue")
        compute_queue.put_nowait(request)
    except KeyError:
        logger.error(
            "Resource 'system.compute_queue' not found. Cannot dispatch compute request."
        )
        raise
    except Exception:
        logger.exception(f"Failed to dispatch compute request for node {node.id}")
        raise

    # 7. Return an empty dictionary to "evaporate" the energy in this branch.
    # The flow will resume when the ComputeService places the result token
    # into the `reply_to_nid` data node.
    return {}
